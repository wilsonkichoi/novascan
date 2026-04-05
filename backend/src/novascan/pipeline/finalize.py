"""Finalize Lambda — main/shadow selection, ranking, and DynamoDB/S3 updates.

Receives the parallel pipeline results from Step Functions, applies main/shadow
selection logic, ranks both results, updates the receipt record in DynamoDB,
creates line item and pipeline result records, and updates S3 object metadata.

This is the final step in the OCR pipeline state machine.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit, single_metric
from aws_lambda_powertools.utilities.typing import LambdaContext

from novascan.models.extraction import ExtractionResult
from novascan.pipeline.ranking import rank_results
from novascan.shared.constants import ITEM, PIPELINE, RECEIPT
from novascan.shared.dynamo import get_table

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="NovaScan")

s3_client = boto3.client("s3")

# Which pipeline is "main" — determined by CDK config (defaultPipeline).
# The other pipeline is "shadow".
DEFAULT_PIPELINE = os.environ.get("DEFAULT_PIPELINE", "ocr-ai")

# Pipeline type labels matching DynamoDB SK pattern: RECEIPT#{ulid}#PIPELINE#{type}
PIPELINE_OCR_AI = "ocr-ai"
PIPELINE_AI_MULTIMODAL = "ai-multimodal"


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Finalize receipt processing — select result, rank, and persist.

    Expected event shape (from Step Functions):
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",
            "receiptId": "01ABC...",
            "customCategories": [...],
            "pipelineResults": [
                {"extractionResult": {...}, "modelId": "...", "processingTimeMs": 123},
                {"extractionResult": {...}, "modelId": "...", "processingTimeMs": 456}
            ]
        }

    pipelineResults[0] is the main pipeline result, [1] is the shadow pipeline.
    Either element may be an error payload: {"error": "...", "errorType": "..."}
    """
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    bucket = event["bucket"]
    key = event["key"]
    pipeline_results = event["pipelineResults"]

    logger.info(
        "Finalizing receipt",
        extra={
            "user_id": user_id,
            "receipt_id": receipt_id,
            "default_pipeline": DEFAULT_PIPELINE,
        },
    )

    # Determine which position is which pipeline type
    main_type, shadow_type = _get_pipeline_types()
    main_raw = pipeline_results[0]
    shadow_raw = pipeline_results[1]

    # Parse results — None if the pipeline errored
    main_result = _parse_pipeline_result(main_raw, main_type)
    shadow_result = _parse_pipeline_result(shadow_raw, shadow_type)

    # Main/shadow selection
    selected_result, selected_type, used_fallback, status = _select_result(
        main_result, main_type, shadow_result, shadow_type
    )

    # Publish pipeline completion metrics
    _emit_pipeline_metrics(main_raw, main_type, shadow_raw, shadow_type)

    # Ranking — run on both results regardless of selection
    ranking_winner = _rank_and_get_winner(main_result, shadow_result, main_type, shadow_type)

    # Persist everything to DynamoDB
    now = datetime.now(UTC).isoformat()
    table = get_table()

    _store_pipeline_results(
        table, user_id, receipt_id, main_raw, main_result, main_type,
        shadow_raw, shadow_result, shadow_type, now,
    )

    failure_reason = None
    if status == "failed":
        main_error = main_raw.get("error", "unknown")
        shadow_error = shadow_raw.get("error", "unknown")
        failure_reason = (
            f"Both pipelines failed. Main ({main_type}): {main_error}. "
            f"Shadow ({shadow_type}): {shadow_error}."
        )

    _update_receipt(
        table, user_id, receipt_id, selected_result, status,
        used_fallback, ranking_winner, failure_reason, now,
    )

    if selected_result is not None:
        _create_line_items(table, user_id, receipt_id, selected_result, now)

    # Update S3 object metadata
    _update_s3_metadata(bucket, key, receipt_id, status, now)

    # Emit receipt status metrics
    _emit_receipt_metrics(status, used_fallback)

    logger.info(
        "Finalize completed",
        extra={
            "receipt_id": receipt_id,
            "status": status,
            "used_fallback": used_fallback,
            "ranking_winner": ranking_winner,
            "selected_pipeline": selected_type,
        },
    )

    return {
        "receiptId": receipt_id,
        "status": status,
        "usedFallback": used_fallback,
        "rankingWinner": ranking_winner,
        "selectedPipeline": selected_type,
    }


def _get_pipeline_types() -> tuple[str, str]:
    """Return (main_type, shadow_type) based on DEFAULT_PIPELINE config."""
    if DEFAULT_PIPELINE == PIPELINE_AI_MULTIMODAL:
        return PIPELINE_AI_MULTIMODAL, PIPELINE_OCR_AI
    return PIPELINE_OCR_AI, PIPELINE_AI_MULTIMODAL


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


