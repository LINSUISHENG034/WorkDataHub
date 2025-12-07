# Epic 6 Mid-Sprint Review: Backflow & Consistency

**Date:** 2025-12-07
**Context:** Review of Stories 6.5-6.7 against `docs/specific/backflow/backflow-mechanism-intent.md`

## 1. Executive Summary
The team has reviewed the existing Tech Spec and completed stories against the newly clarified "Self-Learning & Rule Promotion" intent. The core philosophy is sound, but a critical "Gap of Execution" exists in how the **Resolver** (Story 6.4) and the **Async Job** (Story 6.6) interact with *Normalized* vs. *Raw* names.

## 2. Identified Gaps

### Gap A: The "Lookup Key" Mismatch (Critical)
*   **Intent:** The system upgrades knowledge by caching the **Normalized Name** (P4). Future runs should hit this cache to bypass low-priority lookups.
*   **Current Reality (Story 6.4):** The `CompanyIdResolver` uses `strategy.customer_name_column` for the P4 lookup. If the pipeline passes the **Raw Name** in this column, it will miss the cache entry created by the Backflow mechanism (which stores the Normalized Name).
*   **Risk:** The "Self-Learning" breaks. We learn the lesson (write to DB), but we forget to apply it (lookup fails).
*   **Required Fix:**
    1.  Ensure the pipeline passes a `normalized_name` column to the Resolver.
    2.  Update `ResolutionStrategy` to allow specifying a separate column for P4 (Name) lookup vs P5 (Account Name) lookup, OR ensure the Resolver normalizes the input before P4 lookup.

### Gap B: Async Job Persistence Target (Story 6.6)
*   **Intent:** Async enrichment must result in a high-quality, reusable mapping.
*   **Current Spec:** Mentions updating `company_mapping`.
*   **Refinement:** Must explicitly require that the **Normalized Name** (from the `enrichment_requests` table) is used as the `alias_name` in `company_mapping`, NOT the `raw_name`.

## 3. Story-by-Story Alignment

| Story | Status | Alignment Verdict | Action Items |
|-------|--------|-------------------|--------------|
| **6.4 (Resolver)** | Done | **Partial Mismatch** | **Patch Required:** Modify Resolver to support "Dual Lookup" or explicit Normalized Column config. |
| **6.5 (Enqueue)** | Ready | **Aligned** | Ensure deduplication uses `normalize_for_temp_id` (Already in AC). |
| **6.6 (Async Job)** | Pending | **Needs Refinement** | Update AC to enforce writing `normalized_name` to mapping table. |

## 4. Recommendations

1.  **Proceed with Story 6.5:** The enqueue logic is safe and correct (it captures both raw and normalized names).
2.  **Add Refinement Task:** Before Story 6.6, patch `CompanyIdResolver` to ensure it can actually *hit* the cache entries we are about to generate.
3.  **Update Story 6.6 Spec:** Explicitly define the "Write Back" logic to use Normalized Name.
