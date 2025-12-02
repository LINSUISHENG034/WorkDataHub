# Sprint Change Proposal: PRD Quality Enhancement
**Project:** WorkDataHub
**Date:** 2025-11-09
**Prepared by:** John (Product Manager)
**Reviewed with:** Link
**Status:** Pending Approval

---

## Executive Summary

This Sprint Change Proposal addresses four critical gaps and contradictions discovered during proactive PRD quality review. All issues are resolvable through documentation updates and targeted story modifications without requiring scope reduction or rollback. Recommended approach is a hybrid strategy combining direct PRD adjustments with strategic feature deferrals to maintain MVP timeline while resolving all conflicts.

**Impact Level:** Moderate
**Change Scope:** Documentation updates + 7 story modifications
**Timeline Impact:** +10-20 hours documentation work, minimal implementation delay
**Epic Impact:** Epics 1, 2, and 5 affected

---

## Section 1: Issue Summary

### Problem Statement

During proactive PRD review, four significant gaps and contradictions were identified that could cause implementation conflicts, architectural violations, and data governance issues if not addressed before Epic 4-5 implementation:

1. **Missing Rule Governance Mechanism** - FR-3.2 specifies central cleansing registry but lacks version control, change approval workflows, rollback procedures, and audit trail for rule modifications
2. **Missing Transformation Lineage Tracking** - While Bronze preserves original files and exports failed rows, PRD lacks specification for tracking field-level transformations (original→cleaned values, applied rules, approver identity)
3. **Architectural Dependency Conflict** - Clean Architecture section mandates "domain/ imports NOTHING" while FR-3.3 Company Enrichment requires domain layer to access external services (EQC API, Gateway, async queues)
4. **Validation Order Conflict** - FR-1.4 auto-corrects data issues during load (empty rows, type coercion) while Bronze validation philosophy states "reject bad source data immediately," creating ambiguity about execution order

### Discovery Context

**Trigger:** Proactive PRD quality review (not implementation failure)
**Evidence:** All concerns validated against PRD lines 400-446, 739-748, 815-824, 825-859, 898-906
**Brownfield Reality:** Architecture document confirms concern #3 already exists in codebase - `domain/company_enrichment/` currently has external dependencies despite PRD stating zero-dependency rule

### Supporting Evidence

**Concern #1 Evidence (FR-3.2 lines 815-824):**
- ✅ Central registry exists with enable/disable per domain
- ❌ No version control mechanism specified
- ❌ No gradual rollout or A/B testing strategy
- ❌ No rollback procedures documented
- ❌ No audit trail of rule modifications

**Concern #2 Evidence (FR-4.3 lines 898-906):**
- ✅ Logs pipeline execution (timestamp, file path, row counts)
- ❌ No field-level transformation tracking (before→after values)
- ❌ No record of which rules applied to which fields
- ❌ No approver/reviewer identity capture

**Concern #3 Evidence (Architecture lines 400-446 vs FR-3.3 lines 825-859):**
- Line 442: **"domain/ imports from: NOTHING"** (zero dependencies)
- Lines 839-843: FR-3.3 requires Provider abstraction + Gateway with API/database access
- **Brownfield reality:** `domain/company_enrichment/providers.py` already exists with EqcProvider

**Concern #4 Evidence (FR-1.4 lines 739-748 vs Bronze Validation lines 486-502):**
- FR-1.4: Auto-skips empty rows, coerces types, handles merged cells
- Bronze: "Reject bad source data immediately"
- **Conflict:** Many format issues are silently fixed before Bronze validation runs

---

## Section 2: Impact Analysis

### Epic Impact Assessment

**Epic 1 (Foundation & Core Infrastructure) - AFFECTED:**
- Story 1.3 (Logging): Needs transformation audit requirements
- Story 1.6 (Architecture Boundaries): **MAJOR CONFLICT** - must resolve dependency contradiction
- Story 1.8 (Database Loading): May need projection audit tracking

