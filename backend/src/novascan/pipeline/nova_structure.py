"""Nova Structure Lambda — categorizes and normalizes Textract OCR output.

Receives Textract ExpenseDocuments output and optional custom categories from
Step Functions. Constructs a text-only Bedrock prompt with Textract's structured
OCR data, calls invoke_model with Nova for categorization and normalization,
and parses the response into an ExtractionResult JSON.

Errors are caught and returned as error payloads (not raised) so Step Functions
Catch blocks can route them.
"""

from __future__ import annotations

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
    validate_event_fields,
    validate_model_id,
    validate_s3_key,
)

logger = Logger()
tracer = Tracer()

bedrock_client = boto3.client("bedrock-runtime")

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
        textract_pages = textract_result.get("textractPages", 0)

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

        start_time = time.time()
        raw_response, input_tokens, output_tokens = _call_bedrock(prompt)
        processing_time_ms = int((time.time() - start_time) * 1000)

        extraction_result = _parse_response(raw_response)

        logger.info(
            "Nova structuring completed",
            extra={
                "processing_time_ms": processing_time_ms,
                "confidence": extraction_result.confidence,
                "category": extraction_result.category,
                "line_item_count": len(extraction_result.lineItems),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )

        return {
            "extractionResult": json.loads(extraction_result.model_dump_json()),
            "modelId": MODEL_ID,
            "processingTimeMs": processing_time_ms,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "textractPages": textract_pages,
        }

    except Exception as e:
        # H4 — Error sanitization: no str(e) in return payload
        logger.exception("Nova structuring failed")
        return {
            "error": "nova_structure_failed",
            "errorType": type(e).__name__,
        }


@tracer.capture_method(capture_response=False)
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


@tracer.capture_method(capture_response=False)
def _call_bedrock(prompt: str) -> tuple[str, int, int]:
    """Call Bedrock Nova with Textract text only (no image)."""
    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt,
                    },
                ],
            },
        ],
        "inferenceConfig": {
            "maxTokens": 4096,
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
    output_text: str = response_body["output"]["message"]["content"][0]["text"]
    usage = response_body.get("usage", {})
    return output_text, usage.get("inputTokens", 0), usage.get("outputTokens", 0)


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
