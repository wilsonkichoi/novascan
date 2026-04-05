# Wave 2 Review -- Milestone 3: Pipeline Lambdas

**Reviewer:** code-reviewer (AI)
**Date:** 2026-04-04
**Branch:** `feature/m3-wave2-pipeline-lambdas`
**Base:** `main`

---

## Task 3.2: OCR-AI Pipeline Lambdas

### Spec Compliance

`textract_extract.py` correctly calls `analyze_expense` (sync) with `S3Object` and returns raw `ExpenseDocuments`. Output shape matches what `nova_structure.py` expects as input.

`nova_structure.py` correctly receives Textract output, reads the image from S3, builds an extraction prompt with taxonomy + custom categories + Textract text, calls Bedrock Nova, and parses the response into `ExtractionResult`. The prompt assembly via `build_extraction_prompt(textract_output=...)` matches the SPEC Section 3 description of the OCR-AI path.

`prompts.py` embeds the full 13-category taxonomy matching `category-taxonomy.md` exactly (all slugs verified). Custom category injection follows the SPEC: "appends them to the predefined taxonomy in the structured JSON prompt". The extraction schema matches SPEC Section 7. All 8 AI assignment rules from `category-taxonomy.md` Section "AI Assignment Rules" are encoded in the prompt instructions.

Both handlers return error payloads (`{"error": ..., "errorType": ...}`) instead of raising, which is correct for Step Functions Catch blocks.

### Code Quality

Strong implementation overall:

- Clean separation of concerns: `prompts.py` owns all prompt construction, `textract_extract.py` is a thin Textract wrapper, `nova_structure.py` handles Bedrock orchestration.
- Good use of Lambda Powertools: `Logger`, `Tracer`, `@inject_lambda_context`, `@capture_lambda_handler`, `@capture_method` on all I/O functions.
- `_format_textract_output` produces a human-readable summary from raw Textract JSON that Nova can reason over -- good design for the text+vision multimodal prompt.
- Markdown fence stripping in `_parse_response` is a practical defensive measure for LLM output.
- `_infer_media_type` defaults to JPEG, which is reasonable for receipt images.

### Issues Found

**SUGGESTION: Duplicated helper functions across `nova_structure.py` and `bedrock_extract.py`.**
`_read_image_from_s3`, `_infer_media_type`, `_call_bedrock`, and `_parse_response` are identical (or nearly -- one trivial whitespace difference in `_parse_response`) between the two files. This is ~80 lines of duplicated logic. Given the project rule of "three similar lines > one unnecessary helper," this is borderline acceptable since there are only two copies. However, if these ever need a bug fix (e.g., adding WebP support to `_infer_media_type` or fixing the Bedrock request format), both files need identical changes. Consider extracting shared helpers into a `pipeline/_bedrock_helpers.py` module.

**NIT: `textract_extract.py` extracts `bucket`/`key` with `.get()` defaults (line 48-49) but `bedrock_extract.py` uses `event["bucket"]` (line 67-68) for the same fields.**
Both are valid approaches, but the inconsistency is notable. The task-3.3 review file explains the design choice (missing required fields should error), which is the stronger pattern. `textract_extract.py` would silently pass empty strings to Textract, which would then fail with a less clear error.

---

## Task 3.3: AI-Multimodal Pipeline Lambda

### Spec Compliance

`bedrock_extract.py` correctly implements the shadow pipeline path: reads image from S3, constructs a multimodal prompt (image + taxonomy, no Textract), calls Bedrock Nova, and parses into `ExtractionResult`. This matches SPEC Section 3: "Lambda sends image to Bedrock Nova (multimodal) with structured JSON prompt that includes both predefined taxonomy and user's custom categories."

Correctly reuses `build_extraction_prompt` from `prompts.py` without `textract_output`, triggering the image-only instruction path. No prompt logic duplication.

Error payload pattern is consistent with Task 3.2.

### Code Quality

Clean, well-structured handler. Same Powertools patterns as 3.2. Docstrings document the event shape and return shapes clearly.

The `model_dump_json()` -> `json.loads()` pattern on line 104 is used for serialization, which correctly handles `date` -> ISO string conversion before returning to Step Functions. This is consistent across all pipeline Lambdas.

### Issues Found

No blockers or suggestions specific to this file beyond the cross-file duplication noted in Task 3.2.

