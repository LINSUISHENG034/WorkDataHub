# Sprint Change Proposal: HMAC Temporary ID Implementation Fix

**Date:** 2025-12-13
**Status:** Approved (2025-12-13)
**Triggered By:** Implementation gap discovered in Story 6.2
**Reference:** `docs/specific/optimized-requirements/20251212_epic-6.2-temporary-id-implementation-gap.md`

---

## 1. Issue Summary

### Problem Statement

Epic 6 Story 6.2 (Temporary Company ID Generation) implementation diverges from requirements specification:

| Aspect | Requirement | Current Implementation |
|--------|-------------|------------------------|
| **Algorithm** | HMAC-SHA1 hash | Database sequence |
| **Behavior** | Stateless, deterministic | Stateful, non-deterministic |
| **ID Format** | `IN<16-char-Base32>` | `TEMP_<6-digit-number>` |
| **Idempotency** | Same input = same output | Each call = different output |

### Discovery Context

- Discovered during Epic 6.2 implementation code review
- Documented in gap analysis: `20251212_epic-6.2-temporary-id-implementation-gap.md`
- Story 6.2 was marked as `done` in sprint-status.yaml

### Evidence

**Requirement (Epic 6, Story 6.2 Acceptance Criteria):**
```
- Generate stable ID: HMAC_SHA1(WDH_ALIAS_SALT, "company_name") → Base32 encode → IN<16-chars>
- Same input always produces same ID (deterministic)
- Prefix `IN` distinguishes temporary from real company IDs
```

**Current Implementation (`lookup_queue.py:517-521`):**
```python
sql = """
    UPDATE enterprise.temp_id_sequence
    SET last_number = last_number + 1, updated_at = now()
    RETURNING last_number
"""
# Result: "TEMP_000123"
```

### Impact Risks

1. **Non-Idempotent:** Re-running pipeline generates different IDs for same unknown company
2. **Environment Inconsistency:** Staging and Production generate different IDs for identical company names
3. **State Dependency:** Database reset causes ID collisions with previously exported reports

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact Level | Action Required |
|------|--------|--------------|-----------------|
| Epic 6 | done | Medium | Create Patch Story |
| Epic 6.2 | in-progress | None | Continue current work |
| Epic 7 | backlog | Low | Complete fix before starting |

### Story Impact

| Story | Impact | Notes |
|-------|--------|-------|
| 6-2-temporary-company-id-generation-hmac-based | Direct | Requires re-implementation |
| 6-5-enrichmentgateway-integration | Indirect | Calls `get_next_temp_id()` |

### Artifact Conflicts

| Artifact | Conflict Level | Required Changes |
|----------|----------------|------------------|
| PRD | None | No changes needed |
| Architecture | Minor | `temp_id_sequence` table may become obsolete |
| UI/UX | N/A | Backend-only change |
| Tests | Required | Add HMAC determinism tests |
| Environment Config | Required | Add `WDH_ALIAS_SALT` variable |

### Technical Impact

**Files to Modify:**
- `src/work_data_hub/domain/company_enrichment/lookup_queue.py` - Refactor `get_next_temp_id()`
- `src/work_data_hub/domain/company_enrichment/service.py` - Update call site (if applicable)
- `tests/unit/domain/company_enrichment/test_lookup_queue.py` - Add determinism tests

**New Dependencies:**
- Environment variable: `WDH_ALIAS_SALT` (secret, per-deployment)

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

Create a Patch Story to fix the implementation without reopening Epic 6.

### Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | Low - Single method refactor |
| Technical Risk | Low - Clear fix with code example |
| Timeline Impact | Minimal - Can parallel with Epic 6.2 |
| Long-term Sustainability | Improved - Stateless design |
| Business Value | High - Meets original specification |

### Trade-offs Considered

| Alternative | Why Not Selected |
|-------------|------------------|
| Keep current implementation | Violates requirements, long-term maintenance cost |
| Reopen Epic 6 | Over-complicated, Epic already completed |
| Defer to post-Epic 7 | Tests should be based on correct implementation |

### Effort Estimate

- **Complexity:** Low
- **Risk Level:** Low

### Timeline Impact

- No delay to Epic 6.2 or Epic 7
- Can be implemented in parallel with current work

---

## 4. Detailed Change Proposals

### Proposal 4.1: Create Patch Story

**Story ID:** `6-2-p1-hmac-temp-id-implementation`
**Title:** Fix Temporary ID Generation to Use HMAC-SHA1

