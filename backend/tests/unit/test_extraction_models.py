"""Tests for Pydantic extraction models -- validates the SPEC Section 7 contract.

Tests the extraction pipeline output models defined in models/extraction.py
against the schema in SPEC.md Section 7. Covers defaults, nullability, boundary
values, rejection of invalid data, and JSON serialization format.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from models.extraction import ExtractionResult, LineItem, Merchant

# ---------------------------------------------------------------------------
# Merchant
# ---------------------------------------------------------------------------


class TestMerchant:
    """Tests for the Merchant sub-model."""

    def test_required_name(self):
        """name is the only required field."""
        m = Merchant(name="Whole Foods Market")
        assert m.name == "Whole Foods Market"

    def test_missing_name_rejected(self):
        """name is required -- omitting it must raise ValidationError."""
        with pytest.raises(ValidationError):
            Merchant()  # type: ignore[call-arg]

    def test_nullable_address_defaults_to_none(self):
        m = Merchant(name="Store")
        assert m.address is None

    def test_nullable_phone_defaults_to_none(self):
        m = Merchant(name="Store")
        assert m.phone is None

    def test_address_and_phone_accepted(self):
        m = Merchant(name="Store", address="123 Main St", phone="512-555-1234")
        assert m.address == "123 Main St"
        assert m.phone == "512-555-1234"

    def test_explicit_none_for_nullable_fields(self):
        m = Merchant(name="Store", address=None, phone=None)
        assert m.address is None
        assert m.phone is None


# ---------------------------------------------------------------------------
# LineItem
# ---------------------------------------------------------------------------


class TestLineItem:
    """Tests for a single line item on the receipt."""

    def test_required_name(self):
        item = LineItem(name="Bananas")
        assert item.name == "Bananas"

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            LineItem()  # type: ignore[call-arg]

    def test_quantity_defaults_to_1(self):
        item = LineItem(name="Bananas")
        assert item.quantity == 1.0

    def test_unit_price_defaults_to_zero(self):
        item = LineItem(name="Bananas")
        assert item.unitPrice == 0.00

    def test_total_price_defaults_to_zero(self):
        item = LineItem(name="Bananas")
        assert item.totalPrice == 0.00

    def test_nullable_subcategory_defaults_to_none(self):
        item = LineItem(name="Bananas")
        assert item.subcategory is None

    def test_subcategory_accepted(self):
        item = LineItem(name="Bananas", subcategory="produce-fresh")
        assert item.subcategory == "produce-fresh"

    def test_all_fields_populated(self):
        item = LineItem(
            name="Organic Bananas",
            quantity=2.0,
            unitPrice=1.29,
            totalPrice=2.58,
            subcategory="produce-fresh",
        )
        assert item.quantity == 2.0
        assert item.unitPrice == 1.29
        assert item.totalPrice == 2.58

    def test_negative_monetary_values_accepted(self):
        """Negative values are valid -- OCR may produce refunds/credits."""
        item = LineItem(name="Refund", unitPrice=-5.00, totalPrice=-5.00)
        assert item.totalPrice == -5.00


# ---------------------------------------------------------------------------
# ExtractionResult — Defaults
# ---------------------------------------------------------------------------


class TestExtractionResultDefaults:
    """Tests that all default values match SPEC Section 7."""

    @pytest.fixture()
    def minimal_result(self) -> ExtractionResult:
        """The smallest valid ExtractionResult: only merchant.name is required."""
        return ExtractionResult(merchant=Merchant(name="Test Store"))

    def test_currency_defaults_to_usd(self, minimal_result: ExtractionResult):
        assert minimal_result.currency == "USD"

    def test_category_defaults_to_other(self, minimal_result: ExtractionResult):
        assert minimal_result.category == "other"

    def test_subcategory_defaults_to_uncategorized(self, minimal_result: ExtractionResult):
        assert minimal_result.subcategory == "uncategorized"

    def test_confidence_defaults_to_zero(self, minimal_result: ExtractionResult):
        assert minimal_result.confidence == 0.0

    def test_subtotal_defaults_to_zero(self, minimal_result: ExtractionResult):
        assert minimal_result.subtotal == 0.00

    def test_tax_defaults_to_zero(self, minimal_result: ExtractionResult):
        assert minimal_result.tax == 0.00

    def test_total_defaults_to_zero(self, minimal_result: ExtractionResult):
        assert minimal_result.total == 0.00

    def test_line_items_defaults_to_empty_list(self, minimal_result: ExtractionResult):
        """lineItems must default to an empty list (default_factory=list)."""
        assert minimal_result.lineItems == []
        assert isinstance(minimal_result.lineItems, list)

    def test_line_items_default_not_shared_between_instances(self):
        """Each instance must get its own list -- no mutable default sharing."""
        a = ExtractionResult(merchant=Merchant(name="A"))
        b = ExtractionResult(merchant=Merchant(name="B"))
        a.lineItems.append(LineItem(name="Only on A"))
        assert len(b.lineItems) == 0, "Mutable default was shared between instances"


# ---------------------------------------------------------------------------
# ExtractionResult — Nullable Fields
# ---------------------------------------------------------------------------


class TestExtractionResultNullableFields:
    """Tests for fields that should default to None."""

    @pytest.fixture()
    def minimal_result(self) -> ExtractionResult:
        return ExtractionResult(merchant=Merchant(name="Test Store"))

    def test_receipt_date_defaults_to_none(self, minimal_result: ExtractionResult):
        assert minimal_result.receiptDate is None

    def test_tip_defaults_to_none(self, minimal_result: ExtractionResult):
        assert minimal_result.tip is None

    def test_payment_method_defaults_to_none(self, minimal_result: ExtractionResult):
        assert minimal_result.paymentMethod is None

    def test_nullable_fields_accept_explicit_none(self):
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            receiptDate=None,
            tip=None,
            paymentMethod=None,
        )
        assert result.receiptDate is None
        assert result.tip is None
        assert result.paymentMethod is None


# ---------------------------------------------------------------------------
# ExtractionResult — Confidence Bounds
# ---------------------------------------------------------------------------


class TestConfidenceBounds:
    """confidence must be in [0.0, 1.0] per SPEC."""

    def test_confidence_accepts_zero(self):
        result = ExtractionResult(merchant=Merchant(name="S"), confidence=0.0)
        assert result.confidence == 0.0

    def test_confidence_accepts_one(self):
        result = ExtractionResult(merchant=Merchant(name="S"), confidence=1.0)
        assert result.confidence == 1.0

    def test_confidence_accepts_midpoint(self):
        result = ExtractionResult(merchant=Merchant(name="S"), confidence=0.85)
        assert result.confidence == 0.85

    def test_confidence_rejects_below_zero(self):
        with pytest.raises(ValidationError) as exc_info:
            ExtractionResult(merchant=Merchant(name="S"), confidence=-0.01)
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_rejects_above_one(self):
        with pytest.raises(ValidationError) as exc_info:
            ExtractionResult(merchant=Merchant(name="S"), confidence=1.01)
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_rejects_large_negative(self):
        with pytest.raises(ValidationError):
            ExtractionResult(merchant=Merchant(name="S"), confidence=-100.0)

    def test_confidence_rejects_large_positive(self):
        with pytest.raises(ValidationError):
            ExtractionResult(merchant=Merchant(name="S"), confidence=100.0)


# ---------------------------------------------------------------------------
# ExtractionResult — JSON Serialization Format
# ---------------------------------------------------------------------------


class TestSerializationFormat:
    """Validates that JSON output matches SPEC Section 7 format."""

    def test_monetary_fields_are_numbers_not_strings(self):
        """subtotal, tax, tip, total must serialize as JSON numbers."""
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            subtotal=28.14,
            tax=2.25,
            tip=5.00,
            total=35.39,
        )
        raw = json.loads(result.model_dump_json())
        assert isinstance(raw["subtotal"], (int, float)), "subtotal must be a number"
        assert isinstance(raw["tax"], (int, float)), "tax must be a number"
        assert isinstance(raw["tip"], (int, float)), "tip must be a number"
        assert isinstance(raw["total"], (int, float)), "total must be a number"

    def test_line_item_prices_are_numbers(self):
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[LineItem(name="Item", quantity=2.0, unitPrice=3.50, totalPrice=7.00)],
        )
        raw = json.loads(result.model_dump_json())
        item = raw["lineItems"][0]
        assert isinstance(item["quantity"], (int, float)), "quantity must be a number"
        assert isinstance(item["unitPrice"], (int, float)), "unitPrice must be a number"
        assert isinstance(item["totalPrice"], (int, float)), "totalPrice must be a number"

    def test_receipt_date_serializes_as_yyyy_mm_dd(self):
        """receiptDate must serialize as an ISO 'YYYY-MM-DD' string."""
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            receiptDate=date(2026, 3, 25),
        )
        raw = json.loads(result.model_dump_json())
        assert raw["receiptDate"] == "2026-03-25"

    def test_null_receipt_date_serializes_as_null(self):
        result = ExtractionResult(merchant=Merchant(name="Store"))
        raw = json.loads(result.model_dump_json())
        assert raw["receiptDate"] is None

    def test_null_tip_serializes_as_null(self):
        result = ExtractionResult(merchant=Merchant(name="Store"))
        raw = json.loads(result.model_dump_json())
        assert raw["tip"] is None

    def test_null_payment_method_serializes_as_null(self):
        result = ExtractionResult(merchant=Merchant(name="Store"))
        raw = json.loads(result.model_dump_json())
        assert raw["paymentMethod"] is None

    def test_confidence_serializes_as_number(self):
        result = ExtractionResult(merchant=Merchant(name="Store"), confidence=0.92)
        raw = json.loads(result.model_dump_json())
        assert isinstance(raw["confidence"], (int, float))
        assert raw["confidence"] == 0.92


# ---------------------------------------------------------------------------
# ExtractionResult — JSON Round-Trip
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    """model_dump_json() -> model_validate_json() must produce identical model."""

    def test_minimal_round_trip(self):
        original = ExtractionResult(merchant=Merchant(name="Test Store"))
        json_str = original.model_dump_json()
        restored = ExtractionResult.model_validate_json(json_str)
        assert restored == original

    def test_full_round_trip(self):
        original = ExtractionResult(
            merchant=Merchant(
                name="Whole Foods Market",
                address="123 Main St, Austin, TX 78701",
                phone="512-555-0100",
            ),
            receiptDate=date(2026, 3, 25),
            currency="USD",
            lineItems=[
                LineItem(
                    name="Organic Bananas",
                    quantity=2.0,
                    unitPrice=1.29,
                    totalPrice=2.58,
                    subcategory="produce-fresh",
                ),
                LineItem(name="Almond Milk", quantity=1.0, unitPrice=4.99, totalPrice=4.99),
            ],
            subtotal=28.14,
            tax=2.25,
            tip=5.00,
            total=35.39,
            category="groceries-food",
            subcategory="supermarket-grocery",
            paymentMethod="VISA *1234",
            confidence=0.92,
        )
        json_str = original.model_dump_json()
        restored = ExtractionResult.model_validate_json(json_str)
        assert restored == original

    def test_round_trip_with_null_fields(self):
        """Nullable fields set to None survive round-trip."""
        original = ExtractionResult(
            merchant=Merchant(name="Store"),
            receiptDate=None,
            tip=None,
            paymentMethod=None,
        )
        json_str = original.model_dump_json()
        restored = ExtractionResult.model_validate_json(json_str)
        assert restored == original
        assert restored.receiptDate is None
        assert restored.tip is None
        assert restored.paymentMethod is None

    def test_round_trip_preserves_line_items(self):
        original = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", quantity=3.0, unitPrice=1.00, totalPrice=3.00),
                LineItem(name="B"),
            ],
        )
        json_str = original.model_dump_json()
        restored = ExtractionResult.model_validate_json(json_str)
        assert len(restored.lineItems) == 2
        assert restored.lineItems[0].name == "A"
        assert restored.lineItems[0].quantity == 3.0
        assert restored.lineItems[1].name == "B"
        assert restored.lineItems[1].quantity == 1.0  # default


# ---------------------------------------------------------------------------
# ExtractionResult — Negative Monetary Values
# ---------------------------------------------------------------------------


class TestNegativeMonetaryValues:
    """Negative values are allowed -- OCR may produce refunds/credits."""

    def test_negative_subtotal_accepted(self):
        result = ExtractionResult(merchant=Merchant(name="S"), subtotal=-10.00)
        assert result.subtotal == -10.00

    def test_negative_tax_accepted(self):
        result = ExtractionResult(merchant=Merchant(name="S"), tax=-1.50)
        assert result.tax == -1.50

    def test_negative_total_accepted(self):
        result = ExtractionResult(merchant=Merchant(name="S"), total=-35.00)
        assert result.total == -35.00

    def test_negative_tip_accepted(self):
        result = ExtractionResult(merchant=Merchant(name="S"), tip=-2.00)
        assert result.tip == -2.00
