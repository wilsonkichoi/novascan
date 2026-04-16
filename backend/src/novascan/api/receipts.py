"""Receipt API endpoints — list, get, update, delete, and line item management."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from pydantic import ValidationError

from novascan.models.receipt import (
    LineItemsUpdateRequest,
    ReceiptDetail,
    ReceiptDetailLineItem,
    ReceiptListItem,
    ReceiptListResponse,
    ReceiptUpdateRequest,
)
from novascan.shared.constants import (
    ITEM,
    get_all_category_slugs,
    get_category_display_name,
    get_subcategory_display_name,
    get_subcategory_slugs_for_category,
)
from novascan.shared.dynamo import get_table
from novascan.shared.pagination import decode_cursor, encode_cursor
from novascan.shared.responses import error_response

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]
s3_client = boto3.client("s3")


def _decimal_to_float(val: Any) -> float | None:
    """Convert numeric value to float, return None for None/missing."""
    if val is None:
        return None
    return float(val)


def _get_user_id() -> str:
    """Extract user ID from JWT sub claim."""
    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    return user_id


# Crockford Base32 charset used by ULID: 0-9 A-H J K M N P-T V-Z (excludes I L O U)
_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _validate_receipt_id(receipt_id: str) -> Response[Any] | None:
    """Validate receipt_id is a valid ULID format. Returns error response if invalid, None if valid."""
    if not _ULID_PATTERN.match(receipt_id):
        return error_response(400, "VALIDATION_ERROR", "Invalid receipt ID format")
    return None


def _generate_image_url(image_key: str, bucket: str) -> str | None:
    """Generate a presigned GET URL for a receipt image."""
    if not image_key:
        return None
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": image_key},
        ExpiresIn=3600,
    )


def _build_receipt_detail(
    receipt_item: dict[str, Any],
    line_items: list[dict[str, Any]],
    image_url: str | None,
) -> ReceiptDetail:
    """Build a ReceiptDetail from DynamoDB items."""
    sorted_items = sorted(line_items, key=lambda x: x.get("SK", ""))
    detail_items = []
    for idx, item in enumerate(sorted_items, start=1):
        subcat = item.get("subcategory")
        raw_qty = _decimal_to_float(item.get("quantity"))
        raw_unit = _decimal_to_float(item.get("unitPrice"))
        raw_total = _decimal_to_float(item.get("totalPrice"))
        detail_items.append(
            ReceiptDetailLineItem(
                sortOrder=int(item.get("sortOrder", idx)),
                name=str(item.get("name", "")),
                quantity=raw_qty if raw_qty is not None else 1.0,
                unitPrice=raw_unit if raw_unit is not None else 0.0,
                totalPrice=raw_total if raw_total is not None else 0.0,
                subcategory=str(subcat) if subcat else None,
                subcategoryDisplay=get_subcategory_display_name(str(subcat)) if subcat else None,
            )
        )

    category = receipt_item.get("category")
    subcategory = receipt_item.get("subcategory")

    return ReceiptDetail(
        receiptId=str(receipt_item["receiptId"]),
        receiptDate=str(receipt_item["receiptDate"]) if receipt_item.get("receiptDate") else None,
        merchant=str(receipt_item["merchant"]) if receipt_item.get("merchant") else None,
        merchantAddress=str(receipt_item["merchantAddress"]) if receipt_item.get("merchantAddress") else None,
        total=_decimal_to_float(receipt_item.get("total")),
        subtotal=_decimal_to_float(receipt_item.get("subtotal")),
        tax=_decimal_to_float(receipt_item.get("tax")),
        tip=_decimal_to_float(receipt_item.get("tip")),
        category=str(category) if category else None,
        categoryDisplay=get_category_display_name(str(category)) if category else None,
        subcategory=str(subcategory) if subcategory else None,
        subcategoryDisplay=get_subcategory_display_name(str(subcategory)) if subcategory else None,
        status=str(receipt_item["status"]),  # type: ignore[arg-type]
        usedFallback=receipt_item.get("usedFallback"),
        rankingWinner=receipt_item.get("rankingWinner"),
        imageUrl=image_url,
        paymentMethod=str(receipt_item["paymentMethod"]) if receipt_item.get("paymentMethod") else None,
        lineItems=detail_items,
        createdAt=str(receipt_item["createdAt"]),
        updatedAt=str(receipt_item["updatedAt"]) if receipt_item.get("updatedAt") else None,
    )


@router.get("/api/receipts")
@tracer.capture_method
def list_receipts() -> Response[Any]:
    """List receipts for the authenticated user with filtering and pagination.

    Queries GSI1 (USER#{userId}) sorted by date descending.
    Supports status, category, date range filters, and cursor-based pagination.
    """
    user_id = _get_user_id()
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
            query_kwargs["ExclusiveStartKey"] = decode_cursor(
                cursor, user_id=user_id
            )
        except Exception as e:
            # Log detailed error server-side, return generic message (M7 mitigation)
            logger.warning(
                "Invalid pagination cursor",
                extra={"error": str(e), "user_id": user_id},
            )
            return error_response(400, "VALIDATION_ERROR", "Invalid pagination cursor")

    response = table.query(**query_kwargs)
    items: list[dict[str, Any]] = response.get("Items", [])
    last_key = response.get("LastEvaluatedKey")

    # Build receipt list with presigned GET URLs for images
    receipts: list[ReceiptListItem] = []
    for item in items:
        image_key = str(item.get("imageKey", ""))
        image_url = _generate_image_url(image_key, bucket)

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

    next_cursor = encode_cursor(last_key) if last_key else None
    result = ReceiptListResponse(receipts=receipts, nextCursor=next_cursor)

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=result.model_dump_json(),
    )


@router.get("/api/receipts/<receipt_id>")
@tracer.capture_method
def get_receipt(receipt_id: str) -> Response[Any]:
    """Get receipt detail including line items."""
    if err := _validate_receipt_id(receipt_id):
        return err
    user_id = _get_user_id()
    table = get_table()
    bucket = os.environ["RECEIPTS_BUCKET"]

    # Query all items under this receipt: receipt + items + pipeline results
    # Access pattern #3: PK = USER#{userId}, SK begins_with RECEIPT#{ulid}
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
        & Key("SK").begins_with(f"RECEIPT#{receipt_id}"),
    )
    items: list[dict[str, Any]] = response.get("Items", [])

    if not items:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    # Separate receipt from line items
    receipt_item: dict[str, Any] | None = None
    line_items: list[dict[str, Any]] = []
    for item in items:
        sk = str(item.get("SK", ""))
        if sk == f"RECEIPT#{receipt_id}":
            receipt_item = item
        elif "#ITEM#" in sk:
            line_items.append(item)

    if receipt_item is None:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    image_key = str(receipt_item.get("imageKey", ""))
    image_url = _generate_image_url(image_key, bucket)

    detail = _build_receipt_detail(receipt_item, line_items, image_url)

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=detail.model_dump_json(),
    )


@router.put("/api/receipts/<receipt_id>")
@tracer.capture_method
def update_receipt(receipt_id: str) -> Response[Any]:
    """Update receipt-level fields. Only provided fields are updated."""
    if err := _validate_receipt_id(receipt_id):
        return err
    user_id = _get_user_id()

    try:
        body = router.current_event.json_body or {}
        request = ReceiptUpdateRequest(**body)
    except ValidationError as e:
        logger.warning("Receipt update validation failed", extra={"error_count": e.error_count()})
        sanitized_errors = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in e.errors()
        ]
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": {"code": "VALIDATION_ERROR", "details": sanitized_errors}}),
        )
    except (TypeError, json.JSONDecodeError) as e:
        logger.warning("Receipt update parse error", extra={"error_type": type(e).__name__})
        return error_response(400, "VALIDATION_ERROR", "Invalid request body")

    # Validate category/subcategory against taxonomy
    update_data = request.model_dump(exclude_none=True)
    if "category" in update_data:
        cat_slug = update_data["category"]
        all_cat_slugs = get_all_category_slugs()
        if cat_slug not in all_cat_slugs:
            # Could be a custom category -- we'll allow it since we can't check
            # custom categories without a DB query. The finalize lambda and
            # categories API handle custom slug validation.
            pass

    if "subcategory" in update_data and "category" in update_data:
        cat_slug = update_data["category"]
        subcat_slug = update_data["subcategory"]
        # Empty string means "clear subcategory" — skip validation
        if subcat_slug:
            valid_subcats = get_subcategory_slugs_for_category(cat_slug)
            if valid_subcats and subcat_slug not in valid_subcats:
                return error_response(
                    400,
                    "VALIDATION_ERROR",
                    f"Subcategory '{subcat_slug}' is not valid for category '{cat_slug}'",
                )

    if not update_data:
        # No fields to update -- still return the current receipt
        return get_receipt(receipt_id)

    table = get_table()
    pk = f"USER#{user_id}"
    sk = f"RECEIPT#{receipt_id}"
    now_iso = datetime.now(UTC).isoformat()

    # Build UpdateExpression dynamically
    update_parts: list[str] = []
    expr_names: dict[str, str] = {}
    expr_values: dict[str, Any] = {}
    monetary_fields = {"total", "subtotal", "tax", "tip"}

    for field_name, value in update_data.items():
        attr_name = f"#{field_name}"
        attr_value = f":{field_name}"
        expr_names[attr_name] = field_name
        if field_name in monetary_fields and value is not None:
            value = Decimal(str(value))
        expr_values[attr_value] = value
        update_parts.append(f"{attr_name} = {attr_value}")

    # Add display names for category/subcategory
    if "category" in update_data:
        cat_display = get_category_display_name(update_data["category"])
        expr_names["#categoryDisplay"] = "categoryDisplay"
        expr_values[":categoryDisplay"] = cat_display
        update_parts.append("#categoryDisplay = :categoryDisplay")

    if "subcategory" in update_data:
        subcat_display = get_subcategory_display_name(update_data["subcategory"])
        expr_names["#subcategoryDisplay"] = "subcategoryDisplay"
        expr_values[":subcategoryDisplay"] = subcat_display
        update_parts.append("#subcategoryDisplay = :subcategoryDisplay")

    # Update GSI1SK if receiptDate changed
    if "receiptDate" in update_data:
        expr_names["#GSI1SK"] = "GSI1SK"
        expr_values[":GSI1SK"] = f"{update_data['receiptDate']}#{receipt_id}"
        update_parts.append("#GSI1SK = :GSI1SK")

    # Always update updatedAt
    expr_names["#updatedAt"] = "updatedAt"
    expr_values[":updatedAt"] = now_iso
    update_parts.append("#updatedAt = :updatedAt")

    update_expr = "SET " + ", ".join(update_parts)

    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression=Attr("PK").exists(),
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    # Return the updated receipt with line items
    return get_receipt(receipt_id)


@router.delete("/api/receipts/<receipt_id>")
@tracer.capture_method
def delete_receipt(receipt_id: str) -> Response[Any]:
    """Hard delete a receipt and all related DynamoDB records + S3 image.

    Access pattern #6: Query PK=USER#{userId}, SK begins_with RECEIPT#{ulid}
    then BatchWriteItem to delete all.
    """
    if err := _validate_receipt_id(receipt_id):
        return err
    user_id = _get_user_id()
    table = get_table()
    bucket = os.environ["RECEIPTS_BUCKET"]
    pk = f"USER#{user_id}"

    # Query all items under this receipt
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk)
        & Key("SK").begins_with(f"RECEIPT#{receipt_id}"),
    )
    items: list[dict[str, Any]] = response.get("Items", [])

    if not items:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    # Find the receipt record (for the image key)
    image_key: str | None = None
    for item in items:
        sk = str(item.get("SK", ""))
        if sk == f"RECEIPT#{receipt_id}":
            image_key = str(item.get("imageKey", "")) or None
            break

    # Delete all DynamoDB records via BatchWriteItem
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Delete S3 image
    if image_key:
        try:
            s3_client.delete_object(Bucket=bucket, Key=image_key)
        except Exception:
            logger.warning(
                "Failed to delete S3 image",
                extra={"image_key": image_key, "receipt_id": receipt_id},
            )

    return Response(
        status_code=204,
        content_type=content_types.APPLICATION_JSON,
        body="",
    )


@router.put("/api/receipts/<receipt_id>/items")
@tracer.capture_method
def update_items(receipt_id: str) -> Response[Any]:
    """Bulk replace all line items for a receipt.

    Deletes existing line items, then inserts the provided list.
    """
    if err := _validate_receipt_id(receipt_id):
        return err
    user_id = _get_user_id()

    try:
        body = router.current_event.json_body or {}
        request = LineItemsUpdateRequest(**body)
    except ValidationError as e:
        logger.warning("Line items validation failed", extra={"error_count": e.error_count()})
        sanitized_errors = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in e.errors()
        ]
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": {"code": "VALIDATION_ERROR", "details": sanitized_errors}}),
        )
    except (TypeError, json.JSONDecodeError) as e:
        logger.warning("Line items parse error", extra={"error_type": type(e).__name__})
        return error_response(400, "VALIDATION_ERROR", "Invalid request body")

    table = get_table()
    pk = f"USER#{user_id}"
    sk = f"RECEIPT#{receipt_id}"

    # Verify the receipt exists
    receipt_response = table.get_item(Key={"PK": pk, "SK": sk})
    receipt_item = receipt_response.get("Item")
    if not receipt_item:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    now_iso = datetime.now(UTC).isoformat()

    # Delete existing line items
    existing_items_response = table.query(
        KeyConditionExpression=Key("PK").eq(pk)
        & Key("SK").begins_with(f"RECEIPT#{receipt_id}#ITEM#"),
    )
    existing_items: list[dict[str, Any]] = existing_items_response.get("Items", [])

    # Delete existing + insert new in a single batch_writer to minimize the
    # window where the receipt has no items (S7: reduce race condition window).
    with table.batch_writer() as batch:
        for item in existing_items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        for line_item in request.items:
            item_sk = f"RECEIPT#{receipt_id}#ITEM#{line_item.sortOrder:03d}"
            batch.put_item(
                Item={
                    "PK": pk,
                    "SK": item_sk,
                    "entityType": ITEM,
                    "receiptId": receipt_id,
                    "sortOrder": line_item.sortOrder,
                    "name": line_item.name,
                    "quantity": Decimal(str(line_item.quantity)),
                    "unitPrice": Decimal(str(line_item.unitPrice)),
                    "totalPrice": Decimal(str(line_item.totalPrice)),
                    **({"subcategory": line_item.subcategory} if line_item.subcategory else {}),
                    "createdAt": now_iso,
                }
            )

    # Recalculate subtotal and total from line items
    subtotal = sum(Decimal(str(item.totalPrice)) for item in request.items)
    # Preserve existing tax/tip — only update subtotal and total
    existing_tax = receipt_item.get("tax") or Decimal("0")
    existing_tip = receipt_item.get("tip") or Decimal("0")
    total = subtotal + existing_tax + existing_tip

    # Update receipt updatedAt + recalculated totals
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET #updatedAt = :updatedAt, #subtotal = :subtotal, #total = :total",
        ExpressionAttributeNames={
            "#updatedAt": "updatedAt",
            "#subtotal": "subtotal",
            "#total": "total",
        },
        ExpressionAttributeValues={
            ":updatedAt": now_iso,
            ":subtotal": subtotal,
            ":total": total,
        },
    )

    # Return the full receipt with new line items
    return get_receipt(receipt_id)
