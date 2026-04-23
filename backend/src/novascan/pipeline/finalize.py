"""Finalize Lambda — ranking-based selection and DynamoDB/S3 updates.

Receives parallel pipeline results from Step Functions, selects the result
with the highest ranking score, updates the receipt record in DynamoDB,
creates line item and pipeline result records, and updates S3 object metadata.

This is the final step in the OCR pipeline state machine.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit, single_metric
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

from novascan.models.extraction import ExtractionResult
from novascan.pipeline.ranking import rank_results
from novascan.shared.constants import ITEM, PIPELINE, RECEIPT
from novascan.shared.dynamo import get_table

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="NovaScan")

s3_client = boto3.client("s3")

# Pipeline type labels matching DynamoDB SK pattern: RECEIPT#{ulid}#PIPELINE#{type}
PIPELINE_OCR_AI = "ocr-ai"
PIPELINE_AI_MULTIMODAL = "ai-multimodal"
PIPELINE_AI_VISION_V2 = "ai-vision-v2"

# Pipeline types in Step Functions Parallel branch order (indices 0, 1, 2)
PIPELINE_TYPES = [PIPELINE_OCR_AI, PIPELINE_AI_MULTIMODAL, PIPELINE_AI_VISION_V2]

# Pricing constants (USD per unit)
NOVA_LITE_INPUT_COST_PER_TOKEN = Decimal("0.00000006")   # $0.06 / 1M tokens
NOVA_LITE_OUTPUT_COST_PER_TOKEN = Decimal("0.00000024")  # $0.24 / 1M tokens
NOVA_2_LITE_INPUT_COST_PER_TOKEN = Decimal("0.0000003")  # $0.30 / 1M tokens
NOVA_2_LITE_OUTPUT_COST_PER_TOKEN = Decimal("0.0000025") # $2.50 / 1M tokens
TEXTRACT_EXPENSE_COST_PER_PAGE = Decimal("0.01")         # $0.01 / page


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Finalize receipt processing — rank all pipelines, select best, persist.

    Expected event shape (from Step Functions):
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",
            "receiptId": "01ABC...",
            "customCategories": [...],
            "pipelineResults": [
                {"extractionResult": {...}, "modelId": "...", "processingTimeMs": 123},
                {"extractionResult": {...}, "modelId": "...", "processingTimeMs": 456},
                {"extractionResult": {...}, "modelId": "...", "processingTimeMs": 789}
            ]
        }

    pipelineResults indices match PIPELINE_TYPES order: [ocr-ai, ai-multimodal, ai-vision-v2].
    Any element may be an error payload: {"error": "...", "errorType": "..."}
    """
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    bucket = event["bucket"]
    key = event["key"]
    raw_results = event["pipelineResults"]

    logger.info(
        "Finalizing receipt",
        extra={"user_id": user_id, "receipt_id": receipt_id},
    )

    # Parse all pipeline results (index matches PIPELINE_TYPES order)
    parsed: list[tuple[dict[str, Any], ExtractionResult | None, str]] = []
    for idx, pipeline_type in enumerate(PIPELINE_TYPES):
        raw = raw_results[idx]
        result = _parse_pipeline_result(raw, pipeline_type)
        parsed.append((raw, result, pipeline_type))

    # Ranking-based selection: pick the result with the highest ranking score
    selected_result, selected_type, status = _select_by_ranking(parsed)

    # Publish pipeline completion metrics
    _emit_pipeline_metrics(parsed)

    # Determine ranking winner (same as selected_type when selection succeeds)
    ranking_winner = selected_type

    # Persist everything to DynamoDB
    now = datetime.now(UTC).isoformat()
    table = get_table()

    _store_pipeline_results(table, user_id, receipt_id, parsed, now)

    failure_reason = None
    if status == "failed":
        # H4 — Generic failure_reason in DynamoDB; raw error details logged only
        logger.error(
            "All pipelines failed",
            extra={
                p_type: {"error": raw.get("error", "unknown"), "errorType": raw.get("errorType", "unknown")}
                for raw, _, p_type in parsed
            },
        )
        failure_reason = "Pipeline processing failed. Check CloudWatch logs for details."

    _update_receipt(
        table, user_id, receipt_id, selected_result, status,
        False, ranking_winner, failure_reason, now,
    )

    if selected_result is not None:
        _create_line_items(table, user_id, receipt_id, selected_result, now)

    # Update S3 object metadata
    _update_s3_metadata(bucket, key, receipt_id, status, now)

    # Emit receipt status metrics
    _emit_receipt_metrics(status)

    logger.info(
        "Finalize completed",
        extra={
            "receipt_id": receipt_id,
            "status": status,
            "ranking_winner": ranking_winner,
            "selected_pipeline": selected_type,
        },
    )

    return {
        "receiptId": receipt_id,
        "status": status,
        "usedFallback": False,
        "rankingWinner": ranking_winner,
        "selectedPipeline": selected_type,
    }


