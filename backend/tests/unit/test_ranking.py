"""Tests for the pipeline ranking algorithm.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- rank_results computes a composite score 0.0-1.0
- Based on: confidence, field completeness, line item count, total consistency
- Perfect result -> near 1.0
- Empty/minimal result -> near 0.0
- Inconsistent totals -> lower score
"""

from __future__ import annotations

from datetime import date

from novascan.models.extraction import ExtractionResult, LineItem, Merchant
from novascan.pipeline.ranking import rank_results

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _perfect_result() -> ExtractionResult:
    """Build an ExtractionResult with all fields populated and consistent totals."""
    return ExtractionResult(
        merchant=Merchant(name="Whole Foods Market", address="123 Main St", phone="512-555-0100"),
        receiptDate=date(2026, 3, 25),
        currency="USD",
        lineItems=[
            LineItem(name="Organic Milk", quantity=1, unitPrice=5.99, totalPrice=5.99),
            LineItem(name="Bread", quantity=2, unitPrice=3.50, totalPrice=7.00),
            LineItem(name="Eggs", quantity=1, unitPrice=4.49, totalPrice=4.49),
            LineItem(name="Butter", quantity=1, unitPrice=3.99, totalPrice=3.99),
            LineItem(name="Cheese", quantity=1, unitPrice=6.99, totalPrice=6.99),
        ],
        subtotal=28.46,
        tax=2.35,
        tip=5.00,
        total=35.81,
        category="groceries-food",
        subcategory="supermarket-grocery",
        paymentMethod="VISA *1234",
        confidence=0.95,
    )


def _minimal_result() -> ExtractionResult:
    """Build a minimal ExtractionResult — only merchant name (the only required field)."""
    return ExtractionResult(merchant=Merchant(name="Unknown"))


# ---------------------------------------------------------------------------
# Basic contract: returns float in [0, 1]
# ---------------------------------------------------------------------------


class TestRankingContract:
    """rank_results must return a float between 0.0 and 1.0."""

    def test_returns_float(self):
        """Return type must be float."""
        score = rank_results(_minimal_result())
        assert isinstance(score, float), f"Expected float, got {type(score)}"

    def test_score_in_valid_range(self):
        """Score must be between 0.0 and 1.0 inclusive."""
        score = rank_results(_minimal_result())
        assert 0.0 <= score <= 1.0, f"Score {score} out of [0, 1] range"

    def test_perfect_result_in_valid_range(self):
        """Even a perfect score must be within [0, 1]."""
        score = rank_results(_perfect_result())
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Perfect result: near 1.0
# ---------------------------------------------------------------------------


class TestRankingPerfectResult:
    """A result with all fields, high confidence, and consistent totals -> near 1.0."""

    def test_perfect_result_scores_high(self):
        """A fully populated, consistent result should score near 1.0."""
        score = rank_results(_perfect_result())
        assert score >= 0.75, (
            f"Perfect result should score >= 0.75, got {score}. "
            "SPEC says: high confidence + all fields + consistent totals -> near 1.0"
        )

    def test_perfect_result_above_minimal(self):
        """A perfect result must score significantly higher than a minimal one."""
        perfect = rank_results(_perfect_result())
        minimal = rank_results(_minimal_result())
        assert perfect > minimal + 0.3, (
            f"Perfect ({perfect}) should be well above minimal ({minimal}). "
            "SPEC ranking components: confidence, completeness, line items, consistency"
        )


# ---------------------------------------------------------------------------
# Empty/minimal result: near 0.0
# ---------------------------------------------------------------------------


class TestRankingMinimalResult:
    """A minimal result (defaults for everything) -> near 0.0."""

    def test_minimal_result_scores_low(self):
        """Only merchant name, all defaults -> score near 0.0."""
        score = rank_results(_minimal_result())
        assert score <= 0.35, (
            f"Minimal result should score <= 0.35, got {score}. "
            "SPEC says: empty result -> near 0.0"
        )

    def test_zero_confidence_reduces_score(self):
        """A result with 0 confidence should score lower than one with high confidence."""
        zero_conf = ExtractionResult(merchant=Merchant(name="Store"), confidence=0.0)
        high_conf = ExtractionResult(merchant=Merchant(name="Store"), confidence=0.95)

        assert rank_results(zero_conf) < rank_results(high_conf), (
            "Higher confidence should always produce a higher score (all else equal)"
        )


# ---------------------------------------------------------------------------
# Inconsistent totals: reduce score
# ---------------------------------------------------------------------------


class TestRankingTotalConsistency:
    """Inconsistent line item totals vs subtotal/total should reduce the score."""

    def test_inconsistent_totals_lower_score(self):
        """Line items that don't sum to subtotal/total should score lower."""
        consistent = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", quantity=1, unitPrice=10.00, totalPrice=10.00),
                LineItem(name="B", quantity=1, unitPrice=15.00, totalPrice=15.00),
            ],
            subtotal=25.00,
            total=27.00,
            tax=2.00,
            confidence=0.90,
        )

        inconsistent = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", quantity=1, unitPrice=10.00, totalPrice=10.00),
                LineItem(name="B", quantity=1, unitPrice=15.00, totalPrice=15.00),
            ],
            subtotal=100.00,  # Line items sum to 25, but subtotal says 100
            total=108.00,
            tax=8.00,
            confidence=0.90,
        )

        consistent_score = rank_results(consistent)
        inconsistent_score = rank_results(inconsistent)

        assert consistent_score > inconsistent_score, (
            f"Consistent ({consistent_score}) should score higher than "
            f"inconsistent ({inconsistent_score}). "
            "SPEC says: inconsistent totals reduce score"
        )

    def test_wildly_inconsistent_totals(self):
        """Extreme discrepancy should produce a noticeably lower score."""
        # Line items sum to 10, subtotal is 1000
        wildly_off = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="X", quantity=1, unitPrice=10.00, totalPrice=10.00),
            ],
            subtotal=1000.00,
            total=1100.00,
            confidence=0.90,
        )

        good = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="X", quantity=1, unitPrice=10.00, totalPrice=10.00),
            ],
            subtotal=10.00,
            total=10.80,
            tax=0.80,
            confidence=0.90,
        )

        assert rank_results(good) > rank_results(wildly_off)


