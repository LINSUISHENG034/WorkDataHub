# Product Scope

### MVP - Minimum Viable Product
**"Prove the pattern works on real complexity"**

**Goal:** Successfully migrate the **highest-complexity domain** (annuity performance) using the Strangler Fig pattern, proving the architecture can replace legacy code with zero regression.

**Core MVP Deliverables:**

1. **Annuity Performance Domain - Complete Migration**
   - ✅ Refactor existing `domain/annuity_performance/` to use shared pipeline framework
   - ✅ Integrate company enrichment service adapter for data augmentation
   - ✅ Implement Bronze → Silver → Gold layered architecture
   - ✅ Add pandera data contracts at layer boundaries (DataFrame validation)
   - ✅ Create golden dataset regression suite (100% parity with legacy output)
   - ✅ Parallel execution with legacy system + automated reconciliation
   - ✅ Production validation and legacy code deletion

2. **Core Infrastructure - Battle-Tested**
   - ✅ Shared pipeline framework (`domain/pipelines/core.py`) - proven with annuity domain
   - ✅ Cleansing framework with registry-driven rules (`cleansing/registry.py`)
   - ✅ Configuration-driven file discovery (auto-detect V1, V2 versions)
   - ✅ Dagster orchestration layer with jobs, schedules, sensors
   - ✅ PostgreSQL transactional loading with error handling
   - ✅ Pydantic v2 models for row-level validation

3. **Version Detection System**
   - ✅ Automatically identify latest data version across domains (V1, V2, etc.)
   - ✅ Smart file pattern matching for monthly data drops (`reference/monthly/YYYYMM/收集数据/`)
   - ✅ Configurable version precedence rules per domain

4. **Data Quality Foundation**
   - ✅ Bronze layer validation (reject bad source data immediately)
   - ✅ Pydantic models with Chinese field names matching Excel sources
   - ✅ Pandera DataFrame contracts enforcing schema at layer boundaries
   - ✅ Clear error messages with actionable guidance

**MVP Success Criteria:**
- ✅ Annuity performance domain processes monthly data with 100% parity to legacy
- ✅ Version detection works across V1/V2 variations automatically
- ✅ Golden dataset regression tests pass (no output differences)
- ✅ Team member can understand and modify annuity pipeline in <2 hours

**Out of Scope for MVP:**
- ❌ Migrating all 6+ domains (only annuity domain)
- ❌ Performance optimization beyond "good enough" (<30 min per domain)
- ❌ Advanced scheduling (basic monthly triggers sufficient)
- ❌ UI/dashboard for pipeline monitoring (Dagster UI is sufficient)

---

### Growth Features (Post-MVP)
**"Complete the migration - all domains on modern platform"**

**Goal:** Migrate remaining 5+ data domains following the proven annuity pattern, achieving complete legacy system retirement.

**Additional Domains to Migrate:**

Based on actual implemented domains in `src/work_data_hub/domain/`:

1. **annuity_income (年金收入)**
   - Annuity income tracking and reporting
   - Pattern: Similar to annuity_performance (adapter, models, pipeline_builder, schemas, service)
   - Status: Implemented

2. **annual_award (年度奖励)**
   - Annual award calculations and tracking
   - Pattern: Standard domain pattern (adapter, constants, helpers, models, pipeline_builder, schemas, service)
   - Status: Implemented

3. **annual_loss (年度亏损)**
   - Annual loss tracking and reporting
   - Pattern: Standard domain pattern (same as annual_award)
   - Status: Implemented

4. **company_enrichment (企业信息enrichment)**
   - Company ID resolution via multi-tier strategy (internal mapping → EQC API → async queue)
   - Pattern: Specialized (lookup_queue, models, observability, service)
   - Status: Implemented with full provider abstraction

5. **reference_backfill (参考数据回填)**
   - Reference data backfill with generic/hybrid/sync service patterns
   - Pattern: Specialized (config_loader, generic_service, hybrid_service, sync_service, models, observability)
   - Status: Implemented

6. **sandbox_trustee_performance (受托人业绩沙盒)**
   - Dev/test sandbox for trustee performance domain
   - Pattern: Lightweight (adapter, models, service)
   - Status: Sandbox/experimental

7. **customer_mdm (客户主数据管理)** — Standalone module
   - Customer lifecycle management: sync, snapshot, init-year, validate, cutover
   - Has dedicated CLI sub-commands
   - Status: Implemented as independent module outside domain/

**Growth Features:**

1. **Remaining Domain Migration**
   - Migrate any remaining data domains from legacy system
   - Standardize golden dataset test creation per domain
   - Document domain-specific patterns

2. **Enhanced Orchestration**
   - Cross-domain dependency management (if domain B needs domain A output)
   - Smart scheduling (trigger dependent domains automatically)
   - Parallel execution of independent domains

3. **Improved Version Detection**
   - Machine learning-based "latest file" detection (if naming patterns vary)
   - Version conflict resolution (what if V1 and V2 both exist?)
   - Historical version tracking

4. **Operational Tooling**
   - CLI tools for common operations (re-run domain, validate parity, etc.)
   - Data quality dashboard (track validation failures across domains)
   - Reconciliation reports (new vs legacy output comparison)

**Growth Success Criteria:**
- ✅ All core domains migrated and validated (8 domains currently implemented)
- ✅ Customer MDM module operational with full lifecycle management
- ✅ Legacy `legacy/annuity_hub/` completely deleted
- ✅ Monthly data processing runs unattended across all domains
- ✅ <2% failure rate in production

---

### Vision (Future)
**"Beyond parity - intelligent automation"**

**Goal:** Transform WorkDataHub from a legacy replacement into an intelligent data platform that prevents issues before they occur and adapts to changing data sources.

**Vision Features:**

1. **Predictive Data Quality**
   - ML models that learn "normal" data patterns per domain
   - Anomaly detection: "This month's portfolio values are 30% higher than usual - likely data error"
   - Proactive alerts before bad data reaches database

2. **Self-Healing Pipelines**
   - Automatic retry with exponential backoff for transient failures
   - Smart fallback strategies (use previous month's mapping if new one is missing)
   - Auto-generate cleansing rules from repeated manual corrections

3. **Natural Language Configuration**
   - "Add validation: account numbers must be 10 digits"
   - AI-assisted cleansing rule creation from examples
   - Plain English domain documentation generation

4. **Intelligent Schema Evolution**
   - Detect when Excel source schema changes (new columns, renamed fields)
   - Suggest Pydantic model updates automatically
   - Migration scripts for historical data when schema evolves

5. **Advanced Analytics Integration**
   - Real-time data quality metrics exposed to PowerBI
   - Pipeline performance dashboards (processing time trends, bottlenecks)
   - Predictive load times ("Next month's data will take 45 minutes based on growth trends")

6. **Multi-Source Fusion**
   - Automatically join/enrich data from multiple sources (Excel + database + API)
   - Conflict resolution when same data appears in multiple sources
   - Master data management patterns

**Vision Success Criteria:**
- ✅ Data quality issues caught before human review 90% of the time
- ✅ Schema changes automatically detected and suggested (human approval still required)
- ✅ Zero manual intervention for 95% of monthly data drops

---

**Scope Philosophy - Strangler Fig Migration:**

This scope follows the **Strangler Fig pattern** (from Gemini research):

1. **MVP** = Strangle the hardest piece (annuity domain) to prove the pattern
2. **Growth** = Systematically strangle remaining domains one-by-one
3. **Vision** = New capabilities only possible with modern architecture

Each phase delivers value independently. No "big bang" rewrite risk.

---