def _parse_pipeline_result(
    raw: dict[str, Any], pipeline_type: str
) -> ExtractionResult | None:
    """Parse a pipeline result dict into ExtractionResult, or None on error."""
    if "error" in raw:
        logger.warning(
            "Pipeline returned error",
            extra={
                "pipeline_type": pipeline_type,
                "error": raw.get("error"),
                "error_type": raw.get("errorType"),
            },
        )
        return None

    try:
        return ExtractionResult.model_validate(raw["extractionResult"])
    except Exception:
        logger.exception(
            "Failed to parse pipeline result",
            extra={"pipeline_type": pipeline_type},
        )
        return None


def _select_by_ranking(
    parsed: list[tuple[dict[str, Any], ExtractionResult | None, str]],
) -> tuple[ExtractionResult | None, str | None, str]:
    """Select the result with the highest ranking score.

    Returns:
        (selected_result, selected_type, status)
    """
    scored: list[tuple[ExtractionResult, str, float]] = []
    for _raw, result, pipeline_type in parsed:
        if result is not None:
            score = rank_results(result)
            scored.append((result, pipeline_type, score))

    if not scored:
        logger.error("All pipelines failed — receipt marked as failed")
        return None, None, "failed"

    scored.sort(key=lambda x: x[2], reverse=True)
    winner_result, winner_type, winner_score = scored[0]

    scores_extra: dict[str, Any] = {f"{p_type}_score": s for _, p_type, s in scored}
    scores_extra["winner"] = winner_type
    scores_extra["winner_score"] = winner_score
    logger.info("Ranking-based selection", extra=scores_extra)

    with single_metric(
        name="RankingDecision",
        unit=MetricUnit.Count,
        value=1,
        namespace="NovaScan",
    ) as metric:
        metric.add_dimension(name="Winner", value=winner_type)

    return winner_result, winner_type, "confirmed"


@tracer.capture_method
def _store_pipeline_results(
    table: Any,
    user_id: str,
    receipt_id: str,
    parsed: list[tuple[dict[str, Any], ExtractionResult | None, str]],
    now: str,
) -> None:
    """Store all pipeline results as PIPELINE# entities in DynamoDB."""
    for raw, result, pipeline_type in parsed:
        _write_pipeline_record(table, user_id, receipt_id, raw, result, pipeline_type, now)


def _compute_cost(
    pipeline_type: str,
    input_tokens: int,
    output_tokens: int,
    textract_pages: int,
    model_id: str = "",
) -> Decimal:
    """Compute the USD cost for a single pipeline execution."""
    if "nova-2-lite" in model_id:
        input_rate = NOVA_2_LITE_INPUT_COST_PER_TOKEN
        output_rate = NOVA_2_LITE_OUTPUT_COST_PER_TOKEN
    else:
        input_rate = NOVA_LITE_INPUT_COST_PER_TOKEN
        output_rate = NOVA_LITE_OUTPUT_COST_PER_TOKEN

    nova_cost = (
        Decimal(str(input_tokens)) * input_rate
        + Decimal(str(output_tokens)) * output_rate
    )
    if pipeline_type == PIPELINE_OCR_AI:
        return nova_cost + Decimal(str(textract_pages)) * TEXTRACT_EXPENSE_COST_PER_PAGE
    return nova_cost