def _select_result(
    main_result: ExtractionResult | None,
    main_type: str,
    shadow_result: ExtractionResult | None,
    shadow_type: str,
) -> tuple[ExtractionResult | None, str | None, bool, str]:
    """Apply main/shadow selection logic.

    Returns:
        (selected_result, selected_type, used_fallback, status)
    """
    if main_result is not None:
        return main_result, main_type, False, "confirmed"

    if shadow_result is not None:
        logger.info(
            "Main pipeline failed, using shadow fallback",
            extra={"main_type": main_type, "shadow_type": shadow_type},
        )
        return shadow_result, shadow_type, True, "confirmed"

    logger.error("Both pipelines failed — receipt marked as failed")
    return None, None, False, "failed"


@tracer.capture_method
def _rank_and_get_winner(
    main_result: ExtractionResult | None,
    shadow_result: ExtractionResult | None,
    main_type: str,
    shadow_type: str,
) -> str | None:
    """Rank both results and return the winner pipeline type.

    Returns None if neither result is available for ranking.
    """
    main_score = rank_results(main_result) if main_result else None
    shadow_score = rank_results(shadow_result) if shadow_result else None

    if main_score is not None and shadow_score is not None:
        winner = main_type if main_score >= shadow_score else shadow_type
        delta = abs(main_score - shadow_score)

        logger.info(
            "Ranking computed",
            extra={
                f"{main_type}_score": main_score,
                f"{shadow_type}_score": shadow_score,
                "winner": winner,
                "delta": delta,
            },
        )

        with single_metric(
            name="RankingDecision",
            unit=MetricUnit.Count,
            value=1,
            namespace="NovaScan",
        ) as metric:
            metric.add_dimension(name="Winner", value=winner)
        with single_metric(
            name="RankingScoreDelta",
            unit=MetricUnit.NoUnit,
            value=delta,
            namespace="NovaScan",
        ) as metric:
            metric.add_dimension(name="Winner", value=winner)

        return winner

    if main_score is not None:
        return main_type
    if shadow_score is not None:
        return shadow_type

    return None


@tracer.capture_method
def _store_pipeline_results(
    table: Any,
    user_id: str,
    receipt_id: str,
    main_raw: dict[str, Any],
    main_result: ExtractionResult | None,
    main_type: str,
    shadow_raw: dict[str, Any],
    shadow_result: ExtractionResult | None,
    shadow_type: str,
    now: str,
) -> None:
    """Store both pipeline results as PIPELINE# entities in DynamoDB."""
    _write_pipeline_record(table, user_id, receipt_id, main_raw, main_result, main_type, now)
    _write_pipeline_record(table, user_id, receipt_id, shadow_raw, shadow_result, shadow_type, now)


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

    item: dict[str, Any] = {
        "PK": f"USER#{user_id}",
        "SK": f"{RECEIPT}#{receipt_id}#{PIPELINE}#{pipeline_type}",
        "entityType": PIPELINE,
        "createdAt": now,
        "modelId": raw.get("modelId", "unknown"),
        "processingTimeMs": raw.get("processingTimeMs", 0),
    }

    if parsed is not None:
        extracted_data = json.loads(parsed.model_dump_json())
        item["extractedData"] = _convert_floats_to_decimal(extracted_data)
        item["confidence"] = Decimal(str(parsed.confidence))

    if ranking_score is not None:
        item["rankingScore"] = Decimal(str(ranking_score))

    if "error" in raw:
        item["error"] = raw["error"]
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

    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
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

        s3_client.copy_object(
            Bucket=bucket,
            Key=key,
            CopySource={"Bucket": bucket, "Key": key},
            MetadataDirective="REPLACE",
            ContentType=content_type,
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
    main_raw: dict[str, Any],
    main_type: str,
    shadow_raw: dict[str, Any],
    shadow_type: str,
) -> None:
    """Publish PipelineCompleted and PipelineLatency metrics.

    Uses single_metric context manager to emit each metric with its own
    isolated dimensions, avoiding dimension overwrite across loop iterations.
    """
    for raw, pipeline_type in [(main_raw, main_type), (shadow_raw, shadow_type)]:
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


def _emit_receipt_metrics(status: str, used_fallback: bool) -> None:
    """Publish ReceiptStatus and UsedFallback metrics.

    Uses single_metric context manager to isolate dimensions from other
    metric emissions in the same Lambda invocation.
    """
    with single_metric(
        name="ReceiptStatus",
        unit=MetricUnit.Count,
        value=1,
        namespace="NovaScan",
    ) as metric:
        metric.add_dimension(name="Status", value=status)

    if used_fallback:
        with single_metric(
            name="UsedFallback",
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