# ---------------------------------------------------------------------------
# Component influences: confidence, completeness, line items
# ---------------------------------------------------------------------------


class TestRankingComponents:
    """Individual ranking components affect the composite score."""

    def test_more_line_items_increases_score(self):
        """More line items should contribute to a higher score, per SPEC."""
        few_items = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[LineItem(name="A", totalPrice=10)],
            subtotal=10.00,
            total=10.80,
            confidence=0.85,
        )

        many_items = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name=f"Item {i}", totalPrice=2.00) for i in range(10)
            ],
            subtotal=20.00,
            total=21.60,
            confidence=0.85,
        )

        assert rank_results(many_items) > rank_results(few_items), (
            "More line items should increase the ranking score"
        )

    def test_more_fields_populated_increases_score(self):
        """A result with more non-null fields should score higher (completeness)."""
        sparse = ExtractionResult(
            merchant=Merchant(name="Store"),
            confidence=0.85,
        )

        complete = ExtractionResult(
            merchant=Merchant(name="Store", address="123 St", phone="555-1234"),
            receiptDate=date(2026, 3, 25),
            subtotal=25.00,
            tax=2.00,
            tip=5.00,
            total=32.00,
            category="groceries-food",
            paymentMethod="VISA *1234",
            confidence=0.85,
        )

        assert rank_results(complete) > rank_results(sparse), (
            "More populated fields should increase the ranking score"
        )

    def test_confidence_is_dominant_factor(self):
        """Confidence is weighted most heavily per SPEC — a large confidence
        difference should outweigh moderate differences in other components."""
        low_confidence = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", totalPrice=10.00),
                LineItem(name="B", totalPrice=15.00),
            ],
            subtotal=25.00,
            total=27.00,
            confidence=0.10,
        )

        high_confidence = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", totalPrice=10.00),
            ],
            subtotal=10.00,
            total=10.80,
            confidence=0.95,
        )

        # High confidence should win even with fewer line items
        assert rank_results(high_confidence) > rank_results(low_confidence)

    def test_no_line_items_gets_neutral_consistency(self):
        """With zero line items, consistency is unknown — should not penalize."""
        with_items = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[
                LineItem(name="A", totalPrice=10.00),
            ],
            subtotal=10.00,
            total=10.00,
            confidence=0.80,
        )

        without_items = ExtractionResult(
            merchant=Merchant(name="Store"),
            subtotal=10.00,
            total=10.00,
            confidence=0.80,
        )

        # Without items should not score dramatically lower (just missing
        # the line_items component and neutral consistency)
        score_with = rank_results(with_items)
        score_without = rank_results(without_items)

        # The difference should be moderate, not catastrophic
        assert score_without >= score_with * 0.5, (
            f"No line items ({score_without}) should not catastrophically penalize "
            f"vs with items ({score_with})"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestRankingEdgeCases:
    """Edge cases and boundary values."""

    def test_max_confidence_max_completeness(self):
        """confidence=1.0 with all fields populated should score very high."""
        result = _perfect_result()
        # Override confidence to max
        result.confidence = 1.0
        score = rank_results(result)
        assert score >= 0.80, f"Max everything should score >= 0.80, got {score}"

    def test_zero_confidence_zero_everything(self):
        """Absolute minimum: merchant name only, confidence=0."""
        result = ExtractionResult(
            merchant=Merchant(name="?"),
            confidence=0.0,
        )
        score = rank_results(result)
        assert score <= 0.30, f"Zero everything should score <= 0.30, got {score}"

    def test_single_line_item_consistent(self):
        """A single line item that matches the subtotal should not crash."""
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=[LineItem(name="Item", totalPrice=10.00)],
            subtotal=10.00,
            total=10.80,
            tax=0.80,
            confidence=0.85,
        )
        score = rank_results(result)
        assert 0.0 <= score <= 1.0

    def test_many_line_items_capped(self):
        """Having 100 line items should not produce a score above 1.0."""
        items = [LineItem(name=f"Item {i}", totalPrice=1.00) for i in range(100)]
        result = ExtractionResult(
            merchant=Merchant(name="Store"),
            lineItems=items,
            subtotal=100.00,
            total=108.00,
            confidence=0.95,
        )
        score = rank_results(result)
        assert score <= 1.0, f"Score exceeded 1.0 with 100 items: {score}"

    def test_deterministic(self):
        """Same input should always produce the same score."""
        result = _perfect_result()
        score1 = rank_results(result)
        score2 = rank_results(result)
        assert score1 == score2, "Ranking must be deterministic"
