"""GET /api/transactions — flattened ledger-style view of receipt data."""

from __future__ import annotations

import json
import re
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Attr, ConditionBase, Key

from novascan.shared.constants import get_category_display_name, get_subcategory_display_name
from novascan.shared.dynamo import get_table
from novascan.shared.pagination import decode_cursor, encode_cursor
from novascan.shared.responses import error_response

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]

_VALID_SORT_BY = {"date", "amount", "merchant"}
_VALID_SORT_ORDER = {"asc", "desc"}
_VALID_STATUS = {"processing", "confirmed", "failed"}
_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _decimal_to_float(val: Any) -> float | None:
    """Convert numeric value to float, return None for None/missing."""
    if val is None:
        return None
    return float(val)


def _build_transaction(item: dict[str, Any]) -> dict[str, Any]:
    """Build a transaction dict from a DynamoDB receipt item."""
    category = item.get("category")
    subcategory = item.get("subcategory")

    return {
        "receiptId": str(item["receiptId"]),
        "receiptDate": str(item["receiptDate"]) if item.get("receiptDate") else None,
        "merchant": str(item["merchant"]) if item.get("merchant") else None,
        "total": _decimal_to_float(item.get("total")),
        "category": str(category) if category else None,
        "categoryDisplay": (
            str(item["categoryDisplay"])
            if item.get("categoryDisplay")
            else get_category_display_name(str(category)) if category else None
        ),
        "subcategory": str(subcategory) if subcategory else None,
        "subcategoryDisplay": (
            str(item["subcategoryDisplay"])
            if item.get("subcategoryDisplay")
            else get_subcategory_display_name(str(subcategory)) if subcategory else None
        ),
        "status": str(item["status"]),
    }


def _apply_post_query_filters(
    items: list[dict[str, Any]],
    *,
    merchant_search: str | None,
) -> list[dict[str, Any]]:
    """Apply filters that cannot be expressed as DynamoDB FilterExpression.

    Merchant search uses case-insensitive substring match in Lambda.
    """
    if not merchant_search:
        return items

    merchant_lower = merchant_search.lower()
    return [
        item
        for item in items
        if item.get("merchant") and merchant_lower in str(item["merchant"]).lower()
    ]


def _fetch_all_matching(
    table: Any,
    query_kwargs: dict[str, Any],
    *,
    merchant_search: str | None,
) -> list[dict[str, Any]]:
    """Fetch all matching records from DynamoDB (paginate through all pages).

    Used when sortBy=amount|merchant requires in-memory sorting of all results.
    Also applies merchant search filter.

    # TODO(post-MVP): Add safety cap per SECURITY-REVIEW S5 to prevent Lambda OOM
    """
    all_items: list[dict[str, Any]] = []
    # Remove Limit from kwargs for full fetch — we'll apply limit after sorting
    fetch_kwargs = {k: v for k, v in query_kwargs.items() if k != "Limit" and k != "ExclusiveStartKey"}

    while True:
        response = table.query(**fetch_kwargs)
        items = response.get("Items", [])
        all_items.extend(items)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        fetch_kwargs["ExclusiveStartKey"] = last_key

    return _apply_post_query_filters(all_items, merchant_search=merchant_search)


