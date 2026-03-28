# NovaScan API Contracts

**Base path:** `/api`
**Protocol:** HTTPS
**Content-Type:** `application/json` (all requests and responses)

---

## Authentication

All endpoints require a valid Cognito JWT in the `Authorization` header:

```
Authorization: Bearer {id_token}
```

API Gateway's Cognito User Pool authorizer validates the token. The `sub` claim identifies the user.

The Pre-Sign-Up Lambda trigger is invoked internally by Cognito — it is not an API endpoint.

---

## Error Response Format

All error responses follow this shape:

```json
{
  "error": {
    "code": "RECEIPT_NOT_FOUND",
    "message": "Receipt with ID 01HQ3K5P7M2N4R6S8T0V does not exist"
  }
}
```

### Error Codes

| HTTP Status | Code | When |
|-------------|------|------|
| 400 | `VALIDATION_ERROR` | Request body or params failed validation |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 403 | `FORBIDDEN` | User does not own this resource |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `CONFLICT` | Duplicate (e.g., custom category slug already exists) |
| 429 | `RATE_LIMITED` | Too many requests (API Gateway default throttle) |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

---

## Endpoints

### POST /api/receipts/upload-urls

Generate presigned S3 PUT URLs for receipt image uploads. Creates receipt records in DynamoDB with status `processing`.

**Request:**

