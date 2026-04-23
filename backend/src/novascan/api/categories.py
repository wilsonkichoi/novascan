"""Category and pipeline results API endpoints.

GET /api/categories — list predefined + custom categories
POST /api/categories — create custom category
DELETE /api/categories/{slug} — delete custom category
GET /api/receipts/{id}/pipeline-results — both pipeline outputs (staff only)
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from boto3.dynamodb.conditions import Key
from pydantic import ValidationError

from novascan.models.category import (
    Category,
    CustomCategoryRequest,
    CustomCategoryResponse,
    Subcategory,
)
from novascan.shared.constants import (
    CUSTOMCAT,
    PIPELINE,
    PREDEFINED_CATEGORIES,
    RECEIPT,
    get_all_category_slugs,
)
from novascan.shared.dynamo import get_table
from novascan.shared.responses import error_response

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]

# Crockford Base32 charset used by ULID: 0-9 A-H J K M N P-T V-Z (excludes I L O U)
_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# Slugs produced by _slugify are lowercase alphanumeric with hyphens
_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,100}$")


def _get_user_id() -> str:
    """Extract user ID from JWT sub claim."""
    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    return user_id


def _get_user_groups() -> list[str]:
    """Extract user groups from JWT cognito:groups claim.

    Returns empty list if claim is missing.
    API Gateway HTTP API JWT authorizer stringifies array claims,
    so ["admin", "user"] arrives as "[admin, user]".
    """
    claims = router.current_event.request_context.authorizer.jwt_claim  # type: ignore[attr-defined]
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        stripped = groups.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inner = stripped[1:-1]
            sep = "," if "," in inner else " "
            return [g.strip() for g in inner.split(sep) if g.strip()]
        return [stripped] if stripped else []
    if isinstance(groups, list):
        return [str(g) for g in groups]
    return []


def _slugify(display_name: str) -> str:
    """Generate a URL-safe slug from a display name.

    Lowercased, spaces become hyphens, special chars removed.
    """
    slug = display_name.lower().strip()
    # Replace spaces with hyphens
    slug = re.sub(r"\s+", "-", slug)
    # Remove anything that isn't alphanumeric or hyphen
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def _validate_receipt_id(receipt_id: str) -> Response[Any] | None:
    """Validate receipt_id is a valid ULID format. Returns error response if invalid, None if valid."""
    if not _ULID_PATTERN.match(receipt_id):
        return error_response(400, "VALIDATION_ERROR", "Invalid receipt ID format")
    return None


@router.get("/api/categories")
@tracer.capture_method
def list_categories() -> Response[Any]:
    """List all categories: predefined taxonomy merged with user's custom categories.

    Predefined categories returned first, then custom categories.
    """
    user_id = _get_user_id()
    table = get_table()

    # Build predefined categories
    categories: list[Category] = []
    for slug, cat_data in PREDEFINED_CATEGORIES.items():
        display_name = str(cat_data["displayName"])
        subcats_raw = cat_data.get("subcategories", {})
        subcategories = []
        if isinstance(subcats_raw, dict):
            subcategories = [
                Subcategory(slug=sub_slug, displayName=sub_display)
                for sub_slug, sub_display in subcats_raw.items()
            ]
        categories.append(
            Category(
                slug=slug,
                displayName=display_name,
                isCustom=False,
                subcategories=subcategories,
            )
        )

    # Query user's custom categories: PK = USER#{userId}, SK begins_with CUSTOMCAT#
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
        & Key("SK").begins_with(f"{CUSTOMCAT}#"),
    )
    custom_items: list[dict[str, Any]] = response.get("Items", [])

    for item in custom_items:
        sk = str(item.get("SK", ""))
        # Extract slug from SK: CUSTOMCAT#{slug}
        slug = sk.removeprefix(f"{CUSTOMCAT}#")
        categories.append(
            Category(
                slug=slug,
                displayName=str(item.get("displayName", slug)),
                isCustom=True,
                parentCategory=str(item["parentCategory"]) if item.get("parentCategory") else None,
                subcategories=[],
            )
        )

    result = {"categories": [cat.model_dump() for cat in categories]}
    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(result),
    )


@router.post("/api/categories")
@tracer.capture_method
def create_category() -> Response[Any]:
    """Create a custom category.

    Auto-generates slug from displayName. Validates parentCategory against
    predefined category slugs. Returns 409 on duplicate slug.
    """
    user_id = _get_user_id()

    try:
        body = router.current_event.json_body or {}
        request = CustomCategoryRequest(**body)
    except ValidationError as e:
        logger.warning("Category validation failed", extra={"error_count": e.error_count()})
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
        logger.warning("Category request parse error", extra={"error_type": type(e).__name__})
        return error_response(400, "VALIDATION_ERROR", "Invalid request body")

    # Validate parentCategory against predefined slugs
    if request.parentCategory is not None:
        predefined_slugs = get_all_category_slugs()
        if request.parentCategory not in predefined_slugs:
            return error_response(
                400,
                "VALIDATION_ERROR",
                f"parentCategory '{request.parentCategory}' is not a valid predefined category slug",
            )

    # Auto-generate slug from displayName
    slug = _slugify(request.displayName)
    if not slug:
        return error_response(400, "VALIDATION_ERROR", "Display name produces an empty slug")

    # Check for conflict with predefined category slugs
    predefined_slugs = get_all_category_slugs()
    if slug in predefined_slugs:
        return error_response(
            409,
            "CONFLICT",
            f"Category slug '{slug}' conflicts with a predefined category",
        )

    # Check for conflict with existing custom category for this user
    table = get_table()
    pk = f"USER#{user_id}"
    sk = f"{CUSTOMCAT}#{slug}"

    existing = table.get_item(Key={"PK": pk, "SK": sk})
    if existing.get("Item"):
        return error_response(
            409,
            "CONFLICT",
            f"Custom category with slug '{slug}' already exists",
        )

    # Create the custom category record
    item: dict[str, Any] = {
        "PK": pk,
        "SK": sk,
        "entityType": CUSTOMCAT,
        "displayName": request.displayName,
        "slug": slug,
        "createdAt": datetime.now(UTC).isoformat(),
    }
    if request.parentCategory is not None:
        item["parentCategory"] = request.parentCategory

    table.put_item(Item=item)

    result = CustomCategoryResponse(
        slug=slug,
        displayName=request.displayName,
        parentCategory=request.parentCategory,
        isCustom=True,
    )
    return Response(
        status_code=201,
        content_type=content_types.APPLICATION_JSON,
        body=result.model_dump_json(),
    )


@router.delete("/api/categories/<slug>")
@tracer.capture_method
def delete_category(slug: str) -> Response[Any]:
    """Delete a custom category. Predefined categories cannot be deleted."""
    if not _SLUG_PATTERN.match(slug):
        return error_response(400, "VALIDATION_ERROR", "Invalid category slug format")

    user_id = _get_user_id()

    # Check if this is a predefined category
    predefined_slugs = get_all_category_slugs()
    if slug in predefined_slugs:
        return error_response(
            403,
            "FORBIDDEN",
            "Cannot delete predefined categories",
        )

    table = get_table()
    pk = f"USER#{user_id}"
    sk = f"{CUSTOMCAT}#{slug}"

    # Check if the custom category exists
    existing = table.get_item(Key={"PK": pk, "SK": sk})
    if not existing.get("Item"):
        return error_response(404, "NOT_FOUND", f"Custom category '{slug}' not found")

    # Delete it
    table.delete_item(Key={"PK": pk, "SK": sk})

    return Response(
        status_code=204,
        content_type=content_types.APPLICATION_JSON,
        body="",
    )


@router.get("/api/receipts/<receipt_id>/pipeline-results")
@tracer.capture_method
def get_pipeline_results(receipt_id: str) -> Response[Any]:
    """Get extraction results from both pipeline paths.

    Requires staff role. Returns 403 for non-staff users.
    """
    if err := _validate_receipt_id(receipt_id):
        return err

    user_id = _get_user_id()
    table = get_table()
    pk = f"USER#{user_id}"

    # First check if the receipt exists
    receipt_sk = f"{RECEIPT}#{receipt_id}"
    receipt_response = table.get_item(Key={"PK": pk, "SK": receipt_sk})
    receipt_item = receipt_response.get("Item")
    if not receipt_item:
        return error_response(404, "NOT_FOUND", "Receipt not found")

    # Query pipeline results: SK begins_with RECEIPT#{ulid}#PIPELINE#
    pipeline_response = table.query(
        KeyConditionExpression=Key("PK").eq(pk)
        & Key("SK").begins_with(f"{RECEIPT}#{receipt_id}#{PIPELINE}#"),
    )
    pipeline_items: list[dict[str, Any]] = pipeline_response.get("Items", [])

    # Build results map keyed by pipeline type (ocr-ai, ai-multimodal)
    results: dict[str, Any] = {}
    for item in pipeline_items:
        sk = str(item.get("SK", ""))
        # Extract pipeline type from SK: RECEIPT#{ulid}#PIPELINE#{type}
        parts = sk.split(f"#{PIPELINE}#")
        if len(parts) == 2:
            pipeline_type = parts[1]
        else:
            continue

        pipeline_data: dict[str, Any] = {}

        # extractedData
        extracted = item.get("extractedData")
        if extracted is not None:
            pipeline_data["extractedData"] = _convert_decimal(extracted)
        else:
            pipeline_data["extractedData"] = None

        # confidence
        confidence = item.get("confidence")
        pipeline_data["confidence"] = float(confidence) if confidence is not None else None

        # rankingScore
        ranking_score = item.get("rankingScore")
        pipeline_data["rankingScore"] = float(ranking_score) if ranking_score is not None else None

        # processingTimeMs
        pipeline_data["processingTimeMs"] = int(item.get("processingTimeMs", 0))

        # modelId
        pipeline_data["modelId"] = str(item.get("modelId", "unknown"))

        # createdAt
        pipeline_data["createdAt"] = str(item.get("createdAt", ""))

        # Cost tracking fields
        pipeline_data["inputTokens"] = int(item.get("inputTokens", 0))
        pipeline_data["outputTokens"] = int(item.get("outputTokens", 0))
        pipeline_data["textractPages"] = int(item.get("textractPages", 0))
        cost_usd = item.get("costUsd")
        pipeline_data["costUsd"] = float(cost_usd) if cost_usd is not None else None

        results[pipeline_type] = pipeline_data

    response_body = {
        "receiptId": receipt_id,
        "usedFallback": receipt_item.get("usedFallback", False),
        "rankingWinner": receipt_item.get("rankingWinner"),
        "results": results,
    }

    return Response(
        status_code=200,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps(response_body, default=_json_default),
    )


def _convert_decimal(obj: Any) -> Any:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimal(item) for item in obj]
    return obj


def _json_default(obj: Any) -> Any:
    """JSON serializer fallback for non-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
