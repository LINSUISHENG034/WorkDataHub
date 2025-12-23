# Sprint Change Proposal
## Company ID Enrichment Complexity - Documentation Enhancement

**Generated:** 2025-11-08
**Project:** WorkDataHub
**Workflow:** Correct Course - Sprint Change Management
**Change Scope:** MINOR (Documentation-only, preventive)

---

## Executive Summary

**Issue:** Company ID enrichment complexity significantly underestimated in PRD FR-3.3. Discovered during Phase 1 (Planning) completion, before Phase 2 (Solutioning) begins.

**Impact:** **POSITIVE** - Caught at ideal timing, preventing 300-400% scope creep during future implementation.

**Recommendation:** Apply 3 approved documentation updates (PRD, Architecture, .env), clarify MVP scope to use StubProvider (offline fixtures), defer production enrichment to Growth phase.

**Artifacts Updated:** PRD FR-3.3, Architecture document, `.env.example`

**MVP Impact:** ✅ None - MVP remains fully achievable with clarified scope

**Timeline Impact:** ✅ None - Actually prevents future delays from mid-sprint surprises

---

## Section 1: Issue Summary

### Discovery Context

**When:** Phase 1 (Planning) complete, before Phase 2 (Solutioning) begins
**How:** Created comprehensive reference documentation consolidating solution architecture
**Document:** `reference/01_company_id_analysis.md` (150 lines, 13 sections)

### Core Problem Statement

The PRD's FR-3.3 "Company Enrichment Integration" (lines 825-833) captures the enrichment concept at high level but lacks critical implementation details that would cause significant scope creep if discovered mid-sprint.

**What's Missing from PRD:**

| Missing Element | Current PRD | Documented in Reference |
|----------------|-------------|------------------------|
| Temporary ID Strategy | ❌ Not mentioned | ✅ HMAC-based `IN` aliases with salt management |
| Confidence Scoring | ❌ Not mentioned | ✅ Three-tier thresholds (≥0.90 / 0.60-0.90 / <0.60) with human review |
| Provider Architecture | ❌ Not mentioned | ✅ EnterpriseInfoProvider protocol, Gateway, multiple providers (Stub/EQC/Legacy) |
| Legacy Migration | ❌ Not mentioned | ✅ 5-layer mapping consolidation from Mongo/MySQL |
| Data Models | ❌ Not mentioned | ✅ 3 tables: company_master, company_name_index, enrichment_requests |
| Security/Credentials | ❌ Not mentioned | ✅ EQC token lifecycle, Playwright automation, 11 environment variables |
| Two Approaches | ❌ Not mentioned | ✅ Complex (CI-002 8 sub-tasks) vs Simplified (S-001~S-004) with trade-offs |

### Evidence

**Primary Source:**
- `reference/01_company_id_analysis.md`: Comprehensive 150-line solution documentation with:
  - Problem definition and historical context (§1-2)
  - Two architectural approaches with sub-task breakdown (§6-7)
  - EQC API integration and credential management (§8)
  - Legacy migration strategy (§10)
  - Observability and operational metrics (§11)
  - Environment variables catalog (Appendix A)

**Archive Reference:**
- `reference/archive/context-engineering-intro/docs/company_id/*`: Battle-tested implementation history from previous work

**Current PRD Coverage:**
- FR-3.3 (lines 825-833): Only 9 lines with 5 high-level acceptance criteria
- No architectural patterns documented
- No implementation approach guidance

### Impact Without This Discovery

If epics/stories were created from current PRD FR-3.3 alone:

1. **Underestimation:** Company enrichment scoped as 1-2 stories (~3-5 points)
2. **Mid-Sprint Surprise:** Team discovers 8+ sub-tasks during implementation (actual: ~13-16 points for full approach)
3. **Scope Creep:** 300-400% expansion during sprint execution
4. **Ad-hoc Architecture:** Provider pattern, Gateway abstraction, temporary IDs designed under time pressure
5. **Technical Debt:** Hasty decisions without proper architectural review

---

## Section 2: Impact Analysis

### Epic Impact Assessment

**Current State:**
- ✅ **No epics exist yet** - Project in Phase 1 (Planning), Phase 2 (Solutioning) not started
- ✅ **Perfect timing** - Complexity discovered BEFORE epic creation