**Epic 2 (Multi-Layer Data Quality Framework) - AFFECTED:**
- Story 2.2 (Bronze Validation): **CONFLICT** - execution order with FR-1.4 unclear
- Story 2.3 (Cleansing Registry): Missing governance features
- Story 2.5 (Error Handling): Missing transformation lineage tracking

**Epic 3 (File Discovery) - Low Impact:**
- May benefit from audit logging enhancements

**Epic 4 (Annuity Migration) - HIGH RISK:**
- Depends on Epic 1.6 architecture decision
- Depends on Epic 2 validation order resolution
- Cannot implement domain transformations until dependency conflict resolved

**Epic 5 (Company Enrichment) - CRITICAL IMPACT / BLOCKED:**
- **Directly affected by architectural dependency conflict**
- FR-3.3 specification contradicts architectural principles
- **Cannot implement as currently specified without violating PRD**
- Brownfield already has partial implementation using Protocol pattern

**Epics 6-10 - Medium Impact:**
- Tests must validate audit trails (Epic 6)
- Orchestration/monitoring will consume audit logs (Epics 7-8)
- Rule governance affects configuration management (Epic 10)

### Artifact Conflict Assessment

**PRD (docs/PRD.md) - 4 Significant Conflicts:**
1. ❌ FR-3.2 (lines 815-824): Lacks rule governance mechanisms
2. ❌ FR-4.3 (lines 898-906): Logs executions but not field transformations
3. ❌ **CRITICAL:** Clean Architecture (lines 441-446) contradicts FR-3.3 (lines 825-859)
4. ❌ FR-1.4 (lines 739-748) auto-correction conflicts with Bronze validation philosophy (lines 486-502)