def _write_pipeline_record(
    table: Any,
    user_id: str,
    receipt_id: str,
    raw: dict[str, Any],
    parsed: ExtractionResult | None,
    pipeline_type: str,
    now: str,
) -> None:
    """Write a single PIPELINE# record to DynamoDB."""
    ranking_score = rank_results(parsed) if parsed else None

    input_tokens = raw.get("inputTokens", 0)
    output_tokens = raw.get("outputTokens", 0)
    textract_pages = raw.get("textractPages", 0)

    item: dict[str, Any] = {
        "PK": f"USER#{user_id}",
        "SK": f"{RECEIPT}#{receipt_id}#{PIPELINE}#{pipeline_type}",
        "entityType": PIPELINE,
        "createdAt": now,
        "modelId": raw.get("modelId", "unknown"),
        "processingTimeMs": raw.get("processingTimeMs", 0),
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "textractPages": textract_pages,
        "costUsd": _compute_cost(
            pipeline_type, input_tokens, output_tokens, textract_pages,
            model_id=raw.get("modelId", ""),
        ),
    }

    if parsed is not None:
        extracted_data = json.loads(parsed.model_dump_json())
        item["extractedData"] = _convert_floats_to_decimal(extracted_data)
        item["confidence"] = Decimal(str(parsed.confidence))

    if ranking_score is not None:
        item["rankingScore"] = Decimal(str(ranking_score))

    if "error" in raw:
        # H4 — Store error classification only, not raw exception message.
        # Raw details are logged to CloudWatch by the originating Lambda.
        item["error"] = raw.get("errorType", "Unknown")
        item["errorType"] = raw.get("errorType", "Unknown")

    table.put_item(Item=item)


@tracer.capture_method
def _update_receipt(
    table: Any,
    user_id: str,
    receipt_id: str,
    result: ExtractionResult | None,
    status: str,
    used_fallback: bool,
    ranking_winner: str | None,
    failure_reason: str | None,
    now: str,
) -> None:
    """Update the receipt record with extraction data and status."""
    pk = f"USER#{user_id}"
    sk = f"{RECEIPT}#{receipt_id}"

    update_parts = [
        "#status = :status",
        "updatedAt = :now",
    ]
    attr_names: dict[str, str] = {"#status": "status"}
    attr_values: dict[str, Any] = {
        ":status": status,
        ":now": now,
    }

    if result is not None:
        update_parts.extend([
            "merchant = :merchant",
            "merchantAddress = :merchantAddress",
            "receiptDate = :receiptDate",
            "#currency = :currency",
            "#subtotal = :subtotal",
            "tax = :tax",
            "tip = :tip",
            "#total = :total",
            "#category = :category",
            "subcategory = :subcategory",
            "paymentMethod = :paymentMethod",
        ])
        attr_names.update({
            "#currency": "currency",
            "#subtotal": "subtotal",
            "#total": "total",
            "#category": "category",
        })
        attr_values.update({
            ":merchant": result.merchant.name,
            ":merchantAddress": result.merchant.address,
            ":receiptDate": result.receiptDate.isoformat() if result.receiptDate else None,
            ":currency": result.currency,
            ":subtotal": Decimal(str(result.subtotal)),
            ":tax": Decimal(str(result.tax)),
            ":tip": Decimal(str(result.tip)) if result.tip is not None else None,
            ":total": Decimal(str(result.total)),
            ":category": result.category,
            ":subcategory": result.subcategory,
            ":paymentMethod": result.paymentMethod,
        })

        # Update GSI1SK from createdAt to receiptDate if receiptDate was extracted
        if result.receiptDate:
            update_parts.append("GSI1SK = :gsi1sk")
            attr_values[":gsi1sk"] = f"{result.receiptDate.isoformat()}#{receipt_id}"

    if used_fallback:
        update_parts.append("usedFallback = :fallback")
        attr_values[":fallback"] = True

    if ranking_winner is not None:
        update_parts.append("rankingWinner = :winner")
        attr_values[":winner"] = ranking_winner

    if failure_reason is not None:
        update_parts.append("failureReason = :failReason")
        attr_values[":failReason"] = failure_reason

    update_expression = "SET " + ", ".join(update_parts)

    # M11 — Idempotency: prevent stale overwrites with ConditionExpression
    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
            ConditionExpression="attribute_not_exists(updatedAt) OR updatedAt < :now",
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning(
            "Skipped stale receipt update (newer version exists)",
            extra={"receipt_id": receipt_id},
        )


