"""Structured JSON extraction prompt templates for Bedrock Nova.

The prompt template embeds the full category taxonomy, user custom categories,
and extraction instructions. Output must conform to the ExtractionResult schema
defined in models/extraction.py (SPEC Section 7).

Security: Custom category names and slugs are validated before interpolation
into the prompt to prevent prompt injection attacks (SECURITY-REVIEW C1).
"""

import json
import re

CATEGORY_TAXONOMY = """\
## Predefined Categories

### Groceries & Food (groceries-food)
Subcategories: supermarket-grocery, produce, meat-seafood, breads-bakery, \
deli-prepared-food, dairy-cheese-eggs, frozen-food, snacks, pantry, beverages, \
specialty-food-beverage, convenience-store, farmers-market-bakery

### Dining (dining)
Subcategories: fast-food-quick-service, restaurant-dine-in, delivery-takeout, \
coffee-cafe, bar-nightlife

### Retail & Shopping (retail-shopping)
Subcategories: electronics-technology, clothing-apparel, arts-crafts-hobbies, \
home-garden, general-merchandise-discount, sporting-goods, books-media

### Automotive & Transit (automotive-transit)
Subcategories: fuel-ev-charging, auto-maintenance-service, \
rideshare-public-transit, parking-tolls, auto-parts-accessories

### Health & Wellness (health-wellness)
Subcategories: pharmacy, personal-care, medical-dental, vision-optical, \
fitness-gym

### Entertainment & Travel (entertainment-travel)
Subcategories: event-tickets-shows, lodging-hotels, flights-travel-services, \
attractions-activities

### Home & Utilities (home-utilities)
Subcategories: utilities-electric-gas-water, internet-phone, \
home-maintenance-repair, cleaning-laundry

### Education (education)
Subcategories: courses-tuition, books-supplies, professional-development

### Pets (pets)
Subcategories: veterinary, pet-food-supplies, grooming-boarding

### Gifts & Donations (gifts-donations)
Subcategories: gifts, charitable-donations

### Financial & Insurance (financial-insurance)
Subcategories: bank-service-fees, insurance-premiums

### Office & Business (office-business)
Subcategories: office-supplies, postage-shipping, subscriptions-saas, \
printing-copying

### Other (other)
Subcategories: uncategorized
"""

EXTRACTION_SCHEMA = """\
{
  "merchant": {
    "name": "string (required)",
    "address": "string or null",
    "phone": "string or null"
  },
  "receiptDate": "YYYY-MM-DD or null",
  "currency": "USD",
  "lineItems": [
    {
      "name": "string (required)",
      "quantity": "number (default 1.0)",
      "unitPrice": "number (default 0.00)",
      "totalPrice": "number (default 0.00)",
      "subcategory": "string slug or null"
    }
  ],
  "subtotal": "number (default 0.00)",
  "tax": "number (default 0.00)",
  "tip": "number or null",
  "total": "number (default 0.00)",
  "category": "string (predefined category slug)",
  "subcategory": "string (predefined subcategory slug)",
  "paymentMethod": "string or null",
  "confidence": "number 0.0-1.0"
}
"""

EXTRACTION_INSTRUCTIONS = """\
You are a receipt data extraction assistant. Extract structured data from the \
receipt and return ONLY valid JSON matching the schema below. No markdown, no \
explanation, no extra text.

## Output Schema

{schema}

## Category Taxonomy

Assign a category and subcategory from the taxonomy below. Use the slug values \
(in parentheses) for category and subcategory fields.

{taxonomy}

{custom_categories_section}

## Assignment Rules

1. Infer the category from merchant name and line items (e.g., "Whole Foods" \
-> groceries-food, "Shell" -> automotive-transit > fuel-ev-charging).
2. If the user has custom categories, prefer them when they are a more specific \
match than predefined ones (e.g., if user has "costco" and receipt is from \
Costco, assign "costco" instead of generic "groceries-food").
3. Default to category "other" / subcategory "uncategorized" when confidence \
is below 0.5.
4. For grocery receipts from general supermarkets: assign "supermarket-grocery" \
as the receipt subcategory and tag each line item with the appropriate product \
subcategory (e.g., "Chicken Breast" -> meat-seafood, "Milk" -> dairy-cheese-eggs).
5. For non-grocery receipts: set every line item subcategory to null. \
Do NOT assign a category slug as a subcategory.
6. All monetary values must be decimal numbers (e.g., 5.99 not 599).
7. receiptDate is the date printed on the receipt, not today's date. Use \
YYYY-MM-DD format. Set null if unreadable.
8. confidence is your overall confidence in the extraction accuracy (0.0-1.0).
9. Each printed product line on the receipt is a SEPARATE line item. On grocery \
receipts, multi-quantity items often use a two-line format: the item name and \
total price on one line, then "N @ $X.XX" (quantity x unit price) indented on \
the line below. Do NOT merge adjacent items into one. Parse each product line \
independently.
10. Verify that the number of line items you extract matches the item count \
printed on the receipt (if shown). If the sum of line item totals does not \
match the subtotal, re-examine the receipt for missed items.
"""


