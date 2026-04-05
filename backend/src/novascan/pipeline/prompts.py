"""Structured JSON extraction prompt templates for Bedrock Nova.

The prompt template embeds the full category taxonomy, user custom categories,
and extraction instructions. Output must conform to the ExtractionResult schema
defined in models/extraction.py (SPEC Section 7).
"""

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
5. For non-grocery receipts: line-item subcategory is optional (null).
6. All monetary values must be decimal numbers (e.g., 5.99 not 599).
7. receiptDate is the date printed on the receipt, not today's date. Use \
YYYY-MM-DD format. Set null if unreadable.
8. confidence is your overall confidence in the extraction accuracy (0.0-1.0).
"""


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
    """
    if custom_categories:
        lines = ["## Custom Categories (user-defined, prefer when specific match)"]
        for cat in custom_categories:
            parent = cat.get("parentCategory")
            parent_str = f" (under {parent})" if parent else ""
            lines.append(f"- {cat['displayName']} ({cat['slug']}){parent_str}")
        custom_section = "\n".join(lines)
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
