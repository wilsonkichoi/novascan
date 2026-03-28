# Source Quality Assessment: Manual Research Materials

**Date:** 2026-03-24
**Purpose:** Honest evaluation of the quality, utility, and issues with materials in `workflow/research/manual/`

---

## Accessibility

No issues. All files were readable — markdown, PNG screenshots, HTML code files, DESIGN.md. Nothing was corrupted, missing, or inaccessible.

---

## Overall Verdict

The manual research materials are **heavily over-engineered, redundant, and partially unreliable**. The most useful artifacts are the Stitch UI mockups and DESIGN.md. The 4 markdown research documents read like AI-generated deep research reports that prioritize impressive-sounding prose over actionable information — and they contain fabricated citations.

---

## File-by-File Assessment

### `notes.md` — Rating: Excellent

The most valuable file in the entire directory. 11 lines that clearly state what the project is, what constraints matter, and what the developer actually wants. Every other file should have been written in service of these requirements. Instead, the 4 research docs largely ignore them.

Key signals from notes.md that the research docs contradict:
- "this is an MVP app, don't over-engineer" → research docs describe an enterprise platform
- "first make it runnable locally and use docker" → research docs never mention local development
- "web app layout optimized for mobile" → research docs specify Flutter
- "deployment should be simple and idempotent" → research docs describe 15+ AWS services

### `1.Shopping App Research & MVP Features.md` — Rating: Poor

**What it does well:**
- Competitive analysis of Ibotta vs Fetch is genuinely useful context
- The feature baseline table at the end has some structure

**Problems:**
- ~250 lines of dense, padded academic prose to convey maybe 50 lines of actual information
- Despite having "MVP Features" in the title, describes a full enterprise product (B2B analytics portal, algorithmic fraud detection with >85% detection rate, real-time anti-stacking technology)
- The "MVP Feature Baseline" includes things like "Automated eReceipt Integration" (OAuth email linking) and "Campaign Attribution Dashboards" — these are not MVP features
- Writing style is unmistakably AI-generated: excessive superlatives ("utterly ubiquitous", "vehemently protecting", "mathematically rigorous equilibrium"), every noun has 2-3 adjectives
- Repetitive — the same points about CPG data imperatives are restated 3-4 times with different words

### `2.AWS Receipt Pipeline Design.md` — Rating: Mixed

**What it does well:**
- The S3 presigned URL mechanics are technically accurate and detailed
- EventBridge vs S3 Event Notifications comparison is genuinely useful
- The Step Functions callback pattern (waitForTaskToken) is well-explained
- Cost table (~$0.002/receipt) is a useful data point
- The architecture diagram (Mermaid) is a good artifact

**Problems:**
- Describes the pipeline as if it's the only valid approach. A single Bedrock multimodal call achieves the same result with 1/6th the complexity.
- The presigned URL section goes into extreme depth on x-amz-tagging header hoisting — useful reference material but not a research finding, it's implementation detail that belongs in Phase 4
- ~280 lines of prose for what could be a 60-line architecture summary + decision table
- Fabricated citations (see below)

### `3.Shopping App Research & Design.md` — Rating: Poor

**What it does well:**
- Analytics data model (Timestream + DynamoDB hybrid) is a valid pattern for scale
- RAG architecture section is technically sound
- Vector database cost comparison table is useful
- Aurora vs OpenSearch Serverless cost analysis is well-reasoned (though Aurora itself has problems — see research.md)

**Problems:**
- Massive scope creep: describes multi-agent chatbot orchestration, Nova Sonic voice interface, RAG pipeline, peer-group benchmarking — none of which belong in an MVP
- 240+ lines, heavily redundant with Docs 1, 2, and 4
- Citations are fabricated (see below)
- The Google Stitch / DESIGN.md / MCP section describes an automated pipeline that doesn't exist in production
- Recommends Amazon Timestream without acknowledging its limited community or uncertain future

### `4.AWS Serverless Receipt Scanner Architecture.md` — Rating: Mixed

**What it does well:**
- Best single document for understanding the full intended architecture
- Conflict resolution section (3 conflicts identified and resolved) is genuinely valuable
- System architecture diagram captures the full data flow
- Serves as a useful "north star" for what the full product could eventually look like

**Problems:**
- Describes the final state of a mature product, not an MVP
- Mentions technologies without critical evaluation (Timestream, Aurora Serverless v2 scaling claims)
- Short at ~120 lines but extremely dense — hard to separate the useful architectural decisions from the aspirational features

