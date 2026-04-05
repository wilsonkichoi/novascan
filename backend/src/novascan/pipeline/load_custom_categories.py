"""LoadCustomCategories Lambda — queries user's custom categories from DynamoDB.

Step Functions invokes this Lambda before the parallel pipeline branches.
It fetches the user's CUSTOMCAT# entities and returns them so the pipeline
Lambdas can include them in the extraction prompt alongside the predefined
taxonomy.

This is a lightweight pre-step (~5-10ms) that runs once per receipt.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

from novascan.shared.constants import CUSTOMCAT
from novascan.shared.dynamo import get_table

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Load custom categories for a user and pass through pipeline input.

    Accepts two event shapes:

    1. Direct invocation (bucket/key already extracted):
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",   (optional — looked up if missing)
            "receiptId": "01ABC..."       (optional — extracted from key if missing)
        }

    2. S3 -> SQS -> EventBridge Pipes (raw S3 event body as JSON string):
        {
            "s3EventBody": "{\"Records\":[{\"s3\":{\"bucket\":{\"name\":\"...\"},\"object\":{\"key\":\"...\"}}}]}"
        }

    In case 2, the S3 event is parsed to extract bucket and key. In either case,
    receiptId is extracted from the key and userId is looked up from DynamoDB
    if not already present.

    Returns:
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",
            "receiptId": "01ABC...",
            "customCategories": [...]
        }
    """
    # If the event came from EventBridge Pipes with an S3 event body, parse it
    if "s3EventBody" in event and "bucket" not in event:
        event = _parse_s3_event(event)

    key = event.get("key", "")

    # Extract receiptId from S3 key if not provided
    receipt_id = event.get("receiptId", "")
    if not receipt_id and key:
        receipt_id = _extract_receipt_id(key)
        event["receiptId"] = receipt_id

    # Look up userId from DynamoDB if not provided
    user_id = event.get("userId", "")
    if not user_id and receipt_id:
        user_id = _lookup_user_id(receipt_id)
        if not user_id:
            raise ValueError(
                f"Could not resolve userId for receiptId={receipt_id}"
            )
        event["userId"] = user_id

    logger.info("Loading custom categories", extra={"user_id": user_id})

    try:
        custom_categories = _query_custom_categories(user_id)
    except Exception as e:
        logger.exception(
            "Failed to load custom categories",
            extra={"user_id": user_id},
        )
        return {"error": str(e), "errorType": type(e).__name__}

    logger.info(
        "Custom categories loaded",
        extra={"user_id": user_id, "count": len(custom_categories)},
    )

    # Pass through all original event fields plus the custom categories
    return {
        **event,
        "customCategories": custom_categories,
    }


@tracer.capture_method
def _query_custom_categories(user_id: str) -> list[dict[str, Any]]:
    """Query DynamoDB for user's custom category entities.

    Queries PK=USER#{userId} with SK begins_with CUSTOMCAT#.
    Returns a list of dicts with slug, displayName, and optional parentCategory.
    """
    table = get_table()

    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": (
            Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with(f"{CUSTOMCAT}#")
        ),
    }
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    categories: list[dict[str, Any]] = []
    for item in items:
        # SK format is CUSTOMCAT#{slug}
        sk = item.get("SK", "")
        slug = sk.split("#", 1)[1] if "#" in sk else sk

        category: dict[str, Any] = {
            "slug": slug,
            "displayName": item.get("displayName", slug),
        }

        parent = item.get("parentCategory")
        if parent:
            category["parentCategory"] = parent

        categories.append(category)

    return categories


def _parse_s3_event(event: dict[str, Any]) -> dict[str, Any]:
    """Parse S3 event notification from the SQS message body.

    The EventBridge Pipe passes the SQS message body as s3EventBody (a JSON
    string containing the S3 event notification). This function parses it
    and extracts bucket and key from the first S3 record.

    Returns a new event dict with bucket, key, and any other original fields.
    """
    s3_event_body = event.get("s3EventBody", "")

    # s3EventBody may be a string (JSON) or already parsed as a dict
    s3_event = json.loads(s3_event_body) if isinstance(s3_event_body, str) else s3_event_body

    records = s3_event.get("Records", [])
    if not records:
        logger.error("No records in S3 event", extra={"s3_event": s3_event})
        return event

    s3_record = records[0].get("s3", {})
    bucket = s3_record.get("bucket", {}).get("name", "")
    key = urllib.parse.unquote_plus(s3_record.get("object", {}).get("key", ""))

    logger.info("Parsed S3 event", extra={"bucket": bucket, "key": key})

    return {
        "bucket": bucket,
        "key": key,
    }


def _extract_receipt_id(key: str) -> str:
    """Extract receiptId from S3 key.

    Expected format: receipts/{receiptId}.{ext}
    Returns empty string if format doesn't match.
    """
    # Strip prefix
    filename = key.rsplit("/", 1)[-1] if "/" in key else key
    # Strip extension
    receipt_id = filename.rsplit(".", 1)[0] if "." in filename else filename
    return receipt_id


@tracer.capture_method
def _lookup_user_id(receipt_id: str) -> str:
    """Look up the userId that owns a receipt via GSI2 query.

    Uses GSI2 (GSI2PK = receiptId) to find the receipt's PK, from which
    the userId is extracted. This replaces the previous full-table scan
    (SECURITY-REVIEW C2 — cross-user data exposure mitigation).
    """
    table = get_table()

    response = table.query(
        IndexName="GSI2",
        KeyConditionExpression=Key("GSI2PK").eq(receipt_id),
        ProjectionExpression="PK",
        Limit=1,
    )

    items = response.get("Items", [])
    if items:
        pk = items[0].get("PK", "")
        user_id = pk.split("#", 1)[1] if "#" in pk else ""
        logger.info(
            "Looked up userId from receipt via GSI2",
            extra={"receipt_id": receipt_id, "user_id": user_id},
        )
        return user_id

    logger.error("Receipt not found in GSI2", extra={"receipt_id": receipt_id})
    return ""