---

## Task 3.4: Finalize Lambda + LoadCustomCategories

### Spec Compliance

**Main/shadow selection logic** (lines 184-206): Correct per SPEC Section 3:
- Main succeeded -> use main, status `confirmed`
- Main failed + shadow succeeded -> use shadow, `usedFallback: true`, status `confirmed`
- Both failed -> status `failed`

**Ranking** (lines 209-248): Correct per SPEC -- runs on both results regardless of selection, stores `rankingWinner`, data collection only, does not affect display.

**GSI1SK update** (lines 360-362): Correctly updates `GSI1SK` from createdAt to `{receiptDate}#{receiptId}` when `receiptDate` is extracted. Format matches SPEC Section 5 GSI1 definition.

**Line items** (lines 387-428): Correctly creates `RECEIPT#{ulid}#ITEM#{nnn}` with 3-digit zero-padded sort order starting from 001. Uses `batch_writer` for efficient bulk writes. Includes `entityType: ITEM`.

**Pipeline result storage** (lines 252-302): Both pipeline results stored as `PIPELINE#ocr-ai` and `PIPELINE#ai-multimodal` records with `extractedData`, `confidence`, `rankingScore`, `processingTimeMs`, `modelId`, `createdAt`.

**S3 metadata update** (lines 431-461): Correctly uses `copy_object` with `MetadataDirective: REPLACE`, preserves `ContentType`, non-critical failure handling.

**LoadCustomCategories** (lines 69-100): Correctly queries `PK=USER#{userId}`, `SK begins_with CUSTOMCAT#`. Returns pass-through event with `customCategories` appended. Extracts slug from SK correctly.

**Float-to-Decimal conversion** (lines 496-504): `_convert_floats_to_decimal` recursively converts floats. Individual numeric fields also use explicit `Decimal(str(value))`.

### Code Quality

The finalize handler is the most complex Lambda in the pipeline and is well-organized. The flow is linear and readable: parse -> select -> metrics -> rank -> persist pipeline results -> update receipt -> create line items -> update S3 -> final metrics.

Good defensive handling: S3 metadata update is wrapped in try/except (non-critical), DynamoDB reserved word `status` uses expression attribute name `#status`.

`ranking.py` has sensible weights (confidence 0.40, completeness 0.25, consistency 0.20, line items 0.15). The consistency check with 5% tolerance and linear degradation to 0.5 max discrepancy is reasonable. Neutral 0.5 score for missing line items is a good default.

### Issues Found

**BLOCKER: `MetricUnit.None_` does not exist -- will crash at runtime.**
File: `backend/src/novascan/pipeline/finalize.py`, line 239.
```python
metrics.add_metric(name="RankingScoreDelta", unit=MetricUnit.None_, value=delta)
```
`MetricUnit` does not have a `None_` attribute. The correct attribute is `MetricUnit.NoUnit`. This will raise `AttributeError` at runtime whenever both pipelines produce valid results and ranking runs. Since ranking runs on every successful receipt, this will crash the Finalize Lambda for the majority of receipts.
**Fix:** Change `MetricUnit.None_` to `MetricUnit.NoUnit`.

**BLOCKER: `_emit_pipeline_metrics` dimension overwrite causes incorrect metric attribution.**
File: `backend/src/novascan/pipeline/finalize.py`, lines 464-484.
The function iterates over both pipelines calling `metrics.add_dimension(name="PipelineType", value=pipeline_type)` in a loop. Powertools `Metrics` overwrites dimensions with the same name -- confirmed by the `PowertoolsUserWarning: Dimension 'PipelineType' has already been added. The previous value will be overwritten.` warning. This means both `PipelineCompleted` metric entries get flushed with the **last** pipeline's dimension values (shadow), not their own. The main pipeline's metrics are lost or misattributed.

Additionally, the dimensions set in `_emit_pipeline_metrics` (`PipelineType`, `Outcome`) persist on the shared `metrics` singleton and pollute later metric calls in `_rank_and_get_winner` (which adds `Winner` dimension) and `_emit_receipt_metrics` (which adds `Status` dimension). All metrics emitted in a single Lambda invocation share the **same** dimension set at flush time.

