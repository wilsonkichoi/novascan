# DR-002: OCR Pipeline — Tiered (Textract + Nova) with A/B Testing

**Phase:** 1 (Research)
**Status:** Decided (design evolved — see Addendum below)
**Date:** 2026-03-25 (updated from 2026-03-24)
**Decision:** Tiered pipeline as primary, architected for A/B testing against single Bedrock call

## Context

The manual research documents describe a multi-step receipt processing pipeline:
1. Upload image to S3
2. EventBridge triggers Step Functions state machine
3. Step Functions invokes Textract Expense API (async with callback pattern)
4. Lambda formats Textract output
5. Nova Lite performs constrained decoding to produce structured JSON
6. Result persisted to S3

Alternatively, modern multimodal models (Amazon Nova, Claude on Bedrock) can accept receipt images directly and produce structured JSON in a single API call.

The developer wants: (1) the tiered pipeline as the primary path, and (2) the ability to A/B test both approaches side by side.

## Options

### Option A: Tiered Pipeline (Textract + Nova) — Selected as primary

**Pros:**
- Textract Expense API is purpose-built for receipts — likely higher accuracy on edge cases
- Cost-optimized at scale (~$0.002/receipt)
- Textract handles spatial/tabular extraction that reduces Nova input tokens
- Can add confidence-based routing (easy receipts → Textract only; hard ones → Nova)

**Cons:**
- Complex orchestration (Step Functions, callback Lambdas, DynamoDB token table)
- 6+ services to configure, monitor, and debug
- Async callback pattern is harder to test locally
- More IaC to manage

### Option B: Single Bedrock Multimodal Call

**Pros:**
- One API call: send image + JSON schema prompt → get structured JSON back
- Dramatically simpler: Lambda receives S3 event, calls Bedrock, stores result
- Easy to test locally (just an HTTP call to Bedrock)
- Constrained decoding still available (Nova supports JSON schema enforcement)
- Faster development

**Cons:**
- Higher per-receipt cost at very high volumes (model processes raw pixels + text)
- Less accurate for severely degraded receipts compared to purpose-built Textract
- Input token count higher (image tokens vs pre-extracted text)
- No built-in confidence scoring

## Decision

**Both.** Tiered pipeline (Option A) as primary, with architecture supporting A/B testing against single Bedrock call (Option B).

### A/B Testing Architecture

Both paths share the same:
- **Input**: S3 image key (from presigned URL upload)
- **Output**: Structured JSON matching the receipt schema (merchant, date, line items, totals, tax, category)
- **Storage**: Same DynamoDB table, same S3 results path

The Step Functions state machine includes a routing choice at the entry point:

```
S3 Upload → EventBridge → Step Functions
    ├── [A/B flag = "tiered"] → Textract → Format → Nova → Store result
    └── [A/B flag = "single"] → Bedrock multimodal call → Store result
```

Routing is controlled by:
- A DynamoDB config item (e.g., `pipeline_mode: "tiered" | "single" | "ab_split"`)
- In `ab_split` mode, a percentage-based split (e.g., 80% tiered, 20% single)
- Both paths log extraction results with a `pipeline_path` attribute for comparison

### Why this works for NovaScan

- At <20 users, the volume is low enough that running both paths on a percentage split has negligible cost impact
- Comparing accuracy and latency between the two paths on real receipts provides empirical data for the final decision
- The shared output schema means the frontend is completely unaware of which path was used
- Can switch to 100% either path via a config change — no code deployment needed

## Consequences

- More upfront infrastructure than a single-path approach
- Step Functions state machine is more complex with the branching logic
- Need to define the shared receipt JSON schema early (this is good — forces contract clarity)
- Both paths must handle the same error/retry semantics
- A/B results should be reviewed periodically to determine if one path can be deprecated

---

## Addendum (2026-03-27) — Design Evolved in SPEC

The A/B routing architecture described above (Step Functions choice state with `pipeline_mode` DynamoDB config and percentage-based splits) was an early Phase 1 proposal. During Phase 2 (Specification), the design was simplified:

**What changed:**
- Both pipelines **always** run in parallel (no routing choice, no percentage split)
- `defaultPipeline` in `cdk.json` controls which pipeline is "main" vs "shadow" (default: `ocr-ai`)
- Main pipeline result is used for the receipt; shadow result is stored for comparison only
- If main fails, shadow is used as fallback (`usedFallback: true`)
- Both results are ranked and stored as `PIPELINE#ocr-ai` and `PIPELINE#ai-multimodal` DynamoDB records

**Why:** Running both always is simpler (no branching logic) and at MVP scale (<100 users) the cost difference is negligible. It also produces comparison data on every receipt, not just a percentage.

The core decision (tiered pipeline + single Bedrock as two paths) is unchanged. Only the routing mechanism was simplified. See SPEC.md Section 3 for the final design.
