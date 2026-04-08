# Task 4.1: Category Constants + Receipt CRUD Endpoints

## Work Summary
- **Branch:** `task/4.1-category-receipt-crud` (based on `feature/m4-wave1-receipt-crud`)
- **What was implemented:** Added predefined category taxonomy (all 13 categories with subcategories from category-taxonomy.md) to constants.py with helper functions. Created Category/CustomCategory Pydantic models. Implemented four new receipt CRUD endpoints: GET /api/receipts/{id} (detail with line items), PUT /api/receipts/{id} (partial update with category validation), DELETE /api/receipts/{id} (cascade delete DDB + S3), PUT /api/receipts/{id}/items (bulk replace line items).
- **Key decisions:**
  - Category validation on PUT allows unknown slugs to pass through (could be custom categories that require a DB lookup to validate; full custom category validation deferred to Task 4.2 where the categories API is implemented)
  - Subcategory validation only checks against predefined taxonomy when a predefined category is also provided in the same request
  - Used `ConditionExpression=Attr("PK").exists()` on update to return 404 for non-existent receipts
  - Extracted `_get_user_id()`, `_error_response()`, `_generate_image_url()`, and `_build_receipt_detail()` helpers in receipts.py to share across list/get/update/delete endpoints
  - Display names for category/subcategory resolved from constants at write time (on PUT) and read time (on GET)
  - GSI1SK updated when receiptDate changes on PUT to maintain date-based sort order
- **Files created/modified:**
  - `backend/src/novascan/models/category.py` (created -- Category, Subcategory, CustomCategoryRequest, CustomCategoryResponse)
  - `backend/src/novascan/shared/constants.py` (modified -- added PREDEFINED_CATEGORIES dict + helper functions)
  - `backend/src/novascan/models/receipt.py` (modified -- added ReceiptDetail, ReceiptUpdateRequest, LineItemsUpdateRequest, LineItemInput, ReceiptDetailLineItem)
  - `backend/src/novascan/api/receipts.py` (modified -- added GET/{id}, PUT/{id}, DELETE/{id}, PUT/{id}/items endpoints)
- **Test results:** 386 passed, 0 failed. Ruff lint clean. All existing tests unaffected.
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only -- never overwrite previous entries.}