**Acceptance Criteria:**
1. `get_next_temp_id(company_name: str)` generates ID using HMAC-SHA1
2. Same company name always produces same temporary ID (deterministic)
3. ID format: `IN<16-char-Base32>` (not `TEMP_XXXXXX`)
4. `WDH_ALIAS_SALT` environment variable configured
5. Unit tests verify determinism with 10K unique names
6. No ID collisions in collision test

### Proposal 4.2: Code Refactor

**File:** `src/work_data_hub/domain/company_enrichment/lookup_queue.py`

**OLD (lines 495-587):**
```python
def get_next_temp_id(self) -> str:
    """Generate next temporary ID using atomic sequence increment."""
    # ... database sequence implementation ...
    sql = """
        UPDATE enterprise.temp_id_sequence
        SET last_number = last_number + 1, updated_at = now()
        RETURNING last_number
    """
    # Returns: "TEMP_000123"
```

**NEW:**
```python
import hmac
import hashlib
import base64
import os

def get_next_temp_id(self, company_name: str) -> str:
    """
    Generate stable temporary ID using HMAC-SHA1.

    Same company name always produces same ID (deterministic).

    Args:
        company_name: Company name to generate ID for

    Returns:
        Temporary ID in IN<16-char-Base32> format
    """
    if self.plan_only:
        # Return deterministic mock for plan-only mode
        normalized = company_name.strip().lower() if company_name else "unknown"
        mock_hash = hashlib.sha1(normalized.encode()).hexdigest()[:8]
        return f"IN{mock_hash.upper()}"

    salt = os.getenv("WDH_ALIAS_SALT", "default_dev_salt")
    normalized = company_name.strip().lower()
    digest = hmac.new(salt.encode(), normalized.encode(), hashlib.sha1).digest()
    encoded = base64.b32encode(digest)[:16].decode('ascii')
    return f"IN{encoded}"
```

**Rationale:** Implements HMAC-SHA1 as specified in Story 6.2 requirements

### Proposal 4.3: Update Call Sites

**File:** Any file calling `get_next_temp_id()`

**OLD:**
```python
temp_id = self.lookup_queue.get_next_temp_id()
```

**NEW:**
```python
temp_id = self.lookup_queue.get_next_temp_id(company_name)
```

**Rationale:** Method signature change requires passing company name

### Proposal 4.4: Environment Configuration

**Add to deployment configuration:**
```bash
# .env.example
WDH_ALIAS_SALT=your-secret-salt-here  # REQUIRED: Unique per deployment
```

**Rationale:** Salt must be secret and consistent per environment

### Proposal 4.5: Update sprint-status.yaml

**ADD:**
```yaml
# Patch for Story 6.2 - HMAC temp ID implementation fix
# Added 2025-12-13 via Correct-Course workflow
6-2-p1-hmac-temp-id-implementation: backlog
```

---

## 5. Implementation Handoff

### Change Scope Classification

**Scope:** Minor

This change can be implemented directly by the development team without requiring backlog reorganization or architectural review.

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement code fix, write tests |
| **SM (Scrum Master)** | Create Story file, update sprint-status |
| **Code Reviewer** | Verify HMAC implementation, check determinism |

### Deliverables

1. **Story File:** `docs/sprint-artifacts/stories/6-2-p1-hmac-temp-id-implementation.md`
2. **Code Changes:** Refactored `get_next_temp_id()` method
3. **Tests:** Determinism and collision tests
4. **Config:** `WDH_ALIAS_SALT` environment variable

### Success Criteria

1. Same company name produces identical temporary ID across multiple calls
2. Same company name produces identical ID across different environments (with same salt)
3. 10,000 unique company names produce 10,000 unique IDs (no collisions)
4. All existing tests pass
5. Code review approved

### Dependencies

- Must complete before Epic 7 (Testing & Validation Infrastructure)
- Can run in parallel with Epic 6.2 remaining stories

---

## 6. Approval

**Prepared By:** Claude Code (Correct-Course Workflow)
**Date:** 2025-12-13

### Approval Status

- [x] **Product Owner:** Approved (2025-12-13)
- [x] **Technical Lead:** Approved (2025-12-13)
- [x] **Scrum Master:** Approved (2025-12-13)

### Notes

This is a corrective change to align implementation with original requirements. The fix is low-risk and well-defined, with clear acceptance criteria and code examples.

---

## Appendix: Reference Documents

- Gap Analysis: `docs/specific/optimized-requirements/20251212_epic-6.2-temporary-id-implementation-gap.md`
- Epic 6 Definition: `docs/epics/epic-6-company-enrichment-service.md`
- Current Implementation: `src/work_data_hub/domain/company_enrichment/lookup_queue.py`