**Fix:** CloudWatch Embedded Metric Format (EMF) dimensions are applied at flush time to ALL metrics in the namespace. To emit per-pipeline metrics correctly, either:
(a) Use `metrics.add_metadata()` instead of dimensions for the per-pipeline breakdown, and emit a single aggregate metric. Or
(b) Use `single_metric` context manager from Powertools to emit each pipeline's metrics independently with their own dimensions:
```python
from aws_lambda_powertools.metrics import single_metric, MetricUnit

for raw, pipeline_type in [(main_raw, main_type), (shadow_raw, shadow_type)]:
    succeeded = "error" not in raw
    outcome = "success" if succeeded else "failure"
    with single_metric(name="PipelineCompleted", unit=MetricUnit.Count, value=1, namespace="NovaScan") as metric:
        metric.add_dimension(name="PipelineType", value=pipeline_type)
        metric.add_dimension(name="Outcome", value=outcome)
    if succeeded and "processingTimeMs" in raw:
        with single_metric(name="PipelineLatency", unit=MetricUnit.Milliseconds, value=raw["processingTimeMs"], namespace="NovaScan") as metric:
            metric.add_dimension(name="PipelineType", value=pipeline_type)
```
The same approach should be used for `_rank_and_get_winner` and `_emit_receipt_metrics` to prevent dimension pollution across metric calls.

**SUGGESTION: `load_custom_categories` handler has no error handling -- will raise unhandled on DynamoDB failure.**
File: `backend/src/novascan/pipeline/load_custom_categories.py`.
Unlike the pipeline Lambdas (textract_extract, nova_structure, bedrock_extract), `load_custom_categories` does not wrap its handler in try/except and does not return error payloads. If DynamoDB is unreachable or the query fails, the Lambda raises unhandled, which causes the Step Functions execution to fail at the first step (before any pipeline work starts). The SPEC says "Each branch has a Catch block" for the parallel branches, but `LoadCustomCategories` runs **before** the parallel branches, so its failure mode depends on the Step Functions definition. If the state machine does not have a Catch on the `LoadCustomCategories` step, an unhandled error here will fail the entire execution.

This may be acceptable (if custom categories can't be loaded, there's no point continuing), but it should be a deliberate choice. Consider either:
(a) Adding try/except with an error payload return, like the pipeline Lambdas, and handling it in the state machine. Or
(b) Documenting that this is intentional (fail-fast) and ensuring the Step Functions definition has appropriate error handling.

**SUGGESTION: `load_custom_categories` does not paginate DynamoDB query results.**
File: `backend/src/novascan/pipeline/load_custom_categories.py`, lines 77-81.
`table.query()` returns at most 1MB of data per call. If a user has enough custom categories to exceed 1MB (unlikely at MVP scale but theoretically possible), subsequent pages are silently dropped. At MVP scale (~100 users) this is not a real risk, but adding a pagination loop is a trivial defensive measure:
```python
items = []
kwargs = {"KeyConditionExpression": ...}
while True:
    response = table.query(**kwargs)
    items.extend(response.get("Items", []))
    if "LastEvaluatedKey" not in response:
        break
    kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
```

**SUGGESTION: `_compute_field_completeness` in `ranking.py` counts default values as "present".**
File: `backend/src/novascan/pipeline/ranking.py`, lines 71-92.
Fields with Pydantic defaults (`currency="USD"`, `category="other"`) always count as present in the completeness check. A minimal `ExtractionResult(merchant={"name": "Test"})` scores 0.67 completeness (6/9 fields: merchant.name, category, currency, subtotal=0.0, tax=0.0, total=0.0 all count as present). This inflates completeness scores for results where most fields were never actually extracted. Whether this is a problem depends on interpretation -- if the ranking is purely comparative (both pipelines get the same inflation), it cancels out. But if you ever use completeness scores in isolation, they'll be misleading.

**NIT: Ranking score is computed twice for each pipeline result.**
File: `backend/src/novascan/pipeline/finalize.py`.
`rank_results()` is called once in `_rank_and_get_winner` (line 220-221) and again in `_write_pipeline_record` (line 279). The function is pure and deterministic, so this is a correctness non-issue, but it doubles the computation. Consider computing once and passing the scores through.

---

## Verification Results

```
ruff check: All checks passed
mypy: 17 errors (see details below)
pytest: 144 passed in 3.68s
```

