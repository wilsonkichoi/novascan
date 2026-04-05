"""Pydantic models for receipt extraction (OCR pipeline output).

Matches the schema defined in SPEC.md Section 7.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Merchant(BaseModel):
    """Merchant information extracted from the receipt."""

    name: str
    address: str | None = None
    phone: str | None = None


class LineItem(BaseModel):
    """A single line item on the receipt."""

    name: str
    quantity: float = Field(default=1.0)
    unitPrice: float = Field(default=0.00)
    totalPrice: float = Field(default=0.00)
    subcategory: str | None = None


class ExtractionResult(BaseModel):
    """Full extraction result from the OCR pipeline.

    Serializes to/from JSON matching SPEC Section 7 schema exactly.
    All monetary fields use float (decimal notation, e.g. 5.99 not 599).
    """

    merchant: Merchant
    receiptDate: date | None = None
    currency: str = Field(default="USD")
    lineItems: list[LineItem] = Field(default_factory=list)
    subtotal: float = Field(default=0.00)
    tax: float = Field(default=0.00)
    tip: float | None = None
    total: float = Field(default=0.00)
    category: str = Field(default="other")
    subcategory: str = Field(default="uncategorized")
    paymentMethod: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