**Workflow Status:**
```yaml
Phase 1 (Planning):
  prd: ✅ docs/PRD.md (Complete)

Phase 2 (Solutioning):
  create-architecture: ⏳ recommended (NOT STARTED)
  solutioning-gate-check: ⏳ required (NOT STARTED)

Phase 3 (Implementation):
  sprint-planning: ⏳ required (NOT STARTED)
```

**Future Epic Impact:**

When `/create-epics-and-stories` runs:
- **Original trajectory:** FR-3.3 generates single "Company Enrichment" epic (~2-3 stories, ~3-5 points)
- **Corrected trajectory:** Properly scoped epic with clear MVP vs. Growth phase split:
  - **MVP:** StubProvider implementation (~2 stories, ~3 points)
  - **Growth:** Production enrichment (Simplified ~4-6 stories OR Complex ~13-16 stories)

**Assessment:** ✅ **POSITIVE FINDING** - Caught at ideal time to prevent future issues

### Artifact Conflict and Impact Analysis

| Artifact | Impact Level | Changes Needed | Status |
|----------|--------------|----------------|--------|
| **PRD** (`docs/PRD.md`) | 🔴 High | Expand FR-3.3 acceptance criteria (lines 825-833) | ✅ Proposal #1 Approved |
| **Architecture** (`docs/brownfield-architecture.md`) | 🔴 High | Add comprehensive enrichment architecture section | ✅ Proposal #2 Approved |
| **Environment Config** (`.env.example`) | 🟡 Medium | Add 11 enrichment variables with documentation | ✅ Proposal #3 Approved |
| **UI/UX Specifications** | ✅ None | N/A (backend data platform) | N/A |
| **Testing Strategy** | 🟡 Medium | Document StubProvider test patterns | 📝 To Create |
| **Database DDL** | 🟡 Medium | Generate `enterprise` schema scripts (3 tables) | 📝 To Create |
| **Documentation** (README) | 🟡 Medium | Link to `reference/01_company_id_analysis.md` | 📝 To Create |

**Conflicts with PRD Goals?**
- ✅ **No conflicts** with core objectives (automation, reliability, maintainability)
- ✅ **Aligns with** NFR-3.1 (type safety - Pydantic models for enrichment)
- ✅ **Supports** FR-2.2 (Silver layer validation with enrichment metadata)
- ⚠️ **Scope clarification needed:** FR-3.3 is larger than originally estimated

---

## Section 3: Recommended Approach

### Selected Path Forward

**Primary Approach:** **Direct Adjustment with MVP Scope Clarification**

**What This Means:**

1. **Apply 3 approved documentation updates:**
   - PRD FR-3.3: Expand acceptance criteria with full implementation details
   - Architecture: Add comprehensive Company Enrichment Architecture section
   - Environment: Update `.env.example` with 11 enrichment variables

2. **Clarify MVP scope:**
   - **Use StubProvider** (offline company fixtures) for MVP
   - **Defer to Growth:** EQC integration, async queue, legacy migration, production schema

3. **No epic/story rework needed:**
   - Complexity properly documented before epic creation begins
   - When ready: Run `/create-epics-and-stories` with informed context

4. **Additional artifacts:**
   - Create test strategy guide for StubProvider patterns
   - Generate `enterprise` schema DDL (documentation artifact)
   - Link reference doc from README

### Rationale

✅ **Why This is the RIGHT Approach:**

**1. Perfect Timing Discovery:**
- After PRD (requirements clear) but before Architecture/Epics (can influence design)
- No implementation work to undo
- No mid-sprint surprises for development team

**2. Prevents Technical Debt:**
- Architectural patterns (Provider, Gateway) designed upfront with proper review
- MVP scope realistic and achievable (~2 stories vs. ~13-16 if attempting full complexity)
- Growth phase has clear roadmap documented in reference doc

**3. Maintains MVP Focus:**
- MVP success criteria: automation, parity, extensibility patterns (still achievable)
- Enrichment complexity doesn't need to be solved in MVP to prove architecture
- StubProvider sufficient for validating pipeline framework

**4. Low Risk & Effort:**
- 3 documentation updates (already approved by user)
- No code changes required
- No scope reduction (just clarification)
- Actually prevents future delays from scope creep