@router.get("/api/transactions")
@tracer.capture_method
def list_transactions() -> Response[Any]:
    """List transactions — a flattened, ledger-style view of receipt data.

    Queries GSI1 (USER#{userId}) sorted by date.
    Supports filters: startDate, endDate, category, merchant, status.
    Supports sorting: date (native GSI1), amount, merchant (in-memory).
    Cursor-based pagination using DynamoDB ExclusiveStartKey/LastEvaluatedKey.
    Returns totalCount via parallel Count query or derived from fetched set.
    """
    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    params: dict[str, str] = router.current_event.query_string_parameters or {}

    start_date = params.get("startDate")
    end_date = params.get("endDate")
    category_filter = params.get("category")
    merchant_search = params.get("merchant")
    status_filter = params.get("status")
    sort_by = params.get("sortBy", "date")
    sort_order = params.get("sortOrder", "desc")
    cursor = params.get("cursor")

    # Validate enum parameters
    if sort_by not in _VALID_SORT_BY:
        return error_response(
            400, "VALIDATION_ERROR", f"sortBy must be one of: {', '.join(sorted(_VALID_SORT_BY))}"
        )
    if sort_order not in _VALID_SORT_ORDER:
        return error_response(
            400, "VALIDATION_ERROR", f"sortOrder must be one of: {', '.join(sorted(_VALID_SORT_ORDER))}"
        )
    if status_filter and status_filter not in _VALID_STATUS:
        return error_response(
            400, "VALIDATION_ERROR", f"status must be one of: {', '.join(sorted(_VALID_STATUS))}"
        )
    if start_date and not _DATE_RE.match(start_date):
        return error_response(400, "VALIDATION_ERROR", "startDate must be in YYYY-MM-DD format")
    if end_date and not _DATE_RE.match(end_date):
        return error_response(400, "VALIDATION_ERROR", "endDate must be in YYYY-MM-DD format")
    if start_date and end_date and start_date > end_date:
        return error_response(400, "VALIDATION_ERROR", "startDate must not be after endDate")

    try:
        limit = min(max(int(params.get("limit", "50")), 1), 100)
    except (ValueError, TypeError):
        limit = 50

    table = get_table()

    # Key condition on GSI1
    key_cond: ConditionBase = Key("GSI1PK").eq(f"USER#{user_id}")
    if start_date and end_date:
        key_cond = key_cond & Key("GSI1SK").between(start_date, f"{end_date}~")
    elif start_date:
        key_cond = key_cond & Key("GSI1SK").gte(start_date)
    elif end_date:
        key_cond = key_cond & Key("GSI1SK").lte(f"{end_date}~")

    # DynamoDB FilterExpression for status and category (post-query)
    filter_expr: ConditionBase | None = None
    if status_filter:
        filter_expr = Attr("status").eq(status_filter)
    if category_filter:
        cat_expr: ConditionBase = Attr("category").eq(category_filter)
        filter_expr = (filter_expr & cat_expr) if filter_expr else cat_expr

    query_kwargs: dict[str, Any] = {
        "IndexName": "GSI1",
        "KeyConditionExpression": key_cond,
        "ScanIndexForward": sort_order == "asc" if sort_by == "date" else False,
    }
    if filter_expr:
        query_kwargs["FilterExpression"] = filter_expr

    # Branching logic based on sortBy
    if sort_by == "date" and not merchant_search:
        # Native GSI1 sort without merchant search — use DynamoDB pagination directly
        query_kwargs["Limit"] = limit

        if cursor:
            try:
                query_kwargs["ExclusiveStartKey"] = decode_cursor(cursor, user_id=user_id)
            except Exception as e:
                logger.warning(
                    "Invalid pagination cursor",
                    extra={"error": str(e), "user_id": user_id},
                )
                return error_response(400, "VALIDATION_ERROR", "Invalid pagination cursor")

        # Run data query
        response = table.query(**query_kwargs)
        items: list[dict[str, Any]] = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")

        # Build transactions
        transactions = [_build_transaction(item) for item in items]
        next_cursor = encode_cursor(last_key) if last_key else None

        # Parallel Count query for totalCount
        count_kwargs: dict[str, Any] = {
            "IndexName": "GSI1",
            "KeyConditionExpression": key_cond,
            "Select": "COUNT",
        }
        if filter_expr:
            count_kwargs["FilterExpression"] = filter_expr

        total_count = 0
        while True:
            count_response = table.query(**count_kwargs)
            total_count += count_response.get("Count", 0)
            count_last_key = count_response.get("LastEvaluatedKey")
            if not count_last_key:
                break
            count_kwargs["ExclusiveStartKey"] = count_last_key

    else:
        # sortBy=amount|merchant, or sortBy=date with merchant search — fetch all, paginate in memory
        all_items = _fetch_all_matching(
            table, query_kwargs, merchant_search=merchant_search
        )
        total_count = len(all_items)

        # Sort in-memory
        reverse = sort_order == "desc"
        if sort_by == "amount":
            all_items.sort(
                key=lambda x: float(x["total"]) if x.get("total") is not None else float("-inf"),
                reverse=reverse,
            )
        elif sort_by == "merchant":
            # Sort None/missing merchants to end regardless of direction
            no_merchant = "\uffff" if not reverse else ""
            all_items.sort(
                key=lambda x: (
                    str(x.get("merchant", "")).lower() if x.get("merchant") else no_merchant
                ),
                reverse=reverse,
            )

        # Cursor-based pagination for in-memory sorted results
        start_idx = 0
        if cursor:
            try:
                decoded = decode_cursor(cursor, user_id=user_id)
                cursor_gsi1sk = decoded.get("GSI1SK", "")
                cursor_pk = decoded.get("PK", "")
                cursor_sk = decoded.get("SK", "")
                for i, item in enumerate(all_items):
                    if (
                        item.get("GSI1SK") == cursor_gsi1sk
                        and item.get("PK") == cursor_pk
                        and item.get("SK") == cursor_sk
                    ):
                        start_idx = i + 1
                        break
            except Exception as e:
                logger.warning(
                    "Invalid pagination cursor",
                    extra={"error": str(e), "user_id": user_id},
                )
                return error_response(400, "VALIDATION_ERROR", "Invalid pagination cursor")

        page = all_items[start_idx : start_idx + limit]
        transactions = [_build_transaction(item) for item in page]

        if start_idx + limit < len(all_items):
            last_item = page[-1] if page else None
            if last_item:
                next_cursor = encode_cursor({
                    "GSI1PK": f"USER#{user_id}",
                    "GSI1SK": last_item.get("GSI1SK", ""),
                    "PK": last_item.get("PK", ""),
                    "SK": last_item.get("SK", ""),
                })
            else:
                next_cursor = None
        else:
            next_cursor = None

    result = {
        "transactions": transactions,
        "nextCursor": next_cursor,
        "totalCount": total_count,
    }

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(result),
    )
