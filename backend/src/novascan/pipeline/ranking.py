"""Ranking algorithm for comparing pipeline extraction results.

Computes a composite rankingScore (0-1) for each pipeline based on:
- confidence (from ExtractionResult) — weighted most heavily
- field_completeness — fraction of non-null fields
- line_item_quality — fraction of items with valid unit prices and consistent math
- total_consistency — do line items sum close to subtotal/total? (quadratic decay)

Used by Finalize Lambda for data collection only. The ranking does NOT
affect which pipeline result is displayed to the user — that is determined
by the main/shadow selection logic.
"""

from __future__ import annotations

from novascan.models.extraction import ExtractionResult

# Weights for composite score (must sum to 1.0)
WEIGHT_CONFIDENCE = 0.20
WEIGHT_COMPLETENESS = 0.30
WEIGHT_LINE_ITEMS = 0.10
WEIGHT_CONSISTENCY = 0.40

# Fields checked for completeness scoring
_COMPLETENESS_FIELDS = [
    "merchant.name",
    "receiptDate",
    "total",
    "subtotal",
    "tax",
    "category",
    "paymentMethod",
    "tip",
    "currency",
]

# Tolerance for total consistency check (fraction of total).
# If |sum(lineItems) - subtotal| / total <= tolerance, it's consistent.
_CONSISTENCY_TOLERANCE = 0.02


def rank_results(result: ExtractionResult) -> float:
    """Compute a composite ranking score (0-1) for one pipeline result.

    Args:
        result: The extraction result from one pipeline.

    Returns:
        A float between 0.0 and 1.0 representing the composite quality score.
    """
    confidence_score = result.confidence
    completeness_score = _compute_field_completeness(result)
    line_item_score = _compute_line_item_score(result)
    consistency_score = _compute_total_consistency(result)

    composite = (
        WEIGHT_CONFIDENCE * confidence_score
        + WEIGHT_COMPLETENESS * completeness_score
        + WEIGHT_LINE_ITEMS * line_item_score
        + WEIGHT_CONSISTENCY * consistency_score
    )

    # Clamp to [0, 1] — should already be in range but be defensive
    return float(max(0.0, min(1.0, round(composite, 4))))


def _compute_field_completeness(result: ExtractionResult) -> float:
    """Fraction of key fields that are non-null and non-default."""
    present = 0
    total = len(_COMPLETENESS_FIELDS)

    for field_path in _COMPLETENESS_FIELDS:
        if "." in field_path:
            # Nested field: merchant.name
            parts = field_path.split(".")
            obj = getattr(result, parts[0], None)
            value = getattr(obj, parts[1], None) if obj else None
        else:
            value = getattr(result, field_path, None)

        if value is not None:
            # For numeric fields, 0.0 is a valid value (tax=0 is real).
            # For strings, empty string counts as missing.
            if isinstance(value, str) and value == "":
                continue
            present += 1

    return present / total if total > 0 else 0.0


def _compute_line_item_score(result: ExtractionResult) -> float:
    """Quality score: fraction of line items with valid pricing.

    An item is "valid" when unitPrice > 0 and qty * unitPrice is within
    5% of totalPrice. Items with unitPrice=0 but totalPrice>0 indicate
    the model failed to extract pricing detail.
    """
    if not result.lineItems:
        return 0.0

    valid = 0
    for item in result.lineItems:
        if item.unitPrice <= 0:
            continue
        expected = item.quantity * item.unitPrice
        if item.totalPrice <= 0 or abs(expected - item.totalPrice) / item.totalPrice <= 0.05:
            valid += 1

    return valid / len(result.lineItems)


def _compute_total_consistency(result: ExtractionResult) -> float:
    """Check whether line item totals are consistent with subtotal/total.

    Returns 1.0 if consistent, degrades toward 0.0 as discrepancy grows.
    Returns 0.5 if there are no line items (unknown consistency).
    """
    if not result.lineItems:
        # No line items to check — neutral score
        return 0.5

    line_item_sum = sum(item.totalPrice for item in result.lineItems)

    # Compare against subtotal first (more directly comparable to line items),
    # fall back to total if subtotal is zero
    reference = result.subtotal if result.subtotal > 0 else result.total

    if reference <= 0:
        # Can't check consistency without a reference total
        return 0.5

    discrepancy = abs(line_item_sum - reference) / reference

    if discrepancy <= _CONSISTENCY_TOLERANCE:
        return 1.0

    # Quadratic decay: small overages penalized meaningfully, 30%+ → 0.0
    max_discrepancy = 0.30
    if discrepancy >= max_discrepancy:
        return 0.0

    t = (discrepancy - _CONSISTENCY_TOLERANCE) / (max_discrepancy - _CONSISTENCY_TOLERANCE)
    return float(1.0 - t * t)