**mypy errors breakdown:**
- 10 `import-untyped` errors: The `novascan` package lacks `py.typed` marker. This is a known project-wide issue (not introduced by this wave). Pre-existing.
- 4 `no-any-return` errors: Functions returning `dict[str, Any]`, `str`, or `float` where mypy cannot verify the return type through untyped imports. Pre-existing pattern.
- 1 `attr-defined` error on `MetricUnit.None_` (line 239 of `finalize.py`): **This is a real bug** -- confirms the BLOCKER finding above.

**No new test failures.** The 144 existing tests all pass. However, there are **no tests for any of the new pipeline Lambda handlers** in this wave. The task review files only show import verification (`python -c "from ... import handler; print('PASS')"`), not behavioral tests. This is a gap -- these are the core processing pipeline functions. Unit tests with mocked AWS services (moto for DynamoDB/S3, stubbed Textract/Bedrock responses) should be added for Wave 3 or 4.

---

## Verdict

**CONDITIONAL PASS** -- two BLOCKERs must be fixed before merge.

The pipeline Lambda implementations are well-structured, spec-compliant, and demonstrate strong code quality patterns (Powertools usage, error payloads, Pydantic validation, float-to-Decimal conversion). The prompt template is comprehensive and matches the spec exactly. The finalize Lambda correctly implements the main/shadow selection, ranking, GSI1SK update, line item creation, and S3 metadata update.

The two blockers are both in `finalize.py` and both relate to CloudWatch metrics:
1. `MetricUnit.None_` will crash at runtime (trivial fix)
2. Dimension overwrite in `_emit_pipeline_metrics` will silently produce incorrect metric data (requires refactoring to `single_metric` pattern)

---

## Fix Plan

### BLOCKER 1: `MetricUnit.None_` -> `MetricUnit.NoUnit`

**File:** `backend/src/novascan/pipeline/finalize.py`, line 239
**Change:** Replace `MetricUnit.None_` with `MetricUnit.NoUnit`
**Verification:** `cd backend && uv run python -c "from aws_lambda_powertools.metrics import MetricUnit; print(MetricUnit.NoUnit)"`

### BLOCKER 2: Metrics dimension overwrite / pollution

**File:** `backend/src/novascan/pipeline/finalize.py`, functions `_emit_pipeline_metrics`, `_rank_and_get_winner`, `_emit_receipt_metrics`
**Changes:**
1. Refactor `_emit_pipeline_metrics` to use `single_metric` context manager per pipeline iteration instead of the shared `metrics` singleton.
2. Refactor the metric calls in `_rank_and_get_winner` (lines 237-239) to use `single_metric`.
3. Refactor `_emit_receipt_metrics` to use `single_metric`.
4. Import `single_metric` from `aws_lambda_powertools.metrics`.
5. Remove `@metrics.log_metrics(capture_cold_start_metric=True)` from the handler decorator since all metrics are now emitted via `single_metric`. Alternatively, keep it for cold start tracking but ensure the shared `metrics` instance does not accumulate stale dimensions.
**Verification:** `cd backend && uv run ruff check src/ && uv run mypy src/ && uv run pytest -v`

### SUGGESTION: `load_custom_categories` error handling

**File:** `backend/src/novascan/pipeline/load_custom_categories.py`
**Change:** Wrap handler body in try/except and return error payload on failure, consistent with all other pipeline Lambdas. This lets the Step Functions definition decide how to handle the error.
**Verification:** Manual review of Step Functions state machine definition once created.

### SUGGESTION: `load_custom_categories` pagination

**File:** `backend/src/novascan/pipeline/load_custom_categories.py`, function `_query_custom_categories`
**Change:** Add a pagination loop to handle `LastEvaluatedKey`.

---

## Review Discussion

**What went well:**
- Prompt engineering in `prompts.py` is thorough -- all 13 categories, all subcategories, custom category injection, 8 assignment rules. This is the heart of extraction quality.
- The `build_extraction_prompt` function elegantly handles both pipeline paths (with/without Textract output) via a single `textract_output` parameter.
- Float-to-Decimal conversion is correctly handled in all DynamoDB write paths.
- The ranking algorithm is well-designed with sensible weights and a neutral default for missing data.
- Error payload pattern is consistent across all pipeline Lambdas (except `load_custom_categories`).
- GSI1SK update logic correctly reformats to `{receiptDate}#{receiptId}` format per SPEC.

