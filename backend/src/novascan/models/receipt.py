"""Pydantic models for receipt upload and storage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
    rankingWinner: Literal["ocr-ai", "ai-multimodal"] | None = None
    createdAt: str
    updatedAt: str


class ReceiptListItem(BaseModel):
    """Receipt summary for list views (no line items)."""

    receiptId: str
    receiptDate: str | None = None
    merchant: str | None = None
    total: float | None = None
    category: str | None = None
    status: Literal["processing", "confirmed", "failed"]
    imageUrl: str | None = None
    createdAt: str


class ReceiptListResponse(BaseModel):
    """GET /api/receipts response."""

    receipts: list[ReceiptListItem]
    cursor: str | None = None
