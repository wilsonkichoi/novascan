"""POST /api/receipts/upload-urls — generate presigned S3 upload URLs."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import ValidationError
from ulid import ULID

from novascan.models.receipt import UploadReceiptResponse, UploadRequest, UploadResponse
from novascan.shared.constants import RECEIPT
from novascan.shared.dynamo import get_table

logger = Logger()
tracer = Tracer()
router = Router()  # type: ignore[no-untyped-call]
s3_client = boto3.client("s3")


@router.post("/api/receipts/upload-urls")
@tracer.capture_method
def upload_urls() -> Response[Any]:
    """Generate presigned S3 PUT URLs for receipt image uploads.

    Creates a DynamoDB receipt record (status=processing) for each file,
    then returns presigned URLs for direct-to-S3 upload.
    """
    try:
        request = UploadRequest(**router.current_event.json_body)
    except ValidationError as e:
        # L4 — Sanitize Pydantic ValidationError: return field-level errors only
        logger.warning("Upload validation failed", extra={"error_count": e.error_count()})
        sanitized_errors = [
            {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in e.errors()
        ]
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": {"code": "VALIDATION_ERROR", "details": sanitized_errors}}),
        )
    except (TypeError, json.JSONDecodeError) as e:
        logger.warning("Upload request parse error", extra={"error_type": type(e).__name__})
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": {"code": "VALIDATION_ERROR", "message": "Invalid request body"}}),
        )

    user_id: str = router.current_event.request_context.authorizer.jwt_claim["sub"]  # type: ignore[attr-defined]
    table = get_table()
    bucket = os.environ["RECEIPTS_BUCKET"]
    expiry = int(os.environ.get("PRESIGNED_URL_EXPIRY", "900"))
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    now_date = now.strftime("%Y-%m-%d")

    # Phase 1: Generate receipt IDs and image keys
    receipt_data: list[tuple[str, str, str]] = []  # (receipt_id, image_key, content_type)
    for file_req in request.files:
        receipt_id = str(ULID())
        ext = "jpg" if file_req.contentType == "image/jpeg" else "png"
        image_key = f"receipts/{receipt_id}.{ext}"
        receipt_data.append((receipt_id, image_key, file_req.contentType))

    # Phase 2: Write all DynamoDB records
    with table.batch_writer() as batch:
        for receipt_id, image_key, _content_type in receipt_data:
            batch.put_item(
                Item={
                    "PK": f"USER#{user_id}",
                    "SK": f"RECEIPT#{receipt_id}",
                    "entityType": RECEIPT,
                    "receiptId": receipt_id,
                    "status": "processing",
                    "imageKey": image_key,
                    "createdAt": now_iso,
                    "updatedAt": now_iso,
                    "GSI1PK": f"USER#{user_id}",
                    "GSI1SK": f"{now_date}#{receipt_id}",
                    "GSI2PK": receipt_id,
                }
            )

    # Phase 3: Generate presigned URLs
    receipts = []
    for (receipt_id, image_key, content_type), file_req in zip(receipt_data, request.files, strict=True):
        # M6 — Include ContentLength in presigned URL params so S3 rejects
        # uploads that don't match the declared size.
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": image_key,
                "ContentType": content_type,
                "ContentLength": file_req.fileSize,
            },
            ExpiresIn=expiry,
        )
        receipts.append(
            UploadReceiptResponse(
                receiptId=receipt_id,
                uploadUrl=upload_url,
                imageKey=image_key,
                expiresIn=expiry,
            )
        )

    response = UploadResponse(receipts=receipts)
    return Response(
        status_code=201,
        content_type=content_types.APPLICATION_JSON,
        body=response.model_dump_json(),
    )
