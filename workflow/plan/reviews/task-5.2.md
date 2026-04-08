# Task 5.2: Transactions Endpoint

## Work Summary
- **Branch:** `task/5.2-transactions-endpoint` (based on `feature/m5-wave1-backend-apis`)
- **What was implemented:** GET /api/transactions endpoint providing a flattened ledger-style view of receipt data with support for date range filtering, category/status/merchant filters, three sort modes (date via native GSI1, amount and merchant via in-memory sort), cursor-based pagination, and totalCount.
- **Key decisions:**
  - For `sortBy=date`, used native GSI1 ordering with DynamoDB cursor pagination and a separate Count query for totalCount.
  - For `sortBy=date` with merchant search, switched to in-memory pagination since merchant substring match requires fetching all records for accurate totalCount.
  - For `sortBy=amount|merchant`, fetched all matching records, sorted in-memory, and derived totalCount from the fetched set (no separate Count query needed, as specified in the task).
  - Cursor for in-memory-sorted results encodes the last item's GSI1PK/GSI1SK/PK/SK and locates position by linear scan. Acceptable at MVP scale.
  - Category/subcategory display names resolved from stored `categoryDisplay`/`subcategoryDisplay` attributes first, falling back to taxonomy lookup.
  - Did NOT use pandas (removed in Task 3.17). All processing is plain Python.
- **Files created/modified:**
  - `backend/src/novascan/api/transactions.py` (created)
  - `backend/src/novascan/api/app.py` (modified -- registered transactions router)
- **Test results:**
  - `ruff check src/` -- PASS
  - `mypy src/novascan/api/transactions.py` -- PASS (0 errors)
  - `pytest tests/` -- PASS (482 passed)
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only -- never overwrite previous entries.}
