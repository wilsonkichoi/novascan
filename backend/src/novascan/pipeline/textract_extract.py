"""Textract Extract Lambda — calls AnalyzeExpense (sync) on a receipt image.

Receives S3 bucket/key from Step Functions, invokes Textract AnalyzeExpense
in synchronous mode, and returns the raw ExpenseDocuments output.

Errors are caught and returned as error payloads (not raised) so Step Functions
Catch blocks can route them.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from novascan.pipeline.validation import validate_event_fields, validate_s3_key

logger = Logger()
tracer = Tracer()

textract_client = boto3.client("textract")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Extract expense data from a receipt image using Textract.

    Expected event shape:
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg"
        }

    Returns:
        {
            "expenseDocuments": [...],  # Raw Textract ExpenseDocuments
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg"
        }

    On error:
        {
            "error": "textract_extract_failed",
            "errorType": "ExceptionClassName"
        }
    """
    # H6 — Event validation: fail fast on missing required fields
    validation_error = validate_event_fields(event, ["bucket", "key"])
    if validation_error:
        logger.warning("Invalid event payload", extra={"missing_fields": validation_error})
        return {"error": "invalid_event", "errorType": "ValidationError"}

    bucket = event["bucket"]
    key = event["key"]

    # H5 — S3 key validation: regex + bucket match
    expected_bucket = os.environ.get("RECEIPTS_BUCKET", "")
    if not validate_s3_key(key, bucket, expected_bucket):
        logger.warning("Invalid S3 key or bucket mismatch", extra={"key_present": bool(key)})
        return {"error": "invalid_event", "errorType": "ValidationError"}

    logger.info("Starting Textract AnalyzeExpense", extra={"key_present": True})

    try:
        response = _call_textract(bucket, key)

        expense_documents = response.get("ExpenseDocuments", [])
        logger.info(
            "Textract AnalyzeExpense completed",
            extra={"document_count": len(expense_documents)},
        )

        return {
            "expenseDocuments": expense_documents,
            "bucket": bucket,
            "key": key,
        }

    except Exception as e:
        # H4 — Error sanitization: no str(e) in return payload
        logger.exception("Textract AnalyzeExpense failed")
        return {
            "error": "textract_extract_failed",
            "errorType": type(e).__name__,
        }


@tracer.capture_method
def _call_textract(bucket: str, key: str) -> dict[str, Any]:
    """Call Textract AnalyzeExpense synchronously."""
    return textract_client.analyze_expense(
        Document={
            "S3Object": {
                "Bucket": bucket,
                "Name": key,
            }
        }
    )