**5. Follows Best Practices:**
- Strangler Fig pattern: Prove core patterns before tackling complexity
- Incremental value delivery: MVP delivers working pipeline, Growth adds production enrichment
- Risk mitigation: Defer high-risk external API integration until core validated

### Alternatives Considered & Rejected

❌ **Option 2: Rollback Approach**
- **Status:** N/A - No completed work to revert (planning phase)

❌ **Option 3A: Ignore Complexity**
- **Why rejected:** Would cause 300-400% scope creep during implementation
- **Consequence:** Mid-sprint architectural debates, technical debt, missed estimates

❌ **Option 3B: Full Complex Enrichment in MVP**
- **Why rejected:** Would add ~13-16 story points to MVP
- **Risk:** High complexity (EQC integration, async queue, legacy migration) before core patterns validated
- **Violates:** MVP principle of proving simplest path first

### Trade-offs Accepted

| Trade-off | Impact | Mitigation |
|-----------|--------|----------|
| MVP uses fixtures (not production-ready enrichment) | Cannot process real production data requiring external enrichment | Growth phase implements production enrichment; legacy parity tests use known fixture data |
| Defers EQC integration to Growth | Team doesn't learn external API integration in MVP | Reference doc preserves all integration knowledge; clear Growth roadmap exists |
| Additional documentation upfront | Slight delay before epic creation (~2-4 hours) | Prevents much larger delays from mid-sprint scope creep (weeks of rework) |
| StubProvider in MVP | Cannot validate EQC API contract in MVP | Integration tests with mocked API validate contract; Growth phase handles real API |

### Effort Estimate

**Immediate Actions (Before Epic Creation):**
- Apply 3 approved documentation updates: **2 hours**
- Create test strategy guide: **1 hour**
- Generate DDL scripts: **1 hour**
- Update README with reference link: **15 minutes**

**Total upfront effort:** ~4-5 hours

**Savings from preventing scope creep:** ~40-60 hours (avoided mid-sprint rework for 300-400% expansion)

**Risk Level:** **Low** (documentation-only, no code changes, caught before implementation)

---

## Section 4: Detailed Change Proposals

### Edit Proposal #1: Expand PRD FR-3.3 (APPROVED)

**Location:** `docs/PRD.md` - Lines 825-833

**Summary:** Expand acceptance criteria from 5 high-level items to 12 detailed criteria covering Provider pattern, temporary IDs, confidence scoring, security, and legacy migration.

**Key Additions:**
- Temporary ID generation (HMAC-based `IN` aliases)
- Confidence scoring with human review thresholds
- Provider abstraction pattern (EnterpriseInfoProvider protocol)
- Data persistence schema (3 tables)
- Security & credential management (11 env variables)
- Legacy migration support
- Link to comprehensive reference documentation

**OLD (9 lines):**
```markdown
**FR-3.3: Company Enrichment Integration**
- **Description:** Resolve company IDs using internal mappings and external lookup service
- **User Value:** Augment data with enterprise identifiers for cross-domain joins
- **Acceptance Criteria:**
  - ✅ Three-tier resolution: (1) internal mapping, (2) synchronous EQC lookup (budget-limited), (3) async queue
  - ✅ Sync lookup budget prevents runaway API calls: `sync_lookup_budget=50` per run
  - ✅ Unknown companies exported to CSV for manual review
  - ✅ Enrichment stats tracked: internal hits, external hits, pending lookups, failures
  - ✅ Graceful degradation: enrichment failures don't block main pipeline (optional service)
```

