"""GET /api/receipts — list receipts with pagination and filters."""

from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Attr, ConditionBase, Key

from models.receipt import ReceiptListItem, ReceiptListResponse
from shared.dynamo import get_table

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]
s3_client = boto3.client("s3")


def _encode_cursor(last_key: dict[str, Any]) -> str:
    """Base64-encode DynamoDB LastEvaluatedKey as opaque pagination cursor."""
    return base64.urlsafe_b64encode(json.dumps(last_key).encode()).decode()


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode opaque pagination cursor back to DynamoDB ExclusiveStartKey."""
    return json.loads(base64.urlsafe_b64decode(cursor))  # type: ignore[no-any-return]


@router.get("/api/receipts")
@tracer.capture_method
def list_receipts() -> Response[Any]:
    """List receipts for the authenticated user with filtering and pagination.

    Queries GSI1 (USER#{userId}) sorted by date descending.
    Supports status, category, date range filters, and cursor-based pagination.
    """
    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    params: dict[str, str] = router.current_event.query_string_parameters or {}

    status_filter = params.get("status")
    category_filter = params.get("category")
    start_date = params.get("startDate")
    end_date = params.get("endDate")
    cursor = params.get("cursor")

    try:
        limit = min(max(int(params.get("limit", "50")), 1), 100)
    except (ValueError, TypeError):
        limit = 50

    table = get_table()
    bucket = os.environ["RECEIPTS_BUCKET"]
    # Key condition on GSI1
    key_cond: ConditionBase = Key("GSI1PK").eq(f"USER#{user_id}")
    if start_date and end_date:
        key_cond = key_cond & Key("GSI1SK").between(start_date, f"{end_date}~")
    elif start_date:
        key_cond = key_cond & Key("GSI1SK").gte(start_date)
    elif end_date:
        key_cond = key_cond & Key("GSI1SK").lte(f"{end_date}~")

    # Optional filter expression for post-query filtering
    filter_expr: ConditionBase | None = None
    if status_filter:
        filter_expr = Attr("status").eq(status_filter)
    if category_filter:
        cat_expr: ConditionBase = Attr("category").eq(category_filter)
        filter_expr = (filter_expr & cat_expr) if filter_expr else cat_expr

    query_kwargs: dict[str, Any] = {
        "IndexName": "GSI1",
        "KeyConditionExpression": key_cond,
        "ScanIndexForward": False,
        "Limit": limit,
    }
    if filter_expr:
        query_kwargs["FilterExpression"] = filter_expr
    if cursor:
        try:
            query_kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)
        except Exception as e:
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": {"code": "VALIDATION_ERROR", "message": f"Invalid cursor: {e}"}}),
            )

    response = table.query(**query_kwargs)
    items: list[dict[str, Any]] = response.get("Items", [])
    last_key = response.get("LastEvaluatedKey")

    # Build receipt list with presigned GET URLs for images
    receipts: list[ReceiptListItem] = []
    for item in items:
        image_key = str(item.get("imageKey", ""))
        image_url = None
        if image_key:
            image_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": image_key},
                ExpiresIn=3600,
            )

        total = item.get("total")
        if isinstance(total, Decimal):
            total = float(total)

        receipts.append(
            ReceiptListItem(
                receiptId=str(item["receiptId"]),
                receiptDate=str(item["receiptDate"]) if item.get("receiptDate") else None,
                merchant=str(item["merchant"]) if item.get("merchant") else None,
                total=float(total) if total is not None else None,
                category=str(item["category"]) if item.get("category") else None,
                subcategory=str(item["subcategory"]) if item.get("subcategory") else None,
                categoryDisplay=str(item["categoryDisplay"]) if item.get("categoryDisplay") else None,
                subcategoryDisplay=str(item["subcategoryDisplay"]) if item.get("subcategoryDisplay") else None,
                status=str(item["status"]),  # type: ignore[arg-type]
                imageUrl=image_url,
                createdAt=str(item["createdAt"]),
            )
        )

    next_cursor = _encode_cursor(last_key) if last_key else None
    result = ReceiptListResponse(receipts=receipts, nextCursor=next_cursor)

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=result.model_dump_json(),
    )
