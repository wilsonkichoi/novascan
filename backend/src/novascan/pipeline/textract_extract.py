"""Textract Extract Lambda — calls AnalyzeExpense (sync) on a receipt image.

Receives S3 bucket/key from Step Functions, invokes Textract AnalyzeExpense
in synchronous mode, and returns the raw ExpenseDocuments output.

Errors are caught and returned as error payloads (not raised) so Step Functions
Catch blocks can route them.
"""

from __future__ import annotations

from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

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
            "error": "error message",
            "errorType": "ExceptionClassName"
        }
    """
    bucket = event.get("bucket", "")
    key = event.get("key", "")

    logger.info("Starting Textract AnalyzeExpense", extra={"bucket": bucket, "key": key})

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
        logger.exception("Textract AnalyzeExpense failed", extra={"bucket": bucket, "key": key})
        return {
            "error": str(e),
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