### `stitch_receipt_scanner/` — Rating: Excellent

**The most actionable artifacts in the entire research directory.**

- 10 high-fidelity UI mockups (PNG screenshots) covering desktop + mobile
- Corresponding HTML/CSS code for each screen
- `DESIGN.md` with a concrete, implementable design system (colors, typography, spacing, component rules)
- The mockups directly show what the MVP screens should look like
- The "Digital Curator" aesthetic is sophisticated and distinctive

**Minor issues:**
- Mockups use the name "Lumina Ledger" — needs to be reconciled with actual project name
- Some mockups show features beyond MVP scope (anomaly detection, subscription tracking, peer benchmarking)

---

## Cross-Cutting Issues

### 1. Fabricated Citations (Critical)

Multiple documents cite sources that are completely unrelated to the topic. Examples from Doc 3:

| Ref # | Cited As | Actual URL Content |
|---|---|---|
| 1 | (supports claim about research phase methodology) | "Ultimate School Brand Development Guide" — a school marketing agency |
| 2 | (supports claim about business objectives) | "belred arts district project" — a Bellevue, WA city government PDF |
| 4 | (supports claim about spending data) | "PS-II Chronicles" — BITS Pilani university internship report |
| 5 | (supports claim about user engagement) | "Bachelor's in Computer Applications handbook" — K.R. Mangalam University |
| 6 | (supports claim about serverless architecture) | "ClickHouse Cloud" — a Hacker News thread |

This pattern appears across all 4 documents. The technical content is generally sound, but the citations are unreliable. This strongly suggests the documents were generated by an AI model (likely Google's Gemini via Deep Research or similar) that hallucinated citation links.

**Impact:** Cannot use these citations as authoritative sources. The AWS documentation links (Textract, Bedrock, Step Functions) are generally accurate, but any non-AWS citation should be independently verified before relying on it.

### 2. Extreme Redundancy

The same topics are covered across multiple documents with slightly different framing:

| Topic | Covered In |
|---|---|
| Scale-to-zero economics | Docs 1, 2, 3, 4 |
| Google Stitch / "vibe design" | Docs 1, 3 |
| Textract + Nova pipeline | Docs 1, 2, 4 |
| Constrained decoding | Docs 1, 2 |
| EventBridge vs S3 notifications | Doc 2, Doc 4 |
| Fetch vs Ibotta comparison | Doc 1 (+ echoed in Doc 4) |
| DynamoDB + Timestream hybrid | Docs 3, 4 |

A single 100-line document could have captured all unique findings from the four 200+ line documents.

### 3. Missing Practical Information

Despite ~900+ lines of research, the documents never address:

- How to set up the project locally
- What the actual REST/GraphQL API contract looks like
- Concrete database schema (just vague PK/SK patterns)
- Error handling and retry strategies
- Testing approach
- Deployment automation (IaC tool selection)
- CI/CD pipeline
- Logging and monitoring
- Cost alerting / budget guardrails
- Data backup and recovery

These are all things an MVP developer actually needs to know.

### 4. Tone Mismatch

The documents are written in an academic/enterprise consulting style with excessive formality. Phrases like "the commercial viability of a modern receipt scanning application is entirely dependent on its ability to generate actionable, high-fidelity data for its enterprise partners" are not helpful for someone who wants to build a receipt scanner. The information density per paragraph is low.

---

## Recommendations for Future Research Phases

1. **Start from `notes.md` constraints, not from market analysis.** The research docs would have been far more useful if they started with "given these constraints, what's the simplest viable architecture?" instead of "here's everything about the CPG data marketplace opportunity."

2. **Separate aspirational vision from MVP scope.** The full architecture (Doc 4) is a fine north-star document. But it should be explicitly labeled "future state" with a separate "MVP architecture" that's 1/4 the complexity.

3. **Verify AI-generated citations.** If using AI research tools (Gemini Deep Research, Perplexity, etc.), spot-check at least 20% of citations before including them. The hallucinated citations undermine trust in the entire document.

4. **Prefer tables and bullet points over prose.** A comparison table conveys information 10x faster than four paragraphs restating the same trade-off.

5. **The Stitch mockups are the gold standard.** Concrete, visual, directly implementable. More research should follow this pattern — show what you want, not just describe it abstractly.