**NEW (31 lines):**
```markdown
**FR-3.3: Company Enrichment Integration**
- **Description:** Resolve company IDs using internal mappings and external lookup service (EQC platform API), with fallback to stable temporary IDs for unresolved companies. Uses Provider abstraction pattern for testability and legacy migration support.
- **User Value:** Augment data with enterprise identifiers for cross-domain joins, enabling consistent customer attribution across multiple data domains
- **Reference Documentation:** `reference/01_company_id_analysis.md` - comprehensive solution architecture with two implementation approaches (Complex CI-002 vs. Simplified S-001~S-004)
- **Acceptance Criteria:**
  - ✅ **Multi-tier resolution strategy:**
    - (1) Internal mapping tables: `plan_company_map`, `account_company_map`, `name_company_index`
    - (2) Synchronous EQC API lookup (budget-limited to prevent blocking)
    - (3) Async enrichment queue for deferred resolution
  - ✅ **Temporary ID generation:** Unresolved companies get stable `IN<16-char-Base32>` IDs generated via `HMAC_SHA1(WDH_ALIAS_SALT, business_key)` - ensures same company always maps to same temporary ID
  - ✅ **Confidence scoring with human review thresholds:**
    - ≥0.90: Auto-accept and use company_id
    - 0.60-0.90: Accept but flag `needs_review=True`
    - <0.60: Keep temporary ID and queue for async resolution
  - ✅ **Provider abstraction:** `EnterpriseInfoProvider` protocol with multiple implementations:
    - `StubProvider`: Offline fixtures for testing/CI
    - `EqcProvider`: Real EQC platform API integration
    - `LegacyProvider`: Adapter for existing Mongo/MySQL crawler (optional)
  - ✅ **Gateway pattern:** `EnterpriseInfoGateway` handles normalization, evaluation, caching, and fallback logic
  - ✅ **Data persistence schema:**
    - `enterprise.company_master`: Canonical company records with official_name, unified_credit_code, aliases
    - `enterprise.company_name_index`: Normalized name → company_id mapping with match_type tracking
    - `enterprise.enrichment_requests`: Queue for async resolution with status tracking (pending/processing/done/failed)
  - ✅ **Sync lookup budget:** `WDH_ENRICH_SYNC_BUDGET` prevents runaway API calls (default: 0-5 per run)
  - ✅ **Unknown companies exported:** CSV with unresolved company names for manual review/backfill
  - ✅ **Enrichment observability:** Stats tracked per run:
    - Hit distribution: internal exact/fuzzy, external API, async queued, unknown
    - Sync budget consumption
    - Queue depth and processing success rate
    - Temporary ID generation count
  - ✅ **Graceful degradation:** Enrichment failures don't block main pipeline (optional service with feature flag `WDH_ENRICH_COMPANY_ID`)
  - ✅ **Security & credential management:**
    - EQC API token via `WDH_PROVIDER_EQC_TOKEN` (30-min validity)
    - Logs sanitized (no token leakage)
    - Optional Playwright automation for token capture (see `reference/01_company_id_analysis.md` §8)
  - ✅ **Legacy migration support:** Import existing mappings from Mongo/MySQL via `--job import_company_mappings` CLI command
```

**Status:** ✅ APPROVED

---

### Edit Proposal #2: Add Company Enrichment Architecture Section (APPROVED)

**Location:** `docs/brownfield-architecture.md` - After line 199 (in "Recent work" section or as new subsection)

**Summary:** Add comprehensive 100+ line architecture section documenting Provider pattern, Gateway, data models, persistence schema, resolution strategy, configuration surface, and implementation approaches.

**Key Content:**
- 7 core components (Provider, Gateway, Models, Schema, Temporary IDs, Resolution Strategy, Confidence Scoring)
- Complete DDL for 3 `enterprise` schema tables
- Configuration surface (11 environment variables)
- Two implementation approaches (Complex CI-002 vs. Simplified S-001~S-004) with status
- Security considerations and testing strategy

