"""GET /api/dashboard/summary — dashboard summary metrics."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from novascan.shared.dynamo import get_table

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_FETCH_ITEMS = 10_000  # Safety cap to prevent Lambda OOM (SECURITY-REVIEW S5)


class TopCategory(BaseModel):
    """A single category in the top-categories breakdown."""

    category: str
    categoryDisplay: str
    total: float
    percent: float


class RecentActivityItem(BaseModel):
    """A single receipt in the recent-activity list."""

    receiptId: str
    merchant: str | None = None
    total: float | None = None
    category: str | None = None
    categoryDisplay: str | None = None
    receiptDate: str | None = None
    status: str


class DashboardSummaryResponse(BaseModel):
    """GET /api/dashboard/summary response."""

    month: str
    totalSpent: float
    previousMonthTotal: float
    monthlyChangePercent: float | None = None
    weeklySpent: float
    previousWeekTotal: float
    weeklyChangePercent: float | None = None
    receiptCount: int
    confirmedCount: int
    processingCount: int
    failedCount: int
    topCategories: list[TopCategory]
    recentActivity: list[RecentActivityItem]


def _query_all_gsi1(table: Any, user_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Query all receipts from GSI1 within a date range, paginating through all pages.

    Capped at _MAX_FETCH_ITEMS to prevent Lambda OOM (SECURITY-REVIEW S5).
    """
    items: list[dict[str, Any]] = []
    key_cond = Key("GSI1PK").eq(f"USER#{user_id}") & Key("GSI1SK").between(start_date, f"{end_date}~")

    query_kwargs: dict[str, Any] = {
        "IndexName": "GSI1",
        "KeyConditionExpression": key_cond,
        "ScanIndexForward": False,
    }

    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        if len(items) >= _MAX_FETCH_ITEMS:
            logger.warning("Safety cap reached in _query_all_gsi1", extra={"cap": _MAX_FETCH_ITEMS})
            break
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    return items


def _to_float(val: Any) -> float:
    """Convert a DynamoDB value (Decimal or other) to float."""
    if isinstance(val, Decimal):
        return float(val)
    if val is None:
        return 0.0
    return float(val)


def _monday_of_week(d: date) -> date:
    """Return the Monday of the week containing date d (Monday-Sunday week)."""
    return d - timedelta(days=d.weekday())


def _compute_change_percent(current: float, previous: float) -> float | None:
    """Compute percentage change. Returns None if no previous data."""
    if previous == 0.0:
        return None
    return round((current - previous) / previous * 100, 1)


