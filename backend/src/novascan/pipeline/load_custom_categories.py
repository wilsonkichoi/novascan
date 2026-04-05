"""LoadCustomCategories Lambda — queries user's custom categories from DynamoDB.

Step Functions invokes this Lambda before the parallel pipeline branches.
It fetches the user's CUSTOMCAT# entities and returns them so the pipeline
Lambdas can include them in the extraction prompt alongside the predefined
taxonomy.

This is a lightweight pre-step (~5-10ms) that runs once per receipt.
"""

from __future__ import annotations

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

    Expected event shape (from Step Functions):
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",
            "receiptId": "01ABC..."
        }

    Returns the original event fields plus customCategories:
        {
            "bucket": "my-bucket",
            "key": "receipts/abc123.jpg",
            "userId": "us-east-1:xxx",
            "receiptId": "01ABC...",
            "customCategories": [
                {"slug": "costco", "displayName": "Costco", "parentCategory": "groceries-food"},
                ...
            ]
        }
    """
    user_id = event.get("userId", "")
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
