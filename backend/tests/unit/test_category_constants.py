"""Tests for predefined category taxonomy constants.

Validates that the category taxonomy in shared/constants.py matches
the spec in category-taxonomy.md:
- All 13 predefined categories present
- Slug format valid (lowercase, hyphens)
- Each category has at least one subcategory
- Helper functions return correct results
"""

from __future__ import annotations

import re

from shared.constants import (
    PREDEFINED_CATEGORIES,
    get_all_category_slugs,
    get_all_subcategory_slugs,
    get_category_display_name,
    get_subcategory_display_name,
    get_subcategory_slugs_for_category,
)

# The 13 predefined categories from category-taxonomy.md
EXPECTED_CATEGORIES = {
    "groceries-food",
    "dining",
    "retail-shopping",
    "automotive-transit",
    "health-wellness",
    "entertainment-travel",
    "home-utilities",
    "education",
    "pets",
    "gifts-donations",
    "financial-insurance",
    "office-business",
    "other",
}

# Expected display names from category-taxonomy.md
EXPECTED_DISPLAY_NAMES = {
    "groceries-food": "Groceries & Food",
    "dining": "Dining",
    "retail-shopping": "Retail & Shopping",
    "automotive-transit": "Automotive & Transit",
    "health-wellness": "Health & Wellness",
    "entertainment-travel": "Entertainment & Travel",
    "home-utilities": "Home & Utilities",
    "education": "Education",
    "pets": "Pets",
    "gifts-donations": "Gifts & Donations",
    "financial-insurance": "Financial & Insurance",
    "office-business": "Office & Business",
    "other": "Other",
}

# Subcategory counts from category-taxonomy.md
EXPECTED_SUBCATEGORY_COUNTS = {
    "groceries-food": 13,
    "dining": 5,
    "retail-shopping": 7,
    "automotive-transit": 5,
    "health-wellness": 5,
    "entertainment-travel": 4,
    "home-utilities": 4,
    "education": 3,
    "pets": 3,
    "gifts-donations": 2,
    "financial-insurance": 2,
    "office-business": 4,
    "other": 1,
}

# Slug format: lowercase letters, digits, and hyphens only
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Category count and completeness
# ---------------------------------------------------------------------------


class TestCategoryCompleteness:
    """All 13 predefined categories from category-taxonomy.md must be present."""

    def test_exactly_13_categories(self):
        """PREDEFINED_CATEGORIES must contain exactly 13 categories."""
        assert len(PREDEFINED_CATEGORIES) == 13, (
            f"Expected 13 predefined categories, got {len(PREDEFINED_CATEGORIES)}. "
            f"Present: {sorted(PREDEFINED_CATEGORIES.keys())}"
        )

    def test_all_expected_categories_present(self):
        """Every category from category-taxonomy.md must exist in PREDEFINED_CATEGORIES."""
        actual = set(PREDEFINED_CATEGORIES.keys())
        missing = EXPECTED_CATEGORIES - actual
        extra = actual - EXPECTED_CATEGORIES
        assert missing == set(), f"Missing categories: {missing}"
        assert extra == set(), f"Unexpected categories: {extra}"

    def test_get_all_category_slugs_matches(self):
        """get_all_category_slugs() must return all 13 category slugs."""
        slugs = get_all_category_slugs()
        assert slugs == EXPECTED_CATEGORIES, (
            f"get_all_category_slugs() returned unexpected set. "
            f"Missing: {EXPECTED_CATEGORIES - slugs}, Extra: {slugs - EXPECTED_CATEGORIES}"
        )


# ---------------------------------------------------------------------------
# Slug format validation
# ---------------------------------------------------------------------------


class TestSlugFormat:
    """All slugs must be lowercase with hyphens, per category-taxonomy.md."""

    def test_category_slugs_valid_format(self):
        """Category slugs must match lowercase-hyphenated format."""
        for slug in PREDEFINED_CATEGORIES:
            assert SLUG_PATTERN.match(slug), (
                f"Category slug '{slug}' does not match expected format "
                f"(lowercase letters, digits, hyphens)"
            )

    def test_subcategory_slugs_valid_format(self):
        """All subcategory slugs must match lowercase-hyphenated format."""
        for cat_slug, cat_data in PREDEFINED_CATEGORIES.items():
            subcats = cat_data.get("subcategories", {})
            if isinstance(subcats, dict):
                for sub_slug in subcats:
                    assert SLUG_PATTERN.match(sub_slug), (
                        f"Subcategory slug '{sub_slug}' (under '{cat_slug}') "
                        f"does not match expected format"
                    )


# ---------------------------------------------------------------------------
# Subcategories
# ---------------------------------------------------------------------------


