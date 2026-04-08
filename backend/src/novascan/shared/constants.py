"""Entity type constants and category taxonomy for DynamoDB single-table design.

These match the entityType attribute stored on each DynamoDB item.
See SPEC.md Section 7 (Data Model) for the full schema.
Category taxonomy matches category-taxonomy.md exactly.
"""

PROFILE = "PROFILE"
RECEIPT = "RECEIPT"
ITEM = "ITEM"
PIPELINE = "PIPELINE"
CUSTOMCAT = "CUSTOMCAT"

# Predefined category taxonomy from category-taxonomy.md.
# Structure: {slug: {"displayName": str, "subcategories": {slug: displayName}}}
PREDEFINED_CATEGORIES: dict[str, dict[str, str | dict[str, str]]] = {
    "groceries-food": {
        "displayName": "Groceries & Food",
        "subcategories": {
            "supermarket-grocery": "Supermarket / Grocery",
            "produce": "Produce",
            "meat-seafood": "Meat & Seafood",
            "breads-bakery": "Breads & Bakery",
            "deli-prepared-food": "Deli & Prepared Food",
            "dairy-cheese-eggs": "Dairy, Cheese & Eggs",
            "frozen-food": "Frozen Food",
            "snacks": "Snacks",
            "pantry": "Pantry",
            "beverages": "Beverages",
            "specialty-food-beverage": "Specialty Food & Beverage",
            "convenience-store": "Convenience Store",
            "farmers-market-bakery": "Farmers Market / Bakery",
        },
    },
    "dining": {
        "displayName": "Dining",
        "subcategories": {
            "fast-food-quick-service": "Fast Food / Quick Service",
            "restaurant-dine-in": "Restaurant / Dine-In",
            "delivery-takeout": "Delivery & Takeout",
            "coffee-cafe": "Coffee & Cafe",
            "bar-nightlife": "Bar & Nightlife",
        },
    },
    "retail-shopping": {
        "displayName": "Retail & Shopping",
        "subcategories": {
            "electronics-technology": "Electronics & Technology",
            "clothing-apparel": "Clothing & Apparel",
            "arts-crafts-hobbies": "Arts, Crafts & Hobbies",
            "home-garden": "Home & Garden",
            "general-merchandise-discount": "General Merchandise / Discount",
            "sporting-goods": "Sporting Goods",
            "books-media": "Books & Media",
        },
    },
    "automotive-transit": {
        "displayName": "Automotive & Transit",
        "subcategories": {
            "fuel-ev-charging": "Fuel & EV Charging",
            "auto-maintenance-service": "Auto Maintenance & Service",
            "rideshare-public-transit": "Rideshare & Public Transit",
            "parking-tolls": "Parking & Tolls",
            "auto-parts-accessories": "Auto Parts & Accessories",
        },
    },
    "health-wellness": {
        "displayName": "Health & Wellness",
        "subcategories": {
            "pharmacy": "Pharmacy",
            "personal-care": "Personal Care",
            "medical-dental": "Medical & Dental",
            "vision-optical": "Vision & Optical",
            "fitness-gym": "Fitness & Gym",
        },
    },
    "entertainment-travel": {
        "displayName": "Entertainment & Travel",
        "subcategories": {
            "event-tickets-shows": "Event Tickets & Shows",
            "lodging-hotels": "Lodging & Hotels",
            "flights-travel-services": "Flights & Travel Services",
            "attractions-activities": "Attractions & Activities",
        },
    },
    "home-utilities": {
        "displayName": "Home & Utilities",
        "subcategories": {
            "utilities-electric-gas-water": "Utilities (Electric, Gas, Water)",
            "internet-phone": "Internet & Phone",
            "home-maintenance-repair": "Home Maintenance & Repair",
            "cleaning-laundry": "Cleaning & Laundry",
        },
    },
    "education": {
        "displayName": "Education",
        "subcategories": {
            "courses-tuition": "Courses & Tuition",
            "books-supplies": "Books & Supplies",
            "professional-development": "Professional Development",
        },
    },
    "pets": {
        "displayName": "Pets",
        "subcategories": {
            "veterinary": "Veterinary",
            "pet-food-supplies": "Pet Food & Supplies",
            "grooming-boarding": "Grooming & Boarding",
        },
    },
    "gifts-donations": {
        "displayName": "Gifts & Donations",
        "subcategories": {
            "gifts": "Gifts",
            "charitable-donations": "Charitable Donations",
        },
    },
    "financial-insurance": {
        "displayName": "Financial & Insurance",
        "subcategories": {
            "bank-service-fees": "Bank & Service Fees",
            "insurance-premiums": "Insurance Premiums",
        },
    },
    "office-business": {
        "displayName": "Office & Business",
        "subcategories": {
            "office-supplies": "Office Supplies",
            "postage-shipping": "Postage & Shipping",
            "subscriptions-saas": "Subscriptions & SaaS",
            "printing-copying": "Printing & Copying",
        },
    },
    "other": {
        "displayName": "Other",
        "subcategories": {
            "uncategorized": "Uncategorized",
        },
    },
}


def get_all_category_slugs() -> set[str]:
    """Return the set of all predefined category slugs."""
    return set(PREDEFINED_CATEGORIES.keys())


def get_all_subcategory_slugs() -> set[str]:
    """Return the set of all predefined subcategory slugs across all categories."""
    slugs: set[str] = set()
    for cat_data in PREDEFINED_CATEGORIES.values():
        subcats = cat_data.get("subcategories", {})
        if isinstance(subcats, dict):
            slugs.update(subcats.keys())
    return slugs


def get_subcategory_slugs_for_category(category_slug: str) -> set[str]:
    """Return subcategory slugs for a specific category, or empty set if not found."""
    cat_data = PREDEFINED_CATEGORIES.get(category_slug)
    if not cat_data:
        return set()
    subcats = cat_data.get("subcategories", {})
    if isinstance(subcats, dict):
        return set(subcats.keys())
    return set()


def get_category_display_name(slug: str) -> str | None:
    """Return display name for a category slug, or None if not found."""
    cat_data = PREDEFINED_CATEGORIES.get(slug)
    if cat_data:
        display = cat_data.get("displayName")
        return str(display) if display else None
    return None


def get_subcategory_display_name(subcategory_slug: str) -> str | None:
    """Return display name for a subcategory slug, or None if not found."""
    for cat_data in PREDEFINED_CATEGORIES.values():
        subcats = cat_data.get("subcategories", {})
        if isinstance(subcats, dict) and subcategory_slug in subcats:
            return subcats[subcategory_slug]
    return None