```json
{
  "files": [
    {
      "fileName": "receipt1.jpg",
      "contentType": "image/jpeg",
      "fileSize": 2048576
    }
  ]
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `files` | array | 1–10 items |
| `files[].fileName` | string | 1–255 characters |
| `files[].contentType` | string | `image/jpeg` or `image/png` |
| `files[].fileSize` | integer | 1 – 10,485,760 bytes (10 MB) |

**Response:** `201 Created`

```json
{
  "receipts": [
    {
      "receiptId": "01HQ3K5P7M2N4R6S8T0V",
      "uploadUrl": "https://novascan-dev-receipts.s3.amazonaws.com/receipts/...",
      "imageKey": "receipts/01HQ3K5P7M2N4R6S8T0V.jpg",
      "expiresIn": 900
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `receiptId` | string | ULID assigned to this receipt |
| `uploadUrl` | string | Presigned S3 PUT URL |
| `imageKey` | string | S3 object key where image will be stored |
| `expiresIn` | integer | URL expiration in seconds (900 = 15 minutes) |

**S3 key format:** `receipts/{receiptId}.{ext}` — flat structure, ULID ensures uniqueness

**Upload failure handling:** Frontend uploads each file independently via its presigned URL. Failed uploads are retried up to 3 times with exponential backoff (1s, 2s, 4s). If a presigned URL expires during retry, frontend requests a new URL for the failed file only. After all retries, UI shows per-file success/failure summary.

**Errors:** `400 VALIDATION_ERROR`

---

### GET /api/receipts

List all receipts for the authenticated user.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter: `processing`, `confirmed`, `failed` |
| `category` | string | — | Filter by category slug |
| `startDate` | string | — | Receipts on or after this date (YYYY-MM-DD) |
| `endDate` | string | — | Receipts on or before this date (YYYY-MM-DD) |
| `limit` | integer | 50 | Max results, 1–100 |
| `cursor` | string | — | Pagination cursor from previous response |

**Response:** `200 OK`

```json
{
  "receipts": [
    {
      "receiptId": "01HQ3K5P7M2N4R6S8T0V",
      "receiptDate": "2026-03-25",
      "merchant": "Whole Foods Market",
      "total": 30.39,
      "category": "groceries-food",
      "categoryDisplay": "Groceries & Food",
      "subcategory": "supermarket-grocery",
      "subcategoryDisplay": "Supermarket / Grocery",
      "status": "confirmed",
      "imageUrl": "https://novascan-dev-receipts.s3.amazonaws.com/...",
      "createdAt": "2026-03-25T14:30:00Z"
    }
  ],
  "nextCursor": "eyJza..."
}
```

| Field | Description |
|-------|-------------|
| `imageUrl` | Presigned GET URL, expires in 1 hour |
| `nextCursor` | Opaque pagination token. Null if no more results. |

**Notes:**
- Results sorted by ULID descending (most recent first)
- Cursor-based pagination (not offset)
- Receipts with status `processing` have null values for merchant, total, category

---

### GET /api/receipts/{id}

Get receipt detail including line items.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | string | Receipt ULID |

**Response:** `200 OK`

```json
{
  "receiptId": "01HQ3K5P7M2N4R6S8T0V",
  "receiptDate": "2026-03-25",
  "merchant": "Whole Foods Market",
  "merchantAddress": "123 Main St, Austin, TX 78701",
  "total": 30.39,
  "subtotal": 28.14,
  "tax": 2.25,
  "tip": null,
  "category": "groceries-food",
  "categoryDisplay": "Groceries & Food",
  "subcategory": "supermarket-grocery",
  "subcategoryDisplay": "Supermarket / Grocery",
  "status": "confirmed",
  "usedFallback": false,
  "rankingWinner": "ocr-ai",
  "imageUrl": "https://...",
  "paymentMethod": "VISA *1234",
  "lineItems": [
    {
      "sortOrder": 1,
      "name": "Organic Whole Milk",
      "quantity": 1,
      "unitPrice": 5.99,
      "totalPrice": 5.99,
      "subcategory": "dairy-cheese-eggs",
      "subcategoryDisplay": "Dairy, Cheese & Eggs"
    }
  ],
  "createdAt": "2026-03-25T14:30:00Z",
  "updatedAt": "2026-03-25T14:31:00Z"
}
```

**Errors:** `404 NOT_FOUND`

---

### PUT /api/receipts/{id}

Update receipt-level fields. All fields in the request body are optional — only provided fields are updated.

**Request:**

```json
{
  "merchant": "Whole Foods",
  "merchantAddress": "123 Main St",
  "receiptDate": "2026-03-24",
  "category": "groceries-food",
  "subcategory": "supermarket-grocery",
  "total": 30.39,
  "subtotal": 28.14,
  "tax": 2.25,
  "tip": null,
  "paymentMethod": "VISA *1234"
}
```

**Response:** `200 OK` — full receipt object (same shape as GET /api/receipts/{id})

**Errors:**
- `404 NOT_FOUND`
- `400 VALIDATION_ERROR` — invalid category or subcategory slug

---

### DELETE /api/receipts/{id}

Hard delete a receipt. Removes all DynamoDB records (receipt, line items, pipeline results) and the S3 image.

**Response:** `204 No Content`

**Errors:** `404 NOT_FOUND`

---

### PUT /api/receipts/{id}/items

Bulk replace all line items for a receipt. Deletes all existing line items and inserts the provided list.

**Request:**

```json
{
  "items": [
    {
      "sortOrder": 1,
      "name": "Organic Whole Milk",
      "quantity": 1,
      "unitPrice": 5.99,
      "totalPrice": 5.99,
      "subcategory": "dairy-cheese-eggs"
    },
    {
      "sortOrder": 2,
      "name": "Avocado (Bag of 5)",
      "quantity": 1,
      "unitPrice": 6.50,
      "totalPrice": 6.50,
      "subcategory": "produce"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items` | array | Yes | 0–100 items |
| `items[].sortOrder` | integer | Yes | Display order (1-based) |
| `items[].name` | string | Yes | Item name, 1–200 chars |
| `items[].quantity` | number | Yes | Quantity, > 0 |
| `items[].unitPrice` | number | Yes | Price per unit, >= 0 |
| `items[].totalPrice` | number | Yes | Line total, >= 0 |
| `items[].subcategory` | string | No | Subcategory slug (from parent category's subcategory list) |

**Response:** `200 OK` — full receipt object with updated line items

**Errors:**
- `404 NOT_FOUND`
- `400 VALIDATION_ERROR`

---

### GET /api/transactions

List transactions — a flattened, ledger-style view of receipt data.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `startDate` | string | — | Filter by receipt date (YYYY-MM-DD) |
| `endDate` | string | — | Filter by receipt date |
| `category` | string | — | Filter by category slug |
| `merchant` | string | — | Search merchant name (partial, case-insensitive) |
| `status` | string | — | Filter: `processing`, `confirmed`, `failed` |
| `sortBy` | string | `date` | Sort: `date`, `amount`, `merchant` |
| `sortOrder` | string | `desc` | Direction: `asc`, `desc` |
| `limit` | integer | 50 | Max results, 1–100 |
| `cursor` | string | — | Pagination cursor |

**Response:** `200 OK`

```json
{
  "transactions": [
    {
      "receiptId": "01HQ3K5P7M2N4R6S8T0V",
      "receiptDate": "2026-03-25",
      "merchant": "Whole Foods Market",
      "total": 30.39,
      "category": "groceries-food",
      "categoryDisplay": "Groceries & Food",
      "subcategory": "supermarket-grocery",
      "subcategoryDisplay": "Supermarket / Grocery",
      "status": "confirmed"
    }
  ],
  "nextCursor": "eyJza...",
  "totalCount": 148
}
```

| Field | Description |
|-------|-------------|
| `totalCount` | Total matching transactions (before pagination) |

**Notes:**
- `merchant` search uses case-insensitive substring match
- `sortBy=date` sorts by `receiptDate` (falls back to `createdAt` for receipts without a parsed date)
- Only `confirmed` receipts have meaningful transaction data; `processing`/`failed` have null fields

---

### GET /api/dashboard/summary

Dashboard summary metrics for the authenticated user.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `month` | string | current | Target month (YYYY-MM) |

**Response:** `200 OK`

```json
{
  "month": "2026-03",
  "totalSpent": 2482.50,
  "previousMonthTotal": 2210.75,
  "monthlyChangePercent": 12.3,
  "weeklySpent": 620.75,
  "previousWeekTotal": 580.30,
  "weeklyChangePercent": 7.0,
  "receiptCount": 48,
  "confirmedCount": 45,
  "processingCount": 2,
  "failedCount": 1,
  "topCategories": [
    {
      "category": "groceries-food",
      "categoryDisplay": "Groceries & Food",
      "total": 890.25,
      "percent": 35.9
    }
  ],
  "recentActivity": [
    {
      "receiptId": "01HQ3K5P7M2N4R6S8T0V",
      "merchant": "Whole Foods Market",
      "total": 30.39,
      "category": "groceries-food",
      "categoryDisplay": "Groceries & Food",
      "receiptDate": "2026-03-25",
      "status": "confirmed"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `totalSpent` | Month-to-date total |
| `monthlyChangePercent` | Percentage change vs previous month. Null if no previous month data. |
| `weeklySpent` | Current calendar week total (Monday–Sunday) |
| `weeklyChangePercent` | Percentage change vs previous week. Null if no previous week data. |
| `topCategories` | Up to 5 categories, sorted by total descending (monthly) |
| `recentActivity` | Up to 5 most recent receipts |

**Notes:**
- Aggregation computed with pandas in Lambda at query time (~2s cold start acceptable for MVP)
- Only `confirmed` receipts contribute to totals
- Change percentages are positive for spending increase, negative for decrease
- Weekly is always based on current date, not parameterized

---

### GET /api/categories

List all categories: predefined taxonomy merged with user's custom categories.

**Response:** `200 OK`

```json
{
  "categories": [
    {
      "slug": "groceries-food",
      "displayName": "Groceries & Food",
      "isCustom": false,
      "subcategories": [
        {
          "slug": "supermarket-grocery",
          "displayName": "Supermarket / Grocery"
        },
        {
          "slug": "produce",
          "displayName": "Produce"
        }
      ]
    },
    {
      "slug": "my-custom-cat",
      "displayName": "My Custom Category",
      "isCustom": true,
      "parentCategory": "other",
      "subcategories": []
    }
  ]
}
```

**Notes:**
- Predefined categories are returned first, then custom categories
- Custom categories have `isCustom: true` and an optional `parentCategory` field

---

### POST /api/categories

Create a custom category.

**Request:**

```json
{
  "displayName": "My Custom Category",
  "parentCategory": "other"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `displayName` | string | Yes | 1–100 characters |
| `parentCategory` | string | No | Must be a valid predefined category slug if provided |

**Response:** `201 Created`

```json
{
  "slug": "my-custom-category",
  "displayName": "My Custom Category",
  "parentCategory": "other",
  "isCustom": true
}
```

**Notes:**
- Slug is auto-generated from `displayName` (lowercased, spaces → hyphens, special chars removed)

**Errors:**
- `409 CONFLICT` — slug already exists (predefined or custom)
- `400 VALIDATION_ERROR` — invalid `parentCategory`

---

### DELETE /api/categories/{slug}

Delete a custom category. Predefined categories cannot be deleted.

**Response:** `204 No Content`

**Errors:**
- `404 NOT_FOUND` — category doesn't exist
- `403 FORBIDDEN` — cannot delete predefined categories

**Notes:**
- Receipts assigned to the deleted category retain their category slug. The frontend handles orphaned category references gracefully (display the slug as-is).

---

### GET /api/receipts/{id}/pipeline-results

Get extraction results from both pipeline paths. For A/B comparison and debugging. **Requires `staff` role.**

**Response:** `200 OK`

```json
{
  "receiptId": "01HQ3K5P7M2N4R6S8T0V",
  "usedFallback": false,
  "rankingWinner": "ocr-ai",
  "results": {
    "ocr-ai": {
      "extractedData": {
        "merchant": { "name": "Whole Foods Market", "address": "..." },
        "receiptDate": "2026-03-25",
        "lineItems": [],
        "total": 30.39,
        "category": "groceries-food",
        "subcategory": "supermarket-grocery",
        "confidence": 0.94
      },
      "confidence": 0.94,
      "rankingScore": 0.91,
      "processingTimeMs": 4523,
      "modelId": "amazon.nova-lite-v1:0",
      "createdAt": "2026-03-25T14:30:45Z"
    },
    "ai-multimodal": {
      "extractedData": {
        "merchant": { "name": "Whole Foods", "address": "..." },
        "receiptDate": "2026-03-25",
        "lineItems": [],
        "total": 30.39,
        "category": "groceries-food",
        "subcategory": "supermarket-grocery",
        "confidence": 0.89
      },
      "confidence": 0.89,
      "rankingScore": 0.82,
      "processingTimeMs": 2100,
      "modelId": "amazon.nova-lite-v1:0",
      "createdAt": "2026-03-25T14:30:43Z"
    }
  }
}
```

**Errors:**
- `403 FORBIDDEN` — user does not have `staff` role
- `404 NOT_FOUND`

**Notes:**
- **Requires `staff` role** — non-staff users receive 403
- `usedFallback` — `true` if main pipeline failed and shadow result was used for this receipt
- `rankingWinner` — which pipeline the ranking algorithm scored higher, independent of main/shadow selection
- `rankingScore` — composite score (0–1) per pipeline based on confidence, field completeness, line item count, and total consistency. For studying pipeline performance only.
- `extractedData` follows the Receipt Extraction Schema (SPEC.md Section 7)
- Either `ocr-ai` or `ai-multimodal` may be null if that pipeline path failed
- The frontend pipeline comparison toggle uses this endpoint and is only rendered for staff users