**Content:** (See full content in Edit Proposal #2 - 150+ lines covering complete architecture)

**Status:** ✅ APPROVED

---

### Edit Proposal #3: Update .env.example with Enrichment Variables (APPROVED)

**Location:** `.env.example` (create if doesn't exist)

**Summary:** Add documented section for 11 company enrichment environment variables with descriptions, defaults, and security guidance.

**Content:**
```bash
# ============================================
# Company Enrichment Configuration
# ============================================
# See reference/01_company_id_analysis.md for detailed documentation

# REQUIRED: Salt for generating stable temporary IDs (IN_<hash>)
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
WDH_ALIAS_SALT=your_secret_salt_here_change_in_production

# Enable company ID enrichment service (0=disabled, 1=enabled)
WDH_ENRICH_COMPANY_ID=0

# Sync lookup budget: max external API calls per pipeline run (0=disabled)
WDH_ENRICH_SYNC_BUDGET=0

# Provider selection: stub (testing), eqc (production), legacy (migration)
WDH_ENTERPRISE_PROVIDER=stub

# EQC API Configuration (required if WDH_ENTERPRISE_PROVIDER=eqc)
WDH_PROVIDER_EQC_TOKEN=  # 30-minute validity, refresh via auth automation
WDH_PROVIDER_EQC_BASE_URL=  # Optional: override default EQC API endpoint

# Simplified Approach Configuration (S-001~S-004)
WDH_COMPANY_ENRICHMENT_ENABLED=0
WDH_COMPANY_SYNC_LOOKUP_LIMIT=5

# Queue Processing Configuration
WDH_LOOKUP_QUEUE_BATCH_SIZE=50
WDH_LOOKUP_RETRY_MAX=3
WDH_LOOKUP_RETRY_DELAY=300  # seconds
```

**Status:** ✅ APPROVED

---

## Section 5: PRD MVP Impact & Action Plan

### MVP Achievability Assessment

**MVP Success Criteria Impact:**

| PRD Success Criteria | Impact | Assessment |
|---------------------|--------|------------|
| **1. Automation Excellence** | ✅ No Impact | StubProvider supports automated enrichment interface; version detection and hands-free processing unaffected |
| **2. Fearless Extensibility** | ✅ Enhanced | Provider pattern demonstrates extensibility principle; swap Stub→EQC in Growth proves "new domain in afternoon" |
| **3. Team-Ready Maintainability** | ✅ Enhanced | Better documentation and clearer architecture improve team handoff readiness |
| **4. Legacy System Retirement** | ✅ No Impact | Golden dataset tests use fixture data (known companies); parity validation still achievable |
| **5. Operational Reliability** | ✅ No Impact | Data quality gates and validation work identically with fixture enrichment |

**Conclusion:** ✅ **MVP fully achievable with clarified scope**

### MVP Scope Clarification

**IN SCOPE for MVP:**
- ✅ `EnterpriseInfoProvider` protocol definition (abstraction layer)
- ✅ `StubProvider` implementation (offline company fixtures for testing)
- ✅ Temporary ID generation (HMAC-based `IN` aliases with salt)
- ✅ Basic enrichment stats tracking (internal hits, unknown count)
- ✅ Enrichment integration in annuity pipeline (demonstrate pattern)
- ✅ Feature flag (`WDH_ENRICH_COMPANY_ID`) for toggle on/off
- ✅ Unit tests with StubProvider (no external dependencies)

**OUT OF SCOPE for MVP (deferred to Growth Phase):**
- ❌ EQC API integration (`EqcProvider` implementation)
- ❌ Async enrichment queue (`enrichment_requests` table and processing job)
- ❌ Legacy crawler migration (`LegacyProvider` adapter)
- ❌ Real-time credential management (EQC token automation with Playwright)
- ❌ Production `enterprise` schema deployment (company_master, company_name_index tables)
- ❌ Confidence scoring with human review thresholds (fixtures return 1.0 confidence)
- ❌ Gateway abstraction (optional for StubProvider; add when needed for EqcProvider)

**MVP Sizing Estimate:**
- **Original (without clarification):** 1-2 stories, ~3-5 points (would expand 300-400% mid-sprint)
- **Corrected (with StubProvider scope):** 2 stories, ~3 points
  - Story 1: Provider protocol + StubProvider implementation (~2 points)
  - Story 2: Integrate enrichment into annuity pipeline (~1 point)

**Growth Phase Sizing Estimate:**
- **Simplified Approach (S-001~S-004):** 4-6 stories, ~8-10 points
- **Complex Approach (CI-002 full):** 13-16 stories, ~21-26 points

### High-Level Action Plan

**Phase A: Immediate Actions (Before Epic Creation) - CURRENT PHASE**

| # | Action | Owner | Effort | Status |
|---|--------|-------|--------|--------|
| 1 | Apply PRD FR-3.3 expansion (Proposal #1) | PM (Link) | 30 min | ⏳ Pending Approval |
| 2 | Add Architecture section (Proposal #2) | PM (Link) | 1 hour | ⏳ Pending Approval |
| 3 | Update `.env.example` (Proposal #3) | PM (Link) | 15 min | ⏳ Pending Approval |
| 4 | Create test strategy guide for StubProvider | Architect | 1 hour | 📝 To Create |
| 5 | Generate `enterprise` schema DDL scripts | Architect | 1 hour | 📝 To Create |
| 6 | Update README with reference doc link | PM (Link) | 15 min | 📝 To Create |
| 7 | Update workflow status YAML | PM (Link) | 5 min | 📝 To Create |

**Total Phase A Effort:** ~4-5 hours (prevents ~40-60 hours of scope creep rework)

**Phase B: Phase 2 Solutioning Workflows - NEXT PHASE**

| # | Workflow | Purpose | Output |
|---|----------|---------|--------|
| 8 | `/create-architecture` (optional) | If separate architecture workflow needed beyond brownfield doc updates | Architecture document |
| 9 | `/create-epics-and-stories` | Generate properly-scoped epics with MVP/Growth split | Epic files with user stories |
| 10 | `/solutioning-gate-check` | Validate PRD ↔ Architecture ↔ Epics alignment before implementation | Gate check report |

**Phase C: Phase 3 Implementation - FUTURE**

| # | Epic | Stories | Points | Priority |
|---|------|---------|--------|----------|
| 11 | Company Enrichment MVP | 2 stories (Provider + Integration) | ~3 points | High (part of Annuity domain epic) |
| 12 | Company Enrichment Production (Growth) | 4-6 stories (Simplified) OR 13-16 stories (Complex) | ~8-26 points | Medium (post-MVP) |

---

## Section 6: Implementation Handoff Plan

### Change Scope Classification

**Scope Level:** **MINOR** ✅

**Rationale:**
- Changes are **documentation-only** (no code impacts)
- Discovered **before implementation** begins (preventive, not corrective)
- No backlog reorganization needed (no epics/stories exist yet)
- No timeline impact (actually prevents future delays)
- No rollback of completed work required

**Handoff Type:** **Direct to Product Manager** (documentation updates only)

### Handoff Recipients & Responsibilities

**Primary: Product Manager (Link) - CURRENT OWNER**

**Immediate Responsibilities:**
1. ✅ **Review & approve** this Sprint Change Proposal
2. ✅ **Decide:** Confirm StubProvider approach for MVP (recommended)
3. ✅ **Execute:** Apply 3 approved documentation edits:
   - Edit `docs/PRD.md` FR-3.3 (lines 825-833)
   - Add section to `docs/brownfield-architecture.md` (after line 199)
   - Create/update `.env.example` with enrichment variables
4. ✅ **Execute:** Create supporting artifacts:
   - Link `reference/01_company_id_analysis.md` from README
   - Update `docs/bmm-workflow-status.yaml` (mark PRD as updated)
5. ✅ **Next workflow:** Run `/create-architecture` (optional) or proceed to `/create-epics-and-stories`

**Secondary: Solution Architect (if separate role)**

**Responsibilities:**
1. Review Company Enrichment Architecture section (Proposal #2)
2. Validate Provider/Gateway pattern aligns with system architecture
3. Create database DDL scripts for `enterprise` schema (documentation artifact)
4. Document test strategy for StubProvider and confidence scoring
5. **Deliverable:** Test strategy guide + DDL scripts

**Future: Development Team (Post-Epic Creation)**

**Responsibilities:**
1. Implement StubProvider with offline company fixtures
2. Implement temporary ID generation (HMAC-based)
3. Integrate enrichment service into annuity pipeline
4. Write unit tests with StubProvider (no external dependencies)
5. Validate golden dataset regression tests pass with fixture data
6. **Key Reference:** `reference/01_company_id_analysis.md` for full solution context

**Future: Product Owner / Scrum Master (Phase 3)**

**Responsibilities:**
1. Ensure Growth phase epic for production enrichment exists in backlog
2. Validate MVP stories properly estimated with StubProvider scope (~3 points)
3. Monitor that MVP implementation doesn't creep into EQC integration
4. Prioritize Growth phase enrichment epic based on production readiness needs

### Success Criteria for Handoff Completion

**Definition of Done:**
- [ ] Sprint Change Proposal reviewed and approved by PM (Link)
- [ ] 3 approved documentation edits applied to git repository
- [ ] Reference doc (`reference/01_company_id_analysis.md`) linked from README
- [ ] Workflow status updated: PRD marked as "updated" in `bmm-workflow-status.yaml`
- [ ] Test strategy guide created (Architect)
- [ ] Database DDL scripts generated (Architect)
- [ ] Next workflow command identified: `/create-architecture` or `/create-epics-and-stories`
- [ ] All stakeholders understand their roles and responsibilities

**Validation Checklist:**
- [ ] PRD FR-3.3 includes 12 detailed acceptance criteria (vs. original 5)
- [ ] Architecture document has Company Enrichment section (100+ lines)
- [ ] `.env.example` documents all 11 enrichment environment variables
- [ ] README links to comprehensive reference documentation
- [ ] No ambiguity about MVP scope (StubProvider clear)
- [ ] Growth phase roadmap clear (Simplified vs. Complex approaches documented)

---

## Section 7: Risk Assessment & Mitigation

### Risks Mitigated by This Change

| Risk | Original Probability | Impact | Mitigation via This Change |
|------|---------------------|--------|----------------------------|
| **Scope Creep During Implementation** | High (80%) | High (300-400% expansion) | ✅ Eliminated - Full complexity documented upfront |
| **Mid-Sprint Architectural Debates** | High (70%) | Medium (delays, rework) | ✅ Eliminated - Provider/Gateway pattern decided pre-epic |
| **Underestimated Story Points** | High (90%) | High (missed commitments) | ✅ Eliminated - StubProvider scope clearly defined (~3 points vs. ~13-16) |
| **Technical Debt from Hasty Decisions** | Medium (50%) | High (long-term maintenance) | ✅ Reduced - Architectural review before implementation |
| **Team Confusion on MVP Scope** | Medium (60%) | Medium (wasted effort) | ✅ Eliminated - Clear IN/OUT scope documentation |

### Residual Risks & Mitigations

| Residual Risk | Probability | Impact | Mitigation Strategy |
|--------------|-------------|--------|---------------------|
| **Growth Phase Underestimation** | Low (20%) | Medium | Reference doc provides detailed sub-task breakdown; re-estimate when planning Growth epic |
| **StubProvider Insufficient for Testing** | Low (15%) | Low | Reference doc describes both approaches; can pivot to Simplified (S-001~S-004) if needed |
| **EQC API Changes After MVP** | Low (10%) | Low | Provider abstraction decouples implementation; API changes isolated to EqcProvider |
| **Documentation Becomes Stale** | Medium (40%) | Low | Link reference doc from PRD/Architecture; single source of truth principle |

### Rollback Plan

**If Decision Reversed (Use Full Enrichment in MVP):**

**Steps:**
1. Revert 3 documentation updates (git revert)
2. Re-run `/create-epics-and-stories` with full enrichment scope
3. Increase MVP epic sizing by ~10-13 story points
4. Extend MVP timeline by ~2-3 sprints
5. Increase risk profile to "High" (external API dependency in MVP)

**Likelihood:** Very Low (StubProvider approach is sound architectural decision)

---

## Appendices

### Appendix A: Reference Documentation Index

**Primary Source:**
- `reference/01_company_id_analysis.md` (150 lines)
  - §1: Problem definition and historical context
  - §2: Business objectives and success criteria
  - §3: Constraints and design principles
  - §4: Input signals and data assets
  - §5: Temporary ID and governance strategy
  - §6: CI-002 architecture blueprint (Complex approach)
  - §7: CI-002 sub-task breakdown (8 tasks)
  - §8: EQC integration and credential management
  - §9: Simplified approach (S-001~S-004)
  - §10: Legacy adaptation and data migration
  - §11: Observability and operational metrics
  - §12: Risks and lessons learned
  - §13: Recommendations for new team
  - Appendix A: Environment variables (11 variables)
  - Appendix B: Common commands
  - Appendix C: Reference document index

**Archive:**
- `reference/archive/context-engineering-intro/docs/company_id/complicated/`: Complex approach detailed docs
- `reference/archive/context-engineering-intro/docs/company_id/simplified/`: Simplified approach detailed docs
- `reference/archive/context-engineering-intro/docs/company_id/plan/`: Implementation plans and PoCs
- `reference/archive/context-engineering-intro/docs/company_id/EQC/`: EQC integration specifics

### Appendix B: Environment Variables Quick Reference

| Variable | MVP Need | Growth Need | Default | Description |
|----------|----------|-------------|---------|-------------|
| `WDH_ALIAS_SALT` | ✅ Required | ✅ Required | None | HMAC salt for temporary ID generation |
| `WDH_ENRICH_COMPANY_ID` | ✅ Required | ✅ Required | `0` | Enable/disable enrichment service |
| `WDH_ENTERPRISE_PROVIDER` | ✅ Required | ✅ Required | `stub` | Provider selection (stub/eqc/legacy) |
| `WDH_ENRICH_SYNC_BUDGET` | ❌ Not Used | ✅ Required | `0` | Sync API call budget |
| `WDH_PROVIDER_EQC_TOKEN` | ❌ Not Used | ✅ Required | None | EQC API token (30-min validity) |
| `WDH_PROVIDER_EQC_BASE_URL` | ❌ Not Used | ⚠️ Optional | Default | EQC API endpoint override |
| `WDH_COMPANY_ENRICHMENT_ENABLED` | ⚠️ Optional | ⚠️ Optional | `0` | Simplified approach toggle |
| `WDH_COMPANY_SYNC_LOOKUP_LIMIT` | ❌ Not Used | ✅ Required | `5` | Sync lookup limit (S-003) |
| `WDH_LOOKUP_QUEUE_BATCH_SIZE` | ❌ Not Used | ✅ Required | `50` | Queue batch size |
| `WDH_LOOKUP_RETRY_MAX` | ❌ Not Used | ✅ Required | `3` | Max retry attempts |
| `WDH_LOOKUP_RETRY_DELAY` | ❌ Not Used | ✅ Required | `300` | Retry delay (seconds) |

### Appendix C: Epic Sizing Comparison

**Scenario Analysis:**

| Scenario | Epic Scope | Stories | Points | Timeline | Risk |
|----------|-----------|---------|--------|----------|------|
| **Original (No Discovery)** | Single epic, underestimated | 2 stories → expands to 13-16 mid-sprint | 3-5 → expands to 21-26 | 1 sprint → becomes 3-4 sprints | High (300-400% creep) |
| **Recommended (StubProvider MVP)** | Two epics (MVP + Growth), properly scoped | MVP: 2 stories; Growth: 4-6 stories | MVP: 3; Growth: 8-10 | MVP: 1 sprint; Growth: 2 sprints | Low (clear scope) |
| **Alternative (Full MVP)** | Single epic, fully scoped | 13-16 stories | 21-26 | 3-4 sprints | High (external API in MVP) |

**Recommendation Validation:** StubProvider MVP approach balances risk, scope clarity, and incremental value delivery.

---

## Conclusion

This Sprint Change Proposal documents a **positive finding** caught at the **ideal time** in the project lifecycle. The company ID enrichment complexity was identified after PRD completion but before Architecture/Epic creation, allowing proper scoping without rework.

**Key Outcomes:**
1. ✅ **3 approved documentation updates** prevent 300-400% scope creep
2. ✅ **MVP scope clarified** (StubProvider approach, ~3 points)
3. ✅ **Growth phase roadmap documented** (Simplified vs. Complex approaches)
4. ✅ **No timeline impact** (actually prevents future delays)
5. ✅ **No code changes required** (documentation-only)

**Next Steps:**
1. Obtain PM approval for this proposal
2. Apply 3 approved edits to PRD, Architecture, .env
3. Create supporting artifacts (test guide, DDL scripts, README link)
4. Proceed to `/create-architecture` or `/create-epics-and-stories`

**Change Scope:** MINOR (Documentation-only, preventive)
**Timeline Impact:** NONE (prevents future delays)
**Risk Level:** LOW (no code changes, caught before implementation)

---

**Document prepared by:** John (Product Manager Agent)
**For approval by:** Link (Product Manager)
**Workflow:** Correct Course - Sprint Change Management
**Date:** 2025-11-08

---

*This Sprint Change Proposal follows BMad Method (BMM) workflows and best practices for navigating significant changes during project planning phases.*
