# Company Enrichment Backflow & Priority Promotion Mechanism

**Created:** 2025-12-07
**Context:** Epic 6 - Company Enrichment Service

## Core Philosophy: Self-Learning & Rule Promotion

The Backflow Mechanism is designed to be the "Consistency Anchor" of the WorkDataHub. It transforms the system from a static lookup engine into a **self-learning system** that upgrades its own knowledge base over time.

### 1. The "Clean Source" Principle
Backflow does **not** blindly cache raw inputs.
- **Source:** Data that has successfully passed through the Pipeline's validation and cleansing logic (Silver/Gold layers).
- **Definition:** Only "Clean Customer Names" or authoritative "Account Numbers" associated with a resolved Company ID are candidates for backflow.
- **Trust:** Because the data has been processed and potentially corrected by other logic (or human intervention via config overrides), it is considered high-quality.

### 2. Priority Promotion (The Upgrade Cycle)

The system is designed to "promote" matching rules from low-confidence/specific sources to high-confidence/general sources.

**Scenario:**
1.  **Initial State (Day 1):** A record arrives with a raw account name "Shanghai Branch" and an Account Number "12345".
    *   *Lookup:* Fails P4 (Name). Matches **P5 (Account Name)** or **P2 (Account Number)**.
    *   *Result:* Resolves to `CompanyID: 999`.
2.  **Backflow Action:**
    *   The pipeline holds the clean, normalized name for this company: "Shanghai Branch Ltd."
    *   The system recognizes that "Shanghai Branch Ltd." mapped to `999`.
    *   **Action:** Writes a new mapping to the Database Cache: `{"alias_name": "Shanghai Branch Ltd.", "company_id": "999", "priority": 4 (Name), "source": "backflow"}`.
3.  **Future State (Day 2):** A new file arrives with "Shanghai Branch Ltd.".
    *   *Lookup:* Checks **P4 (Name)** first.
    *   *Result:* **Hit!** Matches "Shanghai Branch Ltd." -> `999`.
    *   *Outcome:* Higher performance (earlier hit), higher consistency, decoupled from the specific Account Number.

### 3. Lookup Strategy: Normalized vs. Raw

To support this consistency, the Resolver must respect the specific matching order dictated by the "Priority Promotion" logic:

1.  **Standardized/Normalized Name (High Priority)**: The system *must* check if the standardized version of the name exists in the high-priority cache (P4). This ensures that if we have already "learned" the standard name, we use it.
2.  **Raw Name (Low Priority)**: If the standard name misses, we fall back to the raw input (e.g., matching via P5 Account Name or P3 Hardcode).

### 4. The Role of Async Enrichment (Closing the Loop)

When **no** match is found (P1-P6 fail):
1.  **Temp ID Generation:** System assigns a stable `IN_...` ID.
2.  **Enqueue:** The *Normalized Name* is sent to the Async Queue (Story 6.5).
3.  **Resolution (Story 6.6):** The Async Worker finds the real ID via EQC.
4.  **Write Back:** The Worker writes `Normalized Name -> Real ID` into the DB Cache (P4/P6).
5.  **Next Run:** The Pipeline treats this as a standard P4 Hit (see "Future State" above).

### Summary
Backflow is not just caching; it is the mechanism by which the system **upgrades** temporary or low-priority associations into permanent, high-priority, standardized knowledge.