**Missing test coverage:**
No behavioral tests exist for any of the 7 new files. At minimum, these should be added:
- `ranking.py`: Pure function, trivially unit-testable. Test edge cases (no line items, zero totals, all fields present vs minimal).
- `load_custom_categories.py`: Test with mocked DynamoDB (moto).
- `finalize.py`: Test main/shadow selection logic, line item creation, GSI1SK update.
- `prompts.py`: Test `build_extraction_prompt` with/without custom categories, with/without textract output.

These can be scheduled as a dedicated testing task in Wave 3 or 4.

### Fix Plan Analysis (code-reviewer AI — 2026-04-04)

**Verdict:** approve

**BLOCKER 1: `MetricUnit.None_` -> `MetricUnit.NoUnit`**

Confirmed correct. `MetricUnit.None_` raises `AttributeError` at import time (verified). `MetricUnit.NoUnit` exists and maps to CloudWatch's `"None"` unit, which is the standard unitless metric type. This is the right replacement. Trivial one-line fix.

**BLOCKER 2: Metrics dimension overwrite / pollution — `single_metric` approach**

Confirmed correct. The `single_metric` context manager is the idiomatic Powertools solution for this exact problem. Each `single_metric` block creates an isolated `SingleMetric` instance, adds the metric and dimensions, and flushes immediately on context exit — producing a separate EMF log line per metric. This prevents:
1. Dimension overwrite within the loop (main pipeline dimensions are no longer clobbered by shadow pipeline dimensions).
2. Dimension pollution across metric functions (dimensions from `_emit_pipeline_metrics` cannot leak into `_rank_and_get_winner` or `_emit_receipt_metrics`).

Important implementation detail verified: `single_metric` only emits the one metric it was initialized with — additional `add_metric` calls inside the context are silently dropped. The fix plan's code correctly uses separate `single_metric` blocks for `PipelineCompleted` and `PipelineLatency`, which is the right pattern.

Regarding the `@metrics.log_metrics(capture_cold_start_metric=True)` decorator: the fix plan correctly identifies the tension here. If all metrics move to `single_metric`, the shared `metrics` instance will have no metrics to flush at handler exit, which is fine — `log_metrics` will just emit the cold start metric on first invocation and nothing else. Keeping the decorator purely for `capture_cold_start_metric=True` is acceptable and simpler than reimplementing cold start detection manually. The fix should keep the decorator.

**SUGGESTION: `load_custom_categories` error handling**

The proposed try/except wrapper is the right approach. `load_custom_categories` runs as a Step Functions Task state *before* the Parallel state. If it raises unhandled, Step Functions marks the entire execution as failed with a Lambda error. Adding a try/except that returns `{"error": ..., "errorType": ...}` makes the failure mode consistent with all other pipeline Lambdas and gives the state machine definition the option to handle it via a Catch block or Choice state.

One nuance: unlike the other pipeline Lambdas where an error payload is gracefully handled downstream (finalize treats them as "pipeline failed"), a `load_custom_categories` error payload would need explicit handling in the state machine definition (it can't just be passed through to the pipelines as-is). The fix should document this dependency — the state machine definition (presumably in a later CDK task) needs to either add a Catch on this state or check for the error field before entering the Parallel state.

That said, the alternative (fail-fast, let the execution error out) is also defensible for MVP. Custom categories are optional prompt enrichment — if DynamoDB is down, the pipelines would fail later anyway when finalize tries to write results. The try/except is marginally better because it produces a cleaner error message in the Step Functions execution history.

**SUGGESTION: `load_custom_categories` pagination**

The proposed pagination loop is correct and follows the standard boto3 pattern. The `LastEvaluatedKey` / `ExclusiveStartKey` loop is the canonical way to paginate DynamoDB queries. At MVP scale (likely <20 custom categories per user), this will never trigger, but it is a trivial defensive measure that prevents a silent data truncation bug if a user somehow accumulates many categories. The code in the fix plan is correct as written.

**SUGGESTION: `_compute_field_completeness` counts defaults as present**

The review correctly identifies that Pydantic defaults inflate completeness scores. The fix plan does not propose a change for this item, which is appropriate — since ranking is purely comparative (both pipelines get the same inflation), the scores cancel out. This is a known limitation, not a bug. No action needed for MVP.
