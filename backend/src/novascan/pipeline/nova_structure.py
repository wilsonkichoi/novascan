"""Nova Structure Lambda — sends Textract output to Bedrock Nova for structured extraction.

Receives Textract ExpenseDocuments output, the S3 image reference, predefined
taxonomy, and optional custom categories from Step Functions. Constructs a
Bedrock prompt, calls invoke_model with Nova, and parses the response into
an ExtractionResult JSON.

Errors are caught and returned as error payloads (not raised) so Step Functions
Catch blocks can route them.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from novascan.models.extraction import ExtractionResult
from novascan.pipeline.prompts import build_extraction_prompt
from novascan.pipeline.validation import (
    check_image_size,
    validate_event_fields,
    validate_model_id,
    validate_s3_key,
)

logger = Logger()
tracer = Tracer()

bedrock_client = boto3.client("bedrock-runtime")
s3_client = boto3.client("s3")

MODEL_ID = os.environ.get("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")

# M8 — Model ID validation at module load
if not validate_model_id(MODEL_ID):
    logger.error("Invalid MODEL_ID", extra={"model_id": MODEL_ID})
    raise RuntimeError(f"NOVA_MODEL_ID '{MODEL_ID}' is not in the allowed model list")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Structure Textract output into ExtractionResult using Bedrock Nova.

    Expected event shape:
        {
            "textractResult": {
                "expenseDocuments": [...],
                "bucket": "my-bucket",
                "key": "receipts/abc123.jpg"
            },
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "customCategories": [
                {"slug": "costco", "displayName": "Costco", "parentCategory": "groceries-food"}
            ]
        }

    Returns:
        {
            "extractionResult": { ... ExtractionResult fields ... },
            "modelId": "amazon.nova-lite-v1:0",
            "processingTimeMs": 1234
        }

    On error:
        {
            "error": "error message",
            "errorType": "ExceptionClassName"
        }
    """
    # H6 — Event validation: fail fast on missing required fields
    validation_error = validate_event_fields(event, ["bucket", "key", "textractResult"])
    if validation_error:
        logger.warning("Invalid event payload", extra={"missing_fields": validation_error})
        return {"error": "invalid_event", "errorType": "ValidationError"}

    try:
        textract_result = event["textractResult"]
        bucket = event.get("bucket", textract_result.get("bucket", ""))
        key = event.get("key", textract_result.get("key", ""))
        custom_categories = event.get("customCategories")

        # H5 — S3 key validation: regex + bucket match
        expected_bucket = os.environ.get("RECEIPTS_BUCKET", "")
        if not validate_s3_key(key, bucket, expected_bucket):
            logger.warning("Invalid S3 key or bucket mismatch", extra={"key_present": bool(key)})
            return {"error": "invalid_event", "errorType": "ValidationError"}

        expense_documents = textract_result.get("expenseDocuments", [])

        logger.info(
            "Starting Nova structuring",
            extra={
                "expense_document_count": len(expense_documents),
                "custom_category_count": len(custom_categories) if custom_categories else 0,
                "model_id": MODEL_ID,
            },
        )

        textract_text = _format_textract_output(expense_documents)

        prompt = build_extraction_prompt(
            custom_categories=custom_categories,
            textract_output=textract_text,
        )

        image_bytes = _read_image_from_s3(bucket, key)
        media_type = _infer_media_type(key)

        start_time = time.time()
        raw_response = _call_bedrock(prompt, image_bytes, media_type)
        processing_time_ms = int((time.time() - start_time) * 1000)

        extraction_result = _parse_response(raw_response)

        logger.info(
            "Nova structuring completed",
            extra={
                "processing_time_ms": processing_time_ms,
                "confidence": extraction_result.confidence,
                "category": extraction_result.category,
                "line_item_count": len(extraction_result.lineItems),
            },
        )

        return {
            "extractionResult": json.loads(extraction_result.model_dump_json()),
            "modelId": MODEL_ID,
            "processingTimeMs": processing_time_ms,
        }

    except Exception as e:
        # H4 — Error sanitization: no str(e) in return payload
        logger.exception("Nova structuring failed")
        return {
            "error": "nova_structure_failed",
            "errorType": type(e).__name__,
        }


@tracer.capture_method
def _format_textract_output(expense_documents: list[dict[str, Any]]) -> str:
    """Convert Textract ExpenseDocuments into a readable text summary.

    Extracts summary fields and line item groups from the Textract response
    into a structured text format that Nova can reason over.
    """
    lines: list[str] = []

    for doc_idx, doc in enumerate(expense_documents):
        lines.append(f"--- Expense Document {doc_idx + 1} ---")

        # Summary fields (merchant name, date, total, etc.)
        summary_fields = doc.get("SummaryFields", [])
        if summary_fields:
            lines.append("Summary Fields:")
            for field in summary_fields:
                field_type = field.get("Type", {}).get("Text", "UNKNOWN")
                value = field.get("ValueDetection", {}).get("Text", "")
                confidence = field.get("ValueDetection", {}).get("Confidence", 0)
                lines.append(f"  {field_type}: {value} (confidence: {confidence:.1f}%)")

        # Line item groups
        line_item_groups = doc.get("LineItemGroups", [])
        for group_idx, group in enumerate(line_item_groups):
            lines.append(f"Line Items (Group {group_idx + 1}):")
            for item in group.get("LineItems", []):
                item_fields = item.get("LineItemExpenseFields", [])
                item_parts: list[str] = []
                for item_field in item_fields:
                    field_type = item_field.get("Type", {}).get("Text", "")
                    value = item_field.get("ValueDetection", {}).get("Text", "")
                    if value:
                        item_parts.append(f"{field_type}={value}")
                if item_parts:
                    lines.append(f"  - {', '.join(item_parts)}")

    return "\n".join(lines) if lines else "No expense data found in Textract output."


@tracer.capture_method
def _read_image_from_s3(bucket: str, key: str) -> bytes:
    """Read the receipt image from S3.

    L5 — Checks ContentLength before reading to guard against oversized images.
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content_length = response.get("ContentLength", 0)
    check_image_size(content_length)
    return response["Body"].read()


def _infer_media_type(key: str) -> str:
    """Infer MIME type from the S3 key extension."""
    lower_key = key.lower()
    if lower_key.endswith(".png"):
        return "image/png"
    if lower_key.endswith(".jpg") or lower_key.endswith(".jpeg"):
        return "image/jpeg"
    # Default to JPEG for receipt images
    return "image/jpeg"


@tracer.capture_method
def _call_bedrock(prompt: str, image_bytes: bytes, media_type: str) -> str:
    """Call Bedrock Nova with the extraction prompt and receipt image."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": media_type.split("/")[1],
                            "source": {
                                "bytes": image_b64,
                            },
                        },
                    },
                    {
                        "text": prompt,
                    },
                ],
            },
        ],
        "inferenceConfig": {
            "maxNewTokens": 4096,
            "temperature": 0.1,
        },
    })

    response = bedrock_client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    response_body = json.loads(response["body"].read())
    output_text = response_body["output"]["message"]["content"][0]["text"]
    return output_text


@tracer.capture_method
def _parse_response(raw_response: str) -> ExtractionResult:
    """Parse the raw Bedrock response into an ExtractionResult.

    Handles cases where the model wraps JSON in markdown code blocks.
    """
    text = raw_response.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        # Remove closing fence
        if text.endswith("```"):
            text = text[: -3].strip()

    data = json.loads(text)
    return ExtractionResult.model_validate(data)