# --- Validation patterns (SECURITY-REVIEW C1) ---

# Category display names: alphanumeric, spaces, & / , . ( ) -
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9 &/,.()\-]+$")

# Category slugs: lowercase alphanumeric + hyphens
_VALID_SLUG_RE = re.compile(r"^[a-z0-9\-]+$")

# Injection patterns: newlines, markdown headers, instruction-like content
_INJECTION_PATTERNS = [
    re.compile(r"[\n\r]"),                     # newlines
    re.compile(r"#{2,}"),                       # markdown headers (##, ###, etc.)
    re.compile(r"(?i)ignore\s+(previous|above|all)\s+instructions?"),
    re.compile(r"(?i)you\s+are\s+(now|a)\b"),
    re.compile(r"(?i)system\s*:"),
    re.compile(r"(?i)assistant\s*:"),
    re.compile(r"(?i)human\s*:"),
]

_MAX_CATEGORY_LENGTH = 64


def validate_category_name(name: str) -> str:
    """Validate a custom category display name.

    Raises:
        ValueError: If the name fails validation.

    Returns:
        The validated name (unchanged).
    """
    if not name or len(name) > _MAX_CATEGORY_LENGTH:
        raise ValueError(
            f"Category name must be 1-{_MAX_CATEGORY_LENGTH} characters, "
            f"got {len(name) if name else 0}"
        )
    if not _VALID_NAME_RE.match(name):
        raise ValueError(
            f"Category name contains invalid characters: {name!r}"
        )
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(name):
            raise ValueError(
                f"Category name contains disallowed pattern: {name!r}"
            )
    return name


def validate_category_slug(slug: str) -> str:
    """Validate a custom category slug.

    Raises:
        ValueError: If the slug fails validation.

    Returns:
        The validated slug (unchanged).
    """
    if not slug or len(slug) > _MAX_CATEGORY_LENGTH:
        raise ValueError(
            f"Category slug must be 1-{_MAX_CATEGORY_LENGTH} characters, "
            f"got {len(slug) if slug else 0}"
        )
    if not _VALID_SLUG_RE.match(slug):
        raise ValueError(
            f"Category slug contains invalid characters: {slug!r}"
        )
    return slug


def build_extraction_prompt(
    *,
    custom_categories: list[dict[str, str]] | None = None,
    textract_output: str | None = None,
) -> str:
    """Build the full extraction prompt with taxonomy and instructions.

    Args:
        custom_categories: List of user custom categories, each with
            "slug", "displayName", and optional "parentCategory" keys.
        textract_output: Raw Textract output text to include in the prompt.
            If None, the prompt is for direct image extraction (multimodal).

    Returns:
        Complete prompt string ready for Bedrock Nova.

    Raises:
        ValueError: If any custom category name or slug fails validation.
    """
    if custom_categories:
        # Validate all categories before building the prompt (C1 mitigation)
        sanitized_cats = []
        for cat in custom_categories:
            validate_category_name(cat["displayName"])
            validate_category_slug(cat["slug"])
            if cat.get("parentCategory"):
                validate_category_slug(cat["parentCategory"])
            sanitized_cats.append({
                "slug": cat["slug"],
                "displayName": cat["displayName"],
                **({"parentCategory": cat["parentCategory"]}
                   if cat.get("parentCategory") else {}),
            })
        # Place custom categories in structured JSON data block to prevent
        # prompt injection via free-text interpolation (C1 mitigation)
        custom_section = (
            "## Custom Categories (user-defined, prefer when specific match)\n\n"
            "The following JSON array contains user-defined categories. "
            "Use them when they are a more specific match than predefined ones.\n\n"
            "```json\n"
            f"{json.dumps(sanitized_cats, indent=2)}\n"
            "```"
        )
    else:
        custom_section = "No custom categories defined."

    prompt = EXTRACTION_INSTRUCTIONS.format(
        schema=EXTRACTION_SCHEMA,
        taxonomy=CATEGORY_TAXONOMY,
        custom_categories_section=custom_section,
    )

    if textract_output:
        prompt += (
            "\n## Textract OCR Output\n\n"
            "Use the following Textract AnalyzeExpense output as the primary "
            "data source. Cross-reference with the receipt image if provided.\n\n"
            f"{textract_output}\n"
        )
    else:
        prompt += (
            "\n## Instructions\n\n"
            "Extract all receipt data from the provided image. "
            "Return ONLY the JSON object.\n"
        )

    return prompt