class TestSubcategories:
    """Each category must have at least one subcategory per category-taxonomy.md."""

    def test_every_category_has_subcategories(self):
        """Each category must have a non-empty subcategories dict."""
        for slug, data in PREDEFINED_CATEGORIES.items():
            subcats = data.get("subcategories")
            assert subcats, f"Category '{slug}' has no subcategories"
            assert isinstance(subcats, dict), (
                f"Category '{slug}' subcategories should be a dict, got {type(subcats)}"
            )
            assert len(subcats) > 0, f"Category '{slug}' has empty subcategories dict"

    def test_subcategory_counts_match_spec(self):
        """Each category should have the expected number of subcategories from the spec."""
        for slug, expected_count in EXPECTED_SUBCATEGORY_COUNTS.items():
            subcats = PREDEFINED_CATEGORIES[slug].get("subcategories", {})
            actual_count = len(subcats) if isinstance(subcats, dict) else 0
            assert actual_count == expected_count, (
                f"Category '{slug}' has {actual_count} subcategories, "
                f"expected {expected_count} per category-taxonomy.md"
            )

    def test_subcategory_display_names_are_strings(self):
        """Subcategory display names must be non-empty strings."""
        for _cat_slug, cat_data in PREDEFINED_CATEGORIES.items():
            subcats = cat_data.get("subcategories", {})
            if isinstance(subcats, dict):
                for sub_slug, display_name in subcats.items():
                    assert isinstance(display_name, str), (
                        f"Subcategory '{sub_slug}' display name should be a string"
                    )
                    assert len(display_name) > 0, (
                        f"Subcategory '{sub_slug}' display name should not be empty"
                    )

    def test_other_has_uncategorized(self):
        """The 'other' category must have 'uncategorized' subcategory per spec."""
        other = PREDEFINED_CATEGORIES.get("other", {})
        subcats = other.get("subcategories", {})
        assert isinstance(subcats, dict) and "uncategorized" in subcats, (
            "The 'other' category must have an 'uncategorized' subcategory "
            "(AI defaults to other/uncategorized for low confidence)"
        )

    def test_groceries_food_key_subcategories(self):
        """Groceries & Food should have key subcategories from spec."""
        subcats = PREDEFINED_CATEGORIES["groceries-food"]["subcategories"]
        assert isinstance(subcats, dict)
        expected_subs = {
            "supermarket-grocery",
            "produce",
            "meat-seafood",
            "dairy-cheese-eggs",
            "frozen-food",
            "snacks",
            "pantry",
            "beverages",
        }
        actual = set(subcats.keys())
        missing = expected_subs - actual
        assert missing == set(), (
            f"Groceries & Food missing subcategories: {missing}"
        )


# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------


class TestDisplayNames:
    """Display names must match category-taxonomy.md exactly."""

    def test_category_display_names(self):
        """Each category's displayName must match the spec."""
        for slug, expected_name in EXPECTED_DISPLAY_NAMES.items():
            actual = PREDEFINED_CATEGORIES[slug].get("displayName")
            assert actual == expected_name, (
                f"Category '{slug}' displayName is '{actual}', "
                f"expected '{expected_name}' per category-taxonomy.md"
            )

    def test_get_category_display_name_helper(self):
        """get_category_display_name() must return correct display names."""
        for slug, expected_name in EXPECTED_DISPLAY_NAMES.items():
            actual = get_category_display_name(slug)
            assert actual == expected_name, (
                f"get_category_display_name('{slug}') returned '{actual}', "
                f"expected '{expected_name}'"
            )

    def test_get_category_display_name_unknown(self):
        """get_category_display_name() must return None for unknown slugs."""
        result = get_category_display_name("nonexistent-slug")
        assert result is None, (
            f"Expected None for unknown slug, got '{result}'"
        )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Helper functions from shared.constants must work correctly."""

    def test_get_all_subcategory_slugs_nonempty(self):
        """get_all_subcategory_slugs() must return a non-empty set."""
        slugs = get_all_subcategory_slugs()
        assert len(slugs) > 0, "get_all_subcategory_slugs() returned empty set"

    def test_get_all_subcategory_slugs_total_count(self):
        """get_all_subcategory_slugs() should return all subcategories across all categories."""
        expected_total = sum(EXPECTED_SUBCATEGORY_COUNTS.values())
        actual = get_all_subcategory_slugs()
        assert len(actual) == expected_total, (
            f"Expected {expected_total} total subcategory slugs, got {len(actual)}"
        )

    def test_get_subcategory_slugs_for_category(self):
        """get_subcategory_slugs_for_category() returns correct slugs for a known category."""
        slugs = get_subcategory_slugs_for_category("dining")
        expected = {
            "fast-food-quick-service",
            "restaurant-dine-in",
            "delivery-takeout",
            "coffee-cafe",
            "bar-nightlife",
        }
        assert slugs == expected, (
            f"get_subcategory_slugs_for_category('dining') returned {slugs}, "
            f"expected {expected}"
        )

    def test_get_subcategory_slugs_for_unknown_category(self):
        """get_subcategory_slugs_for_category() returns empty set for unknown slug."""
        slugs = get_subcategory_slugs_for_category("does-not-exist")
        assert slugs == set(), (
            f"Expected empty set for unknown category, got {slugs}"
        )

    def test_get_subcategory_display_name_known(self):
        """get_subcategory_display_name() returns correct name for a known subcategory."""
        result = get_subcategory_display_name("supermarket-grocery")
        assert result == "Supermarket / Grocery", (
            f"Expected 'Supermarket / Grocery', got '{result}'"
        )

    def test_get_subcategory_display_name_unknown(self):
        """get_subcategory_display_name() returns None for unknown subcategory."""
        result = get_subcategory_display_name("nonexistent-sub")
        assert result is None, (
            f"Expected None for unknown subcategory, got '{result}'"
        )

    def test_no_duplicate_subcategory_slugs_within_category(self):
        """Subcategory slugs should be unique within each category."""
        for cat_slug, cat_data in PREDEFINED_CATEGORIES.items():
            subcats = cat_data.get("subcategories", {})
            if isinstance(subcats, dict):
                slugs = list(subcats.keys())
                assert len(slugs) == len(set(slugs)), (
                    f"Category '{cat_slug}' has duplicate subcategory slugs"
                )