@tracer.capture_method
def _create_line_items(
    table: Any,
    user_id: str,
    receipt_id: str,
    result: ExtractionResult,
    now: str,
) -> None:
    """Create line item records in DynamoDB.

    Each line item is stored as RECEIPT#{ulid}#ITEM#{nnn} where nnn is
    a 3-digit zero-padded index.
    """
    if not result.lineItems:
        return

    pk = f"USER#{user_id}"

    # M11 — Idempotency: delete existing items before writing new ones
    # This prevents duplicate line items on re-execution.
    existing = table.query(
        KeyConditionExpression=(
            Key("PK").eq(pk)
            & Key("SK").begins_with(f"{RECEIPT}#{receipt_id}#{ITEM}#")
        ),
        ProjectionExpression="PK, SK",
    )
    if existing.get("Items"):
        with table.batch_writer() as batch:
            for existing_item in existing["Items"]:
                batch.delete_item(Key={"PK": existing_item["PK"], "SK": existing_item["SK"]})

    with table.batch_writer() as batch:
        for idx, line_item in enumerate(result.lineItems):
            nnn = f"{idx + 1:03d}"
            sk = f"{RECEIPT}#{receipt_id}#{ITEM}#{nnn}"

            item: dict[str, Any] = {
                "PK": pk,
                "SK": sk,
                "entityType": ITEM,
                "name": line_item.name,
                "quantity": Decimal(str(line_item.quantity)),
                "unitPrice": Decimal(str(line_item.unitPrice)),
                "totalPrice": Decimal(str(line_item.totalPrice)),
                "createdAt": now,
            }

            if line_item.subcategory:
                item["subcategory"] = line_item.subcategory

            batch.put_item(Item=item)

    logger.info(
        "Line items created",
        extra={"receipt_id": receipt_id, "count": len(result.lineItems)},
    )


@tracer.capture_method
def _update_s3_metadata(
    bucket: str, key: str, receipt_id: str, status: str, processed_at: str
) -> None:
    """Update S3 object metadata via copy_object with MetadataDirective REPLACE.

    Sets x-amz-meta-status, x-amz-meta-receipt-id, x-amz-meta-processed-at.
    """
    try:
        # Read existing metadata first to preserve content type
        head = s3_client.head_object(Bucket=bucket, Key=key)
        content_type = head.get("ContentType", "image/jpeg")

        # M12 — Explicit S3 encryption on copy
        s3_client.copy_object(
            Bucket=bucket,
            Key=key,
            CopySource={"Bucket": bucket, "Key": key},
            MetadataDirective="REPLACE",
            ContentType=content_type,
            ServerSideEncryption="AES256",
            Metadata={
                "status": status,
                "receipt-id": receipt_id,
                "processed-at": processed_at,
            },
        )
    except Exception:
        # S3 metadata update is non-critical — log and continue
        logger.exception(
            "Failed to update S3 metadata",
            extra={"bucket": bucket, "key": key},
        )


def _emit_pipeline_metrics(
    parsed: list[tuple[dict[str, Any], ExtractionResult | None, str]],
) -> None:
    """Publish PipelineCompleted and PipelineLatency metrics."""
    for raw, _result, pipeline_type in parsed:
        succeeded = "error" not in raw
        outcome = "success" if succeeded else "failure"

        with single_metric(
            name="PipelineCompleted",
            unit=MetricUnit.Count,
            value=1,
            namespace="NovaScan",
        ) as metric:
            metric.add_dimension(name="PipelineType", value=pipeline_type)
            metric.add_dimension(name="Outcome", value=outcome)

        if succeeded and "processingTimeMs" in raw:
            with single_metric(
                name="PipelineLatency",
                unit=MetricUnit.Milliseconds,
                value=raw["processingTimeMs"],
                namespace="NovaScan",
            ) as metric:
                metric.add_dimension(name="PipelineType", value=pipeline_type)


def _emit_receipt_metrics(status: str) -> None:
    """Publish ReceiptStatus metric."""
    with single_metric(
        name="ReceiptStatus",
        unit=MetricUnit.Count,
        value=1,
        namespace="NovaScan",
    ) as metric:
        metric.add_dimension(name="Status", value=status)


def _convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj
