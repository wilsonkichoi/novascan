"""Tests for Pydantic receipt models — validates the data contract.

Tests the request/response models defined in models/receipt.py against
the API contract in api-contracts.md. Covers validation rules, boundary
values, and rejection of invalid data.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.receipt import (
    Receipt,
    ReceiptListItem,
    ReceiptListResponse,
    UploadFileRequest,
    UploadReceiptResponse,
    UploadRequest,
    UploadResponse,
)

# ---------------------------------------------------------------------------
# UploadFileRequest
# ---------------------------------------------------------------------------


class TestUploadFileRequest:
    """Tests for single file metadata in an upload request."""

    def test_valid_jpeg(self):
        req = UploadFileRequest(fileName="receipt.jpg", contentType="image/jpeg", fileSize=2_048_576)
        assert req.fileName == "receipt.jpg"
        assert req.contentType == "image/jpeg"
        assert req.fileSize == 2_048_576

    def test_valid_png(self):
        req = UploadFileRequest(fileName="receipt.png", contentType="image/png", fileSize=1)
        assert req.contentType == "image/png"

    def test_min_file_size_boundary(self):
        """fileSize >= 1 byte per spec."""
        req = UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=1)
        assert req.fileSize == 1

    def test_max_file_size_boundary(self):
        """fileSize <= 10,485,760 bytes (10 MB) per spec."""
        req = UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=10_485_760)
        assert req.fileSize == 10_485_760

    def test_zero_file_size_rejected(self):
        """fileSize=0 is below the minimum of 1."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=0)
        assert "fileSize" in str(exc_info.value) or "greater_than_equal" in str(exc_info.value)

    def test_negative_file_size_rejected(self):
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=-1)

    def test_oversized_file_rejected(self):
        """Files exceeding 10 MB must be rejected."""
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=10_485_761)

    def test_invalid_content_type_rejected(self):
        """Only image/jpeg and image/png are accepted per spec."""
        with pytest.raises(ValidationError) as exc_info:
            UploadFileRequest(fileName="receipt.gif", contentType="image/gif", fileSize=1000)
        errors = exc_info.value.errors()
        assert any("contentType" in str(e) or "literal" in str(e).lower() for e in errors)

    def test_pdf_content_type_rejected(self):
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName="receipt.pdf", contentType="application/pdf", fileSize=1000)

    def test_empty_filename_rejected(self):
        """fileName must be 1-255 characters."""
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName="", contentType="image/jpeg", fileSize=1000)

    def test_max_length_filename_accepted(self):
        """fileName up to 255 characters should be accepted."""
        long_name = "a" * 251 + ".jpg"
        assert len(long_name) == 255
        req = UploadFileRequest(fileName=long_name, contentType="image/jpeg", fileSize=1000)
        assert req.fileName == long_name

    def test_filename_too_long_rejected(self):
        """fileName over 255 characters must be rejected."""
        long_name = "a" * 252 + ".jpg"
        assert len(long_name) == 256
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName=long_name, contentType="image/jpeg", fileSize=1000)

    def test_missing_fields_rejected(self):
        with pytest.raises(ValidationError):
            UploadFileRequest(fileName="a.jpg")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# UploadRequest
# ---------------------------------------------------------------------------


class TestUploadRequest:
    """Tests for the upload request body (files array)."""

    def test_single_file(self):
        req = UploadRequest(
            files=[UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=1000)]
        )
        assert len(req.files) == 1

    def test_max_ten_files(self):
        """Up to 10 files per batch per spec."""
        files = [
            UploadFileRequest(fileName=f"receipt{i}.jpg", contentType="image/jpeg", fileSize=1000)
            for i in range(10)
        ]
        req = UploadRequest(files=files)
        assert len(req.files) == 10

    def test_exceeds_ten_files_rejected(self):
        """More than 10 files must be rejected per spec."""
        files = [
            UploadFileRequest(fileName=f"receipt{i}.jpg", contentType="image/jpeg", fileSize=1000)
            for i in range(11)
        ]
        with pytest.raises(ValidationError) as exc_info:
            UploadRequest(files=files)
        # Should reference the files constraint
        assert "files" in str(exc_info.value) or "max_length" in str(exc_info.value)

    def test_empty_files_rejected(self):
        """At least 1 file required per spec."""
        with pytest.raises(ValidationError):
            UploadRequest(files=[])

    def test_mixed_content_types(self):
        """A batch can contain both JPEG and PNG files."""
        req = UploadRequest(
            files=[
                UploadFileRequest(fileName="a.jpg", contentType="image/jpeg", fileSize=1000),
                UploadFileRequest(fileName="b.png", contentType="image/png", fileSize=2000),
            ]
        )
        assert req.files[0].contentType == "image/jpeg"
        assert req.files[1].contentType == "image/png"

    def test_from_dict_valid(self):
        """Validates that the model can be constructed from raw dict (as API would)."""
        data = {
            "files": [
                {"fileName": "receipt.jpg", "contentType": "image/jpeg", "fileSize": 5000},
            ]
        }
        req = UploadRequest(**data)
        assert len(req.files) == 1
        assert req.files[0].fileName == "receipt.jpg"

    def test_from_dict_invalid_content_type(self):
        data = {
            "files": [
                {"fileName": "receipt.gif", "contentType": "image/gif", "fileSize": 5000},
            ]
        }
        with pytest.raises(ValidationError):
            UploadRequest(**data)


# ---------------------------------------------------------------------------
# UploadReceiptResponse and UploadResponse
# ---------------------------------------------------------------------------


class TestUploadResponse:
    """Tests for the upload response models."""

    def test_upload_receipt_response_fields(self):
        resp = UploadReceiptResponse(
            receiptId="01HQ3K5P7M2N4R6S8T0V",
            uploadUrl="https://bucket.s3.amazonaws.com/receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
            imageKey="receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
            expiresIn=900,
        )
        assert resp.receiptId == "01HQ3K5P7M2N4R6S8T0V"
        assert resp.expiresIn == 900
        assert "receipts/" in resp.imageKey

    def test_upload_response_multiple_receipts(self):
        receipts = [
            UploadReceiptResponse(
                receiptId=f"id{i}",
                uploadUrl=f"https://example.com/{i}",
                imageKey=f"receipts/id{i}.jpg",
                expiresIn=900,
            )
            for i in range(3)
        ]
        resp = UploadResponse(receipts=receipts)
        assert len(resp.receipts) == 3

    def test_upload_response_serialization(self):
        """Response should serialize to JSON matching the API contract."""
        resp = UploadResponse(
            receipts=[
                UploadReceiptResponse(
                    receiptId="id1",
                    uploadUrl="https://example.com/upload",
                    imageKey="receipts/id1.jpg",
                    expiresIn=900,
                )
            ]
        )
        data = resp.model_dump()
        assert "receipts" in data
        assert data["receipts"][0]["receiptId"] == "id1"
        assert data["receipts"][0]["expiresIn"] == 900


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------


class TestReceipt:
    """Tests for the full Receipt model (SPEC.md Section 5)."""

    def test_processing_receipt_minimal(self):
        """Processing receipts have null values for OCR fields."""
        receipt = Receipt(
            receiptId="01HQ3K5P7M2N4R6S8T0V",
            status="processing",
            imageKey="receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
            createdAt="2026-03-25T14:30:00Z",
            updatedAt="2026-03-25T14:30:00Z",
        )
        assert receipt.status == "processing"
        assert receipt.merchant is None
        assert receipt.total is None
        assert receipt.category is None
        assert receipt.receiptDate is None

    def test_confirmed_receipt_full(self):
        receipt = Receipt(
            receiptId="01HQ3K5P7M2N4R6S8T0V",
            receiptDate="2026-03-25",
            merchant="Whole Foods Market",
            merchantAddress="123 Main St, Austin, TX 78701",
            total=30.39,
            subtotal=28.14,
            tax=2.25,
            tip=None,
            category="groceries-food",
            subcategory="supermarket-grocery",
            status="confirmed",
            imageKey="receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
            paymentMethod="VISA *1234",
            usedFallback=False,
            rankingWinner="ocr-ai",
            createdAt="2026-03-25T14:30:00Z",
            updatedAt="2026-03-25T14:31:00Z",
        )
        assert receipt.status == "confirmed"
        assert receipt.total == 30.39
        assert receipt.rankingWinner == "ocr-ai"

    def test_failed_receipt_with_reason(self):
        receipt = Receipt(
            receiptId="01HQ3K5P7M2N4R6S8T0V",
            status="failed",
            imageKey="receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
            failureReason="Textract failed: unreadable image",
            createdAt="2026-03-25T14:30:00Z",
            updatedAt="2026-03-25T14:31:00Z",
        )
        assert receipt.status == "failed"
        assert receipt.failureReason is not None

    def test_invalid_status_rejected(self):
        """Status must be one of: processing, confirmed, failed."""
        with pytest.raises(ValidationError):
            Receipt(
                receiptId="id1",
                status="completed",  # type: ignore[arg-type]
                imageKey="receipts/id1.jpg",
                createdAt="2026-01-01T00:00:00Z",
                updatedAt="2026-01-01T00:00:00Z",
            )

    def test_ranking_winner_values(self):
        """rankingWinner must be 'ocr-ai' or 'ai-multimodal' or None."""
        for winner in ("ocr-ai", "ai-multimodal"):
            receipt = Receipt(
                receiptId="id1",
                status="confirmed",
                imageKey="receipts/id1.jpg",
                rankingWinner=winner,  # type: ignore[arg-type]
                createdAt="2026-01-01T00:00:00Z",
                updatedAt="2026-01-01T00:00:00Z",
            )
            assert receipt.rankingWinner == winner

    def test_invalid_ranking_winner_rejected(self):
        with pytest.raises(ValidationError):
            Receipt(
                receiptId="id1",
                status="confirmed",
                imageKey="receipts/id1.jpg",
                rankingWinner="unknown-pipeline",  # type: ignore[arg-type]
                createdAt="2026-01-01T00:00:00Z",
                updatedAt="2026-01-01T00:00:00Z",
            )

    def test_used_fallback_flag(self):
        """usedFallback is optional boolean per spec."""
        receipt = Receipt(
            receiptId="id1",
            status="confirmed",
            imageKey="receipts/id1.jpg",
            usedFallback=True,
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-01T00:00:00Z",
        )
        assert receipt.usedFallback is True

    def test_missing_required_fields_rejected(self):
        """receiptId, status, imageKey, createdAt, updatedAt are required."""
        with pytest.raises(ValidationError):
            Receipt(receiptId="id1", status="processing")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ReceiptListItem
# ---------------------------------------------------------------------------


class TestReceiptListItem:
    """Tests for receipt summary used in list views."""

    def test_processing_receipt_null_ocr_fields(self):
        """Per spec, receipts with status=processing have null for merchant, total, category."""
        item = ReceiptListItem(
            receiptId="id1",
            status="processing",
            createdAt="2026-03-25T14:30:00Z",
        )
        assert item.merchant is None
        assert item.total is None
        assert item.category is None
        assert item.categoryDisplay is None

    def test_confirmed_receipt_with_all_fields(self):
        item = ReceiptListItem(
            receiptId="01HQ3K5P7M2N4R6S8T0V",
            receiptDate="2026-03-25",
            merchant="Whole Foods Market",
            total=30.39,
            category="groceries-food",
            categoryDisplay="Groceries & Food",
            subcategory="supermarket-grocery",
            subcategoryDisplay="Supermarket / Grocery",
            status="confirmed",
            imageUrl="https://bucket.s3.amazonaws.com/receipts/...",
            createdAt="2026-03-25T14:30:00Z",
        )
        assert item.receiptDate == "2026-03-25"
        assert item.categoryDisplay == "Groceries & Food"

    def test_serialization_matches_api_contract(self):
        """Field names in JSON output should match the API contract (camelCase)."""
        item = ReceiptListItem(
            receiptId="id1",
            status="confirmed",
            merchant="Test",
            total=10.0,
            createdAt="2026-01-01T00:00:00Z",
        )
        data = item.model_dump()
        expected_keys = {
            "receiptId",
            "receiptDate",
            "merchant",
            "total",
            "category",
            "subcategory",
            "categoryDisplay",
            "subcategoryDisplay",
            "status",
            "imageUrl",
            "createdAt",
        }
        assert set(data.keys()) == expected_keys


# ---------------------------------------------------------------------------
# ReceiptListResponse
# ---------------------------------------------------------------------------


class TestReceiptListResponse:
    """Tests for the paginated receipts list response."""

    def test_empty_response(self):
        resp = ReceiptListResponse(receipts=[])
        assert resp.receipts == []
        assert resp.nextCursor is None

    def test_response_with_cursor(self):
        resp = ReceiptListResponse(
            receipts=[
                ReceiptListItem(
                    receiptId="id1",
                    status="confirmed",
                    createdAt="2026-01-01T00:00:00Z",
                )
            ],
            nextCursor="eyJza...",
        )
        assert resp.nextCursor == "eyJza..."

    def test_null_cursor_when_no_more_results(self):
        """nextCursor should be null if no more results per spec."""
        resp = ReceiptListResponse(
            receipts=[
                ReceiptListItem(
                    receiptId="id1",
                    status="processing",
                    createdAt="2026-01-01T00:00:00Z",
                )
            ],
        )
        assert resp.nextCursor is None

    def test_serialization_includes_next_cursor_key(self):
        """JSON output should always include nextCursor, even if null."""
        resp = ReceiptListResponse(receipts=[])
        data = resp.model_dump()
        assert "nextCursor" in data
        assert "receipts" in data