**Architecture Document (docs/brownfield-architecture.md) - Confirms Reality:**
- Lines 201-333: Company Enrichment Service already implemented with Provider/Gateway pattern
- `domain/company_enrichment/` already has external dependencies (validates concern #3)
- No transformation lineage tracking mentioned (validates concern #2)
- No rule governance mechanisms documented (validates concern #1)

**Epics Document (docs/epics.md) - Stories Require Modification:**
- Only Epics 1-2 have detailed stories
- 7 stories identified as needing updates
- Epic 5 not yet detailed but will be blocked without resolution

**UI/UX Specifications:** N/A (backend system, no UI)

**Secondary Artifacts:**
- Testing strategy needs audit validation coverage
- CI/CD may need architecture dependency checks
- Documentation (README) needs principle clarification
- Configuration schemas may need governance extensions

### Technical Impact

**Database Schema:**
- Phase 2: May need transformation_lineage table for field-level tracking (deferred)
- MVP: No schema changes required

**Code Organization:**
- Brownfield already violates stated architecture rule
- Resolution updates PRD to match reality, no code refactor needed for MVP

**Performance:**
- Audit logging adds minimal overhead (structured logs already planned)
- No performance degradation expected

**Security & Compliance:**
- Enhanced audit trail improves compliance posture
- Transformation lineage supports regulatory requirements (Phase 2)

---

## Section 3: Recommended Approach

### Selected Path: Hybrid Direct Adjustment

**Strategy:** Combine PRD documentation updates (Option 1) with strategic feature deferrals (Option 3 elements) to resolve all conflicts while maintaining MVP timeline.

### Core Components

**1. PRD Updates (Direct Adjustment):**
- FR-3.2: Add rule governance requirements (git-based for MVP, advanced features Phase 2)
- FR-4.3: Expand audit logging to include transformation lineage (pipeline-level MVP, field-level Phase 2)
- Architecture Section: Refine dependency rule to allow Protocol-based abstractions with dependency injection
- FR-1.4 + Bronze Validation: Clarify execution order and document auto-correction scope

**2. Strategic Deferrals (MVP Scope Optimization):**
- **Defer to Phase 2:** Advanced rule governance (versioning, A/B testing, auto-rollback)
- **Defer to Phase 2:** Field-level transformation lineage (before/after tracking)
- **Simplify for MVP:** Use StubProvider for enrichment (defer EQC integration)
- **Benefit:** Reduces implementation complexity while resolving all PRD conflicts

**3. Architecture Decision (Concern #3 Resolution):**
- **Accept brownfield reality:** Domain layer CAN have dependencies when using Protocol/Provider pattern
- **Update PRD:** Refine from "imports NOTHING" to "Protocol-based abstractions with dependency injection"
- **Justification:** Maintains testability (inject StubProvider) while allowing real implementations in I/O layer
- **Alignment:** Matches industry-standard Ports & Adapters / Hexagonal Architecture

### Rationale

**Why This Approach:**
1. **Resolves All Conflicts:** All 4 concerns addressed through documentation clarity
2. **Minimal Timeline Impact:** Documentation updates only, no major code refactoring required
3. **Aligns with Brownfield:** Accepts existing architecture patterns, updates PRD to match
4. **Maintains Testability:** Protocol pattern preserves "100% testable" benefit
5. **Reduces MVP Risk:** Strategic deferrals simplify implementation without losing value
6. **Industry Standard:** Dependency injection via Protocols is well-established pattern

**Trade-offs:**
- ✅ Maintains MVP timeline (potentially accelerates with StubProvider simplification)
- ✅ Resolves all 4 PRD conflicts
- ✅ Aligns with brownfield architecture recommendations
- ⚠️ Some advanced features deferred to Phase 2 (governance automation, detailed lineage)
- ✅ Technical debt is documented and intentional, not hidden

### Effort Estimate

**Documentation Updates:** 10-20 hours
- PRD section updates: 4-8 hours
- Epic story modifications: 6-12 hours

**Implementation Impact:** No additional time (StubProvider simplification may reduce effort)

**Net Timeline Impact:** Minimal delay, potentially faster MVP delivery

### Risk Assessment

**Overall Risk Level:** Low-Medium

**Low Risk Elements:**
- Concerns #1, #2, #4 are documentation clarifications/additions
- Brownfield code already exists, not starting from zero
- Strategic deferrals reduce complexity

**Medium Risk Element:**
- Concern #3 requires choosing architectural pattern
- Mitigation: Brownfield already implements Protocol pattern successfully

**Risk Mitigation:**
- All changes approved by user (Link) before implementation
- Incremental approach allows course correction
- Phase 2 deferrals clearly documented in PRD

---

## Section 4: Detailed Change Proposals

### Change Proposal #1: Add Rule Governance to FR-3.2

**Document:** docs/PRD.md
**Section:** FR-3.2: Registry-Driven Cleansing (lines 815-824)
**Status:** ✅ Approved by Link

**Before:**
```markdown
**FR-3.2: Registry-Driven Cleansing**
- **Description:** Apply value-level cleansing rules from central registry
- **User Value:** Standardize data transformations without duplicating code
- **Acceptance Criteria:**
  - ✅ Rules registered once in `cleansing/registry.py`, applied across domains
  - ✅ Example rules: trim whitespace, normalize company names, standardize dates
  - ✅ Pydantic adapter integration: rules applied automatically during model validation
  - ✅ Rules are composable: multiple rules can apply to same field
  - ✅ Configurable rule application: enable/disable rules per domain via config
```

**After:**
```markdown
**FR-3.2: Registry-Driven Cleansing**
- **Description:** Apply value-level cleansing rules from central registry with governance and audit controls
- **User Value:** Standardize data transformations without duplicating code while maintaining accountability and rollback capability
- **Acceptance Criteria:**
  - ✅ Rules registered once in `cleansing/registry.py`, applied across domains
  - ✅ Example rules: trim whitespace, normalize company names, standardize dates
  - ✅ Pydantic adapter integration: rules applied automatically during model validation
  - ✅ Rules are composable: multiple rules can apply to same field
  - ✅ Configurable rule application: enable/disable rules per domain via config
  - ✅ **Rule governance (MVP - Git-based):**
    - Rule changes follow standard code review process (PR required for `cleansing/rules/`)
    - Rule modifications logged in git history with clear commit messages
    - Rule tests required: each rule must have unit test demonstrating behavior
    - Breaking changes documented: if rule behavior changes, update CHANGELOG.md with migration notes
  - ⚠️ **Advanced governance (Phase 2 - Deferred):**
    - Version tracking: rules tagged with semantic versions (v1.0, v1.1, etc.)
    - Gradual rollout: A/B testing framework for validating rule changes on subset of data
    - Automated rollback: detection of data quality regressions with automatic rule revert
    - Cross-domain impact analysis: tool to identify which domains use specific rules
```

**Epic Impact:**
- **Epic 2 Story 2.3 (Cleansing Registry):** Add acceptance criteria for unit test coverage, CHANGELOG.md entries, code review requirements

---

### Change Proposal #2: Add Transformation Lineage to FR-4.3

**Document:** docs/PRD.md
**Section:** FR-4.3: Audit Logging (lines 898-906)
**Status:** ✅ Approved by Link

**Before:**
```markdown
**FR-4.3: Audit Logging**
- **Description:** Record every pipeline execution in database for traceability
- **User Value:** Answer questions like "which file was processed for January 2025?"
- **Acceptance Criteria:**
  - ✅ Logged per execution: timestamp, domain, input file path, version used, row counts (input/output/failed), duration
  - ✅ Error details captured: exception message, stack trace, failed row IDs
  - ✅ Queryable via SQL: "show me all annuity runs in last 6 months"
  - ✅ Retention policy: keep logs for 2 years
```

**After:**
```markdown
**FR-4.3: Audit Logging**
- **Description:** Record every pipeline execution in database for traceability, including transformation lineage for data governance
- **User Value:** Answer questions like "which file was processed for January 2025?" and "why did this company name change?"
- **Acceptance Criteria:**
  - ✅ **Pipeline execution logs (MVP):**
    - Logged per execution: timestamp, domain, input file path, version used, row counts (input/output/failed), duration
    - Error details captured: exception message, stack trace, failed row IDs
    - Queryable via SQL: "show me all annuity runs in last 6 months"
    - Retention policy: keep logs for 2 years
  - ✅ **Transformation tracking (MVP - Pipeline level):**
    - Each pipeline step logs: step name, duration, input/output row counts, applied configuration
    - Cleansing rules applied logged per pipeline run: which rules were active for this execution
    - Enrichment statistics: hit rates (internal mapping/external API/unknown), confidence score distribution
    - Validation failures exported to CSV with original row data + error details (already in FR-2.2)
  - ⚠️ **Field-level lineage (Phase 2 - Deferred):**
    - Row-level transformation tracking: original value → cleaned value for modified fields
    - Rule attribution: which specific rule(s) modified each field
    - Approver identity: who manually confirmed corrections or overrides
    - Lineage query API: "show me all transformations applied to company name 'ABC Corp' in last 6 months"
```

**Epic Impact:**
- **Epic 1 Story 1.3 (Logging Framework):** Add structured logging for pipeline steps with context (step_name, rules_applied, input/output rows, pipeline_run_id)
- **Epic 1 Story 1.8 (Database Loading):** Log removed columns with WARNING when using column projection

---

### Change Proposal #3: Resolve Dependency Conflict

**Document:** docs/PRD.md
**Section:** Code Organization (lines 400-446)
**Status:** ✅ Approved by Link

**Before:**
```markdown
**Dependency Rule (Critical):**
- **`domain/` imports from:** NOTHING (pure business logic, zero dependencies)
- **`io/` imports from:** `domain/` only (knows about models, not how to transform them)
- **`orchestration/` imports from:** `domain/` + `io/` (wires everything together)

**Benefit:** Business logic in `domain/` is 100% testable without database, files, or external services.
```

**After:**
```markdown
**Dependency Rule (Critical):**
- **`domain/` imports from:** Standard library + core data libraries (pandas, pydantic) + Protocol abstractions ONLY
  - ✅ Allowed: Defining Protocol interfaces for external services (e.g., `EnterpriseInfoProvider`)
  - ✅ Allowed: Pure business logic, validation rules, transformation functions
  - ❌ Forbidden: Direct imports from `io/`, `orchestration/`, or concrete I/O implementations
  - ❌ Forbidden: Direct HTTP clients, database connections, file system access
  - **Pattern:** Use dependency injection - domain functions accept Protocol instances as parameters
- **`io/` imports from:** `domain/` (implements Protocols, knows about models)
  - ✅ Provides concrete implementations of domain Protocols (e.g., `EqcProvider` implements `EnterpriseInfoProvider`)
  - ✅ Handles all external I/O: HTTP, database, file system, external APIs
- **`orchestration/` imports from:** `domain/` + `io/` (wires everything together)
  - ✅ Injects I/O implementations into domain functions
  - ✅ Coordinates execution flow and handles configuration

**Benefit:** Business logic in `domain/` is 100% testable by injecting stub/mock implementations of Protocol interfaces, eliminating need for database, files, or external services.

**Example Pattern:**
```python
# domain/company_enrichment/protocols.py (domain layer - just the contract)
from typing import Protocol, Optional

class EnterpriseInfoProvider(Protocol):
    """Protocol for company information lookup services."""
    def search_by_name(self, name: str) -> Optional[CompanyDetail]:
        """Search for company by name."""
        ...

# domain/company_enrichment/service.py (domain layer - pure business logic)
def enrich_company_name(
    company_name: str,
    provider: Optional[EnterpriseInfoProvider] = None  # DI pattern
) -> str:
    """Resolve company name to canonical ID. 100% testable with stub provider."""
    if provider is None:
        return generate_temp_id(company_name)

    result = provider.search_by_name(company_name)
    return result.company_id if result else generate_temp_id(company_name)

# io/connectors/eqc_provider.py (I/O layer - concrete implementation)
class EqcProvider:
    """Real EQC API client - lives in I/O layer, not domain."""
    def search_by_name(self, name: str) -> Optional[CompanyDetail]:
        response = requests.post(...)  # External API call
        return parse_response(response)

# orchestration/ops.py (orchestration - wires domain + I/O)
from domain.company_enrichment import enrich_company_name
from io.connectors.eqc_provider import EqcProvider

def process_data():
    provider = EqcProvider()  # I/O layer implementation
    result = enrich_company_name("ABC Corp", provider=provider)  # Inject
```
```

**Additional PRD Update - FR-3.3 Company Enrichment (add clarification note):**
```markdown
**Implementation Note:**
- Provider and Gateway abstractions follow dependency injection pattern
- Protocol definitions live in `domain/company_enrichment/protocols.py`
- Concrete implementations (EqcProvider, database access) live in `io/` layer
- MVP uses `StubProvider` (offline fixtures) - no external dependencies
- Real EQC integration deferred to Phase 2 (Growth phase)
```

**Epic Impact:**
- **Epic 1 Story 1.6 (Architecture Boundaries):** Update to reflect refined dependency rule with Protocol/DI pattern, add example code
- **Epic 5 (Company Enrichment):** UNBLOCKED - can proceed with StubProvider for MVP, defer EqcProvider to Phase 2

---

### Change Proposal #4: Clarify Validation Order

**Document:** docs/PRD.md
**Sections:** FR-1.4 (lines 739-748) AND Bronze Validation (lines 486-502)
**Status:** ✅ Approved by Link

**Before (FR-1.4 lines 739-748):**
```markdown
**FR-1.4: Resilient Data Loading**
- **Description:** Gracefully handles common Excel data issues during load
- **User Value:** Prevents pipeline crashes from minor data format variations
- **Acceptance Criteria:**
  - ✅ Skips completely empty rows automatically
  - ✅ Coerces numeric strings to numbers where appropriate
  - ✅ Handles merged cells (uses first cell's value for entire range)
  - ✅ Normalizes column names (spaces, special characters) using `column_normalizer`
  - ✅ Logs warnings for data coercion (e.g., "Column '月度' coerced from string to date")
```

**After (FR-1.4):**
```markdown
**FR-1.4: Resilient Data Loading with Audit Trail**
- **Description:** Handles Excel structural issues during load while preserving audit trail of corrections
- **User Value:** Prevents pipeline crashes from Excel formatting variations (merged cells, extra rows) while maintaining data quality visibility
- **Acceptance Criteria:**
  - ✅ **Structural normalization (automatic, always logged):**
    - Skips completely empty rows (all cells null/empty) - logs count: "Skipped 5 empty rows"
    - Handles merged cells: uses first cell's value for entire range - logs warning with cell range
    - Normalizes column names: strips whitespace, removes special characters - logs original→normalized mapping
  - ✅ **Type coercion (optional, configurable, always logged):**
    - Numeric strings to numbers: "123.45" → 123.45 (when column schema expects numeric)
    - Date strings to dates: "2025-01" → date(2025, 1, 1) (when column schema expects date)
    - Enabled via `WDH_EXCEL_AUTO_COERCE=1` (default: disabled for MVP to catch data issues early)
    - Each coercion logged as WARNING: "Row 15, column '月度': coerced '202501' (str) → 2025-01-01 (date)"
  - ✅ **Audit trail requirements:**
    - All auto-corrections logged to structured log with details: row number, column, original value, corrected value, reason
    - Correction summary in pipeline execution log: "Auto-corrections: 5 empty rows skipped, 3 merged cells handled, 12 dates coerced"
  - ❌ **NOT auto-corrected (must pass Bronze validation):**
    - Missing required columns
    - Null values in required fields
    - Invalid data types that can't be coerced
    - Out-of-range values (negative amounts, future dates beyond threshold)

**Execution Order:**
1. Load Excel → Apply structural normalization (empty rows, merged cells, column names)
2. Apply type coercion if enabled (log each coercion)
3. Pass to Bronze validation → Validate schema, required fields, data types
4. Bronze validation failures → Export to CSV for review
```

**Before (Bronze Validation lines 486-502):**
```markdown
**1. Source Data Validation (Bronze Layer Entry)**
```python
@pa.check_schema(BronzeAnnuitySchema)
def load_raw_excel(file_path: str) -> pd.DataFrame:
    """Reject bad source data immediately"""
    df = pd.read_excel(file_path)
    return df
```

**Required Bronze Validations:**
- ✅ Expected columns present
- ✅ No completely null columns
- ✅ Date fields parseable
- ✅ Numeric fields are numeric
- ✅ Required fields not null
```

**After (Bronze Validation):**
```markdown
**1. Source Data Validation (Bronze Layer Entry)**
```python
@pa.check_schema(BronzeAnnuitySchema)
def load_raw_excel(file_path: str) -> pd.DataFrame:
    """Validate data after structural normalization but before business logic.

    Execution flow:
    1. excel_reader.py: Load Excel, apply FR-1.4 structural normalization
    2. THIS FUNCTION: Validate normalized data meets Bronze requirements
    3. If validation fails: raise SchemaError, export failed rows to CSV
    4. If validation passes: data moves to Silver for business transformation
    """
    df = read_excel_with_normalization(file_path)  # FR-1.4 applied
    return df  # pandera validates NORMALIZED data
```

**Required Bronze Validations (applied AFTER FR-1.4 normalization):**
- ✅ Expected columns present - column names already normalized by FR-1.4
- ✅ No completely null columns - empty rows already removed by FR-1.4
- ✅ Date fields parseable - may be coerced by FR-1.4 if enabled
- ✅ Numeric fields are numeric - may be coerced by FR-1.4 if enabled
- ✅ Required fields not null - first defense if coercion disabled
- ✅ Date ranges reasonable: dates between 2000-2030
- ✅ No duplicate composite keys within single file

**Bronze Philosophy:**
- Validates STRUCTURE and BASIC TYPES of normalized data
- Auto-corrections from FR-1.4 are LOGGED, not hidden
- If coercion disabled (recommended MVP), Bronze catches type errors immediately
- If coercion enabled, Bronze validates coerced values meet business constraints
```

**Epic Impact:**
- **Epic 2 Story 2.2 (Pandera Schemas):** Update to validate data AFTER FR-1.4 normalization, add tests with/without coercion
- **Epic 3 (Excel Reader - not yet detailed):** Add structured logging for auto-corrections, `WDH_EXCEL_AUTO_COERCE` configuration flag

---

## Section 5: Implementation Handoff

### Change Scope Classification

**Scope: MODERATE**

**Rationale:**
- Primarily documentation updates (PRD, epics)
- 7 story modifications across 2 epics
- No major code refactoring required
- Strategic deferrals reduce implementation complexity
- Brownfield architecture already implements key patterns

### Handoff Recipients and Responsibilities

**Primary: Product Manager (John) - Documentation Updates**

**Responsibilities:**
1. Update PRD (docs/PRD.md) with all 4 approved change proposals:
   - FR-3.2: Add rule governance section
   - FR-4.3: Expand audit logging requirements
   - Architecture Section (lines 441-446): Refine dependency rule with Protocol/DI pattern
   - FR-1.4 (lines 739-748): Clarify auto-correction scope
   - Bronze Validation (lines 486-502): Update execution order documentation
   - FR-3.3: Add implementation note about StubProvider MVP approach

2. Update Epics (docs/epics.md) for affected stories:
   - Epic 1 Story 1.3: Add transformation logging context
   - Epic 1 Story 1.6: Update architecture boundary rules
   - Epic 1 Story 1.8: Add column projection logging
   - Epic 2 Story 2.2: Update Bronze validation timing
   - Epic 2 Story 2.3: Add rule governance requirements
   - Epic 2 Story 2.5: Add transformation tracking

3. Create Epic 5 (Company Enrichment) stories with StubProvider MVP approach

4. Document Phase 2 deferrals in PRD "Roadmap" or "Future Enhancements" section

**Secondary: Solution Architect (Winston) - Architecture Validation**

**Responsibilities:**
1. Review refined dependency rule for technical accuracy
2. Validate Protocol/DI pattern aligns with brownfield implementation
3. Confirm StubProvider MVP approach for Epic 5
4. Update brownfield architecture document if needed (docs/brownfield-architecture.md)

**Tertiary: Development Team - Story Implementation**

**Responsibilities:**
1. Implement modified stories according to updated acceptance criteria
2. Focus on MVP scope (git-based governance, pipeline-level logging)
3. Use StubProvider for company enrichment in MVP
4. Ensure all auto-corrections are logged per FR-1.4 updates

### Success Criteria

**Documentation Complete:**
- ✅ PRD updated with all 4 change proposals
- ✅ All affected epic stories updated with new acceptance criteria
- ✅ Phase 2 deferrals clearly marked in PRD
- ✅ Architecture document aligned with refined dependency rule

**Conflicts Resolved:**
- ✅ Rule governance mechanism specified (git-based MVP)
- ✅ Transformation audit trail defined (pipeline-level MVP)
- ✅ Dependency conflict resolved (Protocol/DI pattern accepted)
- ✅ Validation order clarified (FR-1.4 → Bronze → Silver)

**Epic 5 Unblocked:**
- ✅ Can proceed with StubProvider implementation
- ✅ Architectural pattern clarified and validated
- ✅ Real EQC integration deferred to Phase 2

**Quality Gates:**
- ✅ Link (user) approval obtained for all proposals
- ✅ No scope creep - MVP features clearly separated from Phase 2
- ✅ Timeline maintained - minimal delay, possibly accelerated
- ✅ Technical debt documented - deferrals are intentional, not hidden

### Implementation Timeline

**Phase 1: Documentation Updates (1-2 weeks)**
- Week 1: PRD updates (4 sections)
- Week 2: Epic story updates (7 stories) + Epic 5 creation

**Phase 2: Story Implementation (ongoing)**
- Epic 1-2 stories: Implement as part of normal sprint progression
- Epic 5: Can proceed once documentation complete

**Total Impact:** +1-2 weeks for documentation, no additional implementation delay

### Next Steps

1. **Immediate:** Link approves Sprint Change Proposal (this document)
2. **Week 1:** John updates PRD with approved changes
3. **Week 1:** Winston reviews architecture updates for technical accuracy
4. **Week 2:** John updates Epic 1-2 stories and creates Epic 5 stories
5. **Week 2:** Development team reviews updated stories, asks clarifying questions
6. **Week 3+:** Proceed with Epic 1-2 implementation using updated acceptance criteria

### Open Questions / Decisions Needed

1. **Phase 2 Timing:** When should deferred features (advanced governance, field-level lineage, real EQC integration) be scheduled?
   - Recommendation: After Epic 9 (all domains migrated) when value is clearer

2. **Configuration Default:** Should `WDH_EXCEL_AUTO_COERCE` default to enabled or disabled for MVP?
   - Current proposal: Disabled (catch more errors early)
   - Alternative: Enabled (more resilient, but silent corrections)
   - **Decision needed from Link**

3. **Brownfield Architecture Update:** Should brownfield architecture document be updated to reflect refined dependency rule?
   - Recommendation: Yes, update lines 201-333 to mention Protocol/DI pattern explicitly

---

## Appendix A: Change Summary Matrix

| Concern | PRD Section | Change Type | MVP Scope | Phase 2 Deferred |
|---------|-------------|-------------|-----------|------------------|
| #1 Rule Governance | FR-3.2 (815-824) | Addition | Git-based governance, test requirements | Version control, A/B testing, auto-rollback |
| #2 Audit Trail | FR-4.3 (898-906) | Expansion | Pipeline-level logging, rule tracking | Field-level lineage, approver identity |
| #3 Dependency Conflict | Architecture (441-446) | Refinement | Protocol/DI pattern, StubProvider MVP | Real EqcProvider implementation |
| #4 Validation Order | FR-1.4 (739-748) + Bronze (486-502) | Clarification | Execution order documented, configurable coercion | None (fully resolved in MVP) |

---

## Appendix B: Epic Story Modification Checklist

**Epic 1: Foundation & Core Infrastructure**

- [ ] Story 1.3 (Logging): Add pipeline step context logging with rules_applied, input/output rows
- [ ] Story 1.6 (Architecture): Update dependency rule to Protocol/DI pattern with examples
- [ ] Story 1.8 (Database Loading): Add WARNING log for column projection removals

**Epic 2: Multi-Layer Data Quality Framework**

- [ ] Story 2.2 (Pandera Schemas): Update Bronze validation to occur AFTER FR-1.4 normalization
- [ ] Story 2.3 (Cleansing Registry): Add unit test requirements, CHANGELOG documentation, code review
- [ ] Story 2.5 (Error Handling): Add pipeline-level transformation tracking

**Epic 5: Company Enrichment Service**

- [ ] Create Epic 5 stories using StubProvider MVP approach
- [ ] Defer EqcProvider implementation to Phase 2
- [ ] Define Protocol interfaces in domain layer
- [ ] Implement StubProvider in I/O layer for testing

---

## Appendix C: Approval Record

**Sprint Change Proposal Review Session: 2025-11-09**

| Change Proposal | Reviewer | Decision | Timestamp |
|-----------------|----------|----------|-----------|
| #1 Rule Governance | Link | ✅ Approved | 2025-11-09 |
| #2 Audit Trail | Link | ✅ Approved | 2025-11-09 |
| #3 Dependency Conflict | Link | ✅ Approved | 2025-11-09 |
| #4 Validation Order | Link | ✅ Approved | 2025-11-09 |

**Overall Sprint Change Proposal:** ✅ **APPROVED by Link on 2025-11-09**

---

**End of Sprint Change Proposal**
