"""Pydantic models for receipt upload and storage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UploadFileRequest(BaseModel):
    """Single file in an upload request."""

    fileName: str = Field(min_length=1, max_length=255)
    contentType: Literal["image/jpeg", "image/png"]
    fileSize: int = Field(ge=1, le=10_485_760)


class UploadRequest(BaseModel):
    """POST /api/receipts/upload-urls request body."""

    files: list[UploadFileRequest] = Field(min_length=1, max_length=10)


class UploadReceiptResponse(BaseModel):
    """Single receipt in the upload response."""

    receiptId: str
    uploadUrl: str
    imageKey: str
    expiresIn: int


class UploadResponse(BaseModel):
    """POST /api/receipts/upload-urls response."""

    receipts: list[UploadReceiptResponse]


class Receipt(BaseModel):
    """Full receipt record matching SPEC.md Section 5."""

    receiptId: str
    receiptDate: str | None = None
    merchant: str | None = None
    merchantAddress: str | None = None
    total: float | None = None
    subtotal: float | None = None
    tax: float | None = None
    tip: float | None = None
    category: str | None = None
    subcategory: str | None = None
    status: Literal["processing", "confirmed", "failed"]
    imageKey: str
    failureReason: str | None = None
    paymentMethod: str | None = None
    usedFallback: bool | None = None
    rankingWinner: Literal["ocr-ai", "ai-multimodal", "ai-vision-v2"] | None = None
    createdAt: str
    updatedAt: str


class ReceiptListItem(BaseModel):
    """Receipt summary for list views (no line items)."""

    receiptId: str
    receiptDate: str | None = None
    merchant: str | None = None
    total: float | None = None
    category: str | None = None
    subcategory: str | None = None
    categoryDisplay: str | None = None
    subcategoryDisplay: str | None = None
    status: Literal["processing", "confirmed", "failed"]
    imageUrl: str | None = None
    createdAt: str


class ReceiptListResponse(BaseModel):
    """GET /api/receipts response."""

    receipts: list[ReceiptListItem]
    nextCursor: str | None = None


class ReceiptDetailLineItem(BaseModel):
    """Line item in a receipt detail response."""

    sortOrder: int
    name: str
    quantity: float
    unitPrice: float
    totalPrice: float
    subcategory: str | None = None
    subcategoryDisplay: str | None = None


class ReceiptDetail(BaseModel):
    """GET /api/receipts/{id} response — full receipt with line items."""

    receiptId: str
    receiptDate: str | None = None
    merchant: str | None = None
    merchantAddress: str | None = None
    total: float | None = None
    subtotal: float | None = None
    tax: float | None = None
    tip: float | None = None
    category: str | None = None
    categoryDisplay: str | None = None
    subcategory: str | None = None
    subcategoryDisplay: str | None = None
    status: Literal["processing", "confirmed", "failed"]
    usedFallback: bool | None = None
    rankingWinner: Literal["ocr-ai", "ai-multimodal", "ai-vision-v2"] | None = None
    imageUrl: str | None = None
    paymentMethod: str | None = None
    lineItems: list[ReceiptDetailLineItem] = Field(default_factory=list)
    createdAt: str
    updatedAt: str | None = None


class ReceiptUpdateRequest(BaseModel):
    """PUT /api/receipts/{id} request body — partial update.

    Note: Uses exclude_none=True in the endpoint, so explicit null and absent
    fields are indistinguishable. If null-setting is needed later, switch to
    exclude_unset=True and handle None values with REMOVE expressions.
    """

    model_config = ConfigDict(extra="forbid")

    merchant: str | None = Field(None, max_length=500)
    merchantAddress: str | None = Field(None, max_length=1000)
    receiptDate: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    category: str | None = Field(None, max_length=100)
    subcategory: str | None = Field(None, max_length=100)
    total: float | None = None
    subtotal: float | None = None
    tax: float | None = None
    tip: float | None = None
    paymentMethod: str | None = Field(None, max_length=200)


class LineItemInput(BaseModel):
    """Single line item in a PUT /api/receipts/{id}/items request."""

    sortOrder: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0)
    unitPrice: float = Field(ge=0)
    totalPrice: float = Field(ge=0)
    subcategory: str | None = None


class LineItemsUpdateRequest(BaseModel):
    """PUT /api/receipts/{id}/items request body."""

    items: list[LineItemInput] = Field(min_length=0, max_length=100)