@router.get("/api/dashboard/summary")
@tracer.capture_method
def dashboard_summary() -> Response[Any]:
    """Return dashboard summary metrics for the authenticated user.

    Queries GSI1 for the target month and previous month, then
    aggregates totals, categories, and recent activity using plain Python.
    """
    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    params: dict[str, str] = router.current_event.query_string_parameters or {}

    # Parse and validate month parameter
    month_param = params.get("month")
    today = datetime.now(UTC).date()

    if month_param:
        if not _MONTH_RE.match(month_param):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps(
                    {"error": {"code": "VALIDATION_ERROR", "message": "month must be in YYYY-MM format"}}
                ),
            )
        target_year, target_month_num = int(month_param[:4]), int(month_param[5:7])
    else:
        target_year, target_month_num = today.year, today.month
        month_param = f"{target_year:04d}-{target_month_num:02d}"

    # Calculate date ranges for target month and previous month
    target_month_start = f"{target_year:04d}-{target_month_num:02d}-01"
    if target_month_num == 12:
        next_month_start = f"{target_year + 1:04d}-01-01"
        prev_year, prev_month_num = target_year, 11
    else:
        next_month_start = f"{target_year:04d}-{target_month_num + 1:02d}-01"
        if target_month_num == 1:
            prev_year, prev_month_num = target_year - 1, 12
        else:
            prev_year, prev_month_num = target_year, target_month_num - 1

    prev_month_start = f"{prev_year:04d}-{prev_month_num:02d}-01"

    # Query receipts for both months in one range (prev month start to target month end)
    # The end date is the day before the next month starts
    target_month_end_date = date.fromisoformat(next_month_start) - timedelta(days=1)
    target_month_end = target_month_end_date.isoformat()

    table = get_table()
    all_items = _query_all_gsi1(table, user_id, prev_month_start, target_month_end)

    # Split items into target month and previous month
    target_items: list[dict[str, Any]] = []
    prev_items: list[dict[str, Any]] = []

    for item in all_items:
        receipt_date = str(item.get("receiptDate", ""))
        if receipt_date >= target_month_start and receipt_date <= target_month_end:
            target_items.append(item)
        elif receipt_date >= prev_month_start and receipt_date < target_month_start:
            prev_items.append(item)

    # Receipt counts (all statuses in target month)
    confirmed_count = 0
    processing_count = 0
    failed_count = 0
    for item in target_items:
        status = str(item.get("status", ""))
        if status == "confirmed":
            confirmed_count += 1
        elif status == "processing":
            processing_count += 1
        elif status == "failed":
            failed_count += 1
    receipt_count = confirmed_count + processing_count + failed_count

    # Monthly totals (only confirmed receipts)
    total_spent = 0.0
    category_totals: dict[str, float] = defaultdict(float)
    category_displays: dict[str, str] = {}

    for item in target_items:
        if str(item.get("status", "")) != "confirmed":
            continue
        amount = _to_float(item.get("total"))
        total_spent += amount

        cat = str(item.get("category", "")) if item.get("category") else None
        if cat:
            category_totals[cat] += amount
            if cat not in category_displays and item.get("categoryDisplay"):
                category_displays[cat] = str(item["categoryDisplay"])

    total_spent = round(total_spent, 2)

    # Previous month total (only confirmed)
    previous_month_total = 0.0
    for item in prev_items:
        if str(item.get("status", "")) != "confirmed":
            continue
        previous_month_total += _to_float(item.get("total"))
    previous_month_total = round(previous_month_total, 2)

    monthly_change_percent = _compute_change_percent(total_spent, previous_month_total)

    # Weekly totals (current calendar week Monday-Sunday, always based on today)
    current_monday = _monday_of_week(today)
    current_sunday = current_monday + timedelta(days=6)
    prev_monday = current_monday - timedelta(days=7)
    prev_sunday = current_monday - timedelta(days=1)

    current_week_start = current_monday.isoformat()
    current_week_end = current_sunday.isoformat()
    prev_week_start = prev_monday.isoformat()
    prev_week_end = prev_sunday.isoformat()

    # Query weekly data separately since it may not overlap with the month range
    weekly_items = _query_all_gsi1(table, user_id, prev_week_start, current_week_end)

    weekly_spent = 0.0
    previous_week_total = 0.0

    for item in weekly_items:
        if str(item.get("status", "")) != "confirmed":
            continue
        receipt_date = str(item.get("receiptDate", ""))
        amount = _to_float(item.get("total"))
        if current_week_start <= receipt_date <= current_week_end:
            weekly_spent += amount
        elif prev_week_start <= receipt_date <= prev_week_end:
            previous_week_total += amount

    weekly_spent = round(weekly_spent, 2)
    previous_week_total = round(previous_week_total, 2)
    weekly_change_percent = _compute_change_percent(weekly_spent, previous_week_total)

    # Top categories (up to 5, sorted by total descending, from target month confirmed)
    top_categories: list[TopCategory] = []
    if total_spent > 0:
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        for cat_slug, cat_total in sorted_cats:
            top_categories.append(
                TopCategory(
                    category=cat_slug,
                    categoryDisplay=category_displays.get(cat_slug, cat_slug),
                    total=round(cat_total, 2),
                    percent=round(cat_total / total_spent * 100, 1),
                )
            )

    # Recent activity (up to 5 most recent receipts from target month)
    # target_items are already sorted by GSI1SK descending (ScanIndexForward=False)
    recent_activity: list[RecentActivityItem] = []
    for item in target_items[:5]:
        total_val = item.get("total")
        recent_activity.append(
            RecentActivityItem(
                receiptId=str(item["receiptId"]),
                merchant=str(item["merchant"]) if item.get("merchant") else None,
                total=_to_float(total_val) if total_val is not None else None,
                category=str(item["category"]) if item.get("category") else None,
                categoryDisplay=str(item["categoryDisplay"]) if item.get("categoryDisplay") else None,
                receiptDate=str(item["receiptDate"]) if item.get("receiptDate") else None,
                status=str(item.get("status", "")),
            )
        )

    result = DashboardSummaryResponse(
        month=month_param,
        totalSpent=total_spent,
        previousMonthTotal=previous_month_total,
        monthlyChangePercent=monthly_change_percent,
        weeklySpent=weekly_spent,
        previousWeekTotal=previous_week_total,
        weeklyChangePercent=weekly_change_percent,
        receiptCount=receipt_count,
        confirmedCount=confirmed_count,
        processingCount=processing_count,
        failedCount=failed_count,
        topCategories=top_categories,
        recentActivity=recent_activity,
    )

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=result.model_dump_json(),
    )
