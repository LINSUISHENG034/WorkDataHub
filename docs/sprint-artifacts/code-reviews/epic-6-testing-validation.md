# Epic 6: Testing & Validation Infrastructure

**Goal:** Build the testing infrastructure required to validate 100% parity between legacy and modern pipelines, enabling confident legacy system retirement. This epic implements the Strangler Fig pattern's validation phase, ensuring zero regression when cutover occurs.

**Business Value:** Cannot retire legacy system without proof of 100% parity. Epic 6 provides automated reconciliation, regression detection, and divergence reporting that makes legacy code deletion safe. This is the "trust but verify" layer that enables the entire modernization strategy.

**Dependencies:** Epic 1 (infrastructure), Epic 4 (annuity domain migration with shadow table)

**NFR Support:** NFR-2.2 (100% legacy parity), NFR-3.2 (test coverage >80%), NFR-5.2 (debuggability)

**Sequencing:** Execute Stories 6.1-6.2 in parallel with Epic 4 Stories 4.3-4.4, complete Stories 6.3-6.4 before Epic 4 Story 4.5 finishes

---

## Story 6.1: Golden Dataset Extraction from Legacy System

As a **data engineer**,
I want **automated extraction of legacy pipeline outputs as golden datasets**,
So that **I have a ground truth baseline for validating new pipeline outputs without manual data collection**.

### Acceptance Criteria

**Given** I have the legacy annuity pipeline running in production
**When** I execute golden dataset extraction for a specific month (e.g., 202501)
**Then** System should:
- Connect to legacy database tables (read-only permissions)
- Extract complete output dataset: `SELECT * FROM legacy.annuity_performance WHERE 月度 = '202501'`
- Export to versioned golden dataset file: `tests/golden/annuity_performance_202501_v1.csv`
- Include metadata: extraction timestamp, row count, legacy system version, source table name
- Validate completeness: compare row count against legacy audit log
- Store MD5 hash of golden dataset for integrity verification

**And** When golden dataset extracted successfully
**Then** Metadata file created: `tests/golden/annuity_performance_202501_v1.meta.json`
```json
{
  "extraction_timestamp": "2025-11-09T16:30:00Z",
  "source_table": "legacy.annuity_performance",
  "filter_criteria": "月度 = '202501'",
  "row_count": 1250,
  "column_count": 15,
  "legacy_system_version": "v2.3.1",
  "md5_hash": "a1b2c3d4e5f6...",
  "extracted_by": "golden_dataset_extractor_v1"
}
```

**And** When I extract golden dataset for multiple months (202501, 202502, 202503)
**Then** Each month has separate versioned files (enables historical validation)

**And** When legacy data changes after initial extraction
**Then** Extract new version: `annuity_performance_202501_v2.csv` (versioning prevents overwrite)

**And** When extraction fails (e.g., table locked, connection timeout)
**Then** Clear error message with retry instructions and rollback guidance

### Prerequisites
- Epic 1 Story 1.8 (database connection)
- Epic 4 Story 4.5 (know which legacy tables to extract)

### Technical Notes

**Implementation:**
- Implement in `tests/golden/extractor.py` as standalone script
- Use Epic 1 Story 1.8 WarehouseLoader pattern for database connection
- Read-only database role: prevent accidental legacy data modification

**Versioning Strategy:**
- Format: `{domain}_{month}_v{N}.csv` where N increments on re-extraction
- Example: `annuity_performance_202501_v1.csv`, `annuity_performance_202501_v2.csv`

**Data Format:**
- CSV format for human readability (easier to diff than binary formats)
- UTF-8 encoding for Chinese characters
- Include all columns from legacy table

**Execution:**
```bash
python tests/golden/extractor.py --domain=annuity_performance --month=202501
```

**Storage:**
- Golden datasets stored in `tests/golden/` directory
- `.gitignore` if contains real data, or use anonymized test database
- Alternative: Use anonymized test database for CI-safe golden datasets

**References:**
- PRD §952-976 (FR-6: Migration Support)
- NFR-2.2 (100% parity requirement)

---

## Story 6.2: Automated Reconciliation Engine

As a **data engineer**,
I want **automated row-by-row reconciliation between golden dataset and new pipeline output**,
So that **I can detect any differences programmatically without manual spreadsheet comparison**.

### Acceptance Criteria

**Given** I have golden dataset from Story 6.1 and new pipeline output from Epic 4 Story 4.5
**When** I run reconciliation for annuity domain, month 202501
**Then** Reconciliation engine should:
- Load golden dataset: `tests/golden/annuity_performance_202501_v1.csv`
- Load new output: Query `SELECT * FROM annuity_performance_NEW WHERE 月度 = '202501'`
- Normalize both datasets: sort by composite PK (月度, 计划代码, company_id), standardize column order
- Compare row-by-row: detect missing rows, extra rows, field-level differences
- Generate reconciliation report: `tests/results/reconciliation_annuity_202501_{timestamp}.json`
- Calculate metrics: total rows, matched rows, divergent rows, match percentage

**And** When 100% parity achieved (all rows match exactly)
**Then** Reconciliation report shows:
```json
{
  "reconciliation_timestamp": "2025-11-09T17:00:00Z",
  "domain": "annuity_performance",
  "month": "202501",
  "golden_dataset": "tests/golden/annuity_performance_202501_v1.csv",
  "golden_row_count": 1250,
  "new_output_row_count": 1250,
  "matched_rows": 1250,
  "divergent_rows": 0,
  "missing_in_new": 0,
  "extra_in_new": 0,
  "match_percentage": 100.0,
  "status": "PASS",
  "divergences": []
}
```

**And** When divergences detected (e.g., 5 rows with different `期末资产规模` values)
**Then** Reconciliation report includes detailed divergences:
```json
{
  "match_percentage": 99.6,
  "status": "FAIL",
  "divergent_rows": 5,
  "divergences": [
    {
      "composite_pk": {"月度": "2025-01-01", "计划代码": "ABC123", "company_id": "COMP001"},
      "field": "期末资产规模",
      "golden_value": 1234567.89,
      "new_value": 1234567.90,
      "difference": 0.01,
      "difference_type": "numeric_precision"
    }
  ]
}
```

**And** When rows missing in new output
**Then** Report includes: `"missing_in_new": [{"月度": "2025-01-01", "计划代码": "XYZ789", ...}]`

**And** When extra rows in new output (not in golden dataset)
**Then** Report includes: `"extra_in_new": [{"月度": "2025-01-01", "计划代码": "NEW123", ...}]`

**And** When numeric precision differences <0.01 detected (floating-point rounding)
**Then** Reconciliation classifies as "WARN" (not automatic failure), logs tolerance exceeded

### Prerequisites
- Story 6.1 (golden datasets)
- Epic 4 Story 4.5 (new pipeline output in database)

### Technical Notes

**Implementation:**
- File: `tests/reconciliation/engine.py`
- Use pandas DataFrames for efficient comparison: `pd.DataFrame.compare()` or custom logic

**Composite PK Matching:**
- Key: `(月度, 计划代码, company_id)` must be unique in both datasets
- Sorting for comparison ensures row alignment

**Field-Level Comparison:**
- **Numeric fields:** Allow tolerance ±0.01 for floating-point precision (configurable)
- **String fields:** Exact match (case-sensitive)
- **Date fields:** Normalize to `date` objects before comparison
- **Null handling:** `None` == `None`, `None` != `0`

**Performance Optimization:**
For large datasets (>100K rows), use SQL joins:
```sql
SELECT g.*, n.*
FROM golden_temp g
FULL OUTER JOIN annuity_performance_NEW n
  ON g.月度 = n.月度
  AND g.计划代码 = n.计划代码
  AND g.company_id = n.company_id
WHERE g.月度 IS NULL
   OR n.月度 IS NULL
   OR g.期末资产规模 != n.期末资产规模
```

**CLI Execution:**
```bash
python tests/reconciliation/engine.py \
  --domain=annuity_performance \
  --month=202501 \
  --tolerance=0.01
```

**Output Formats:**
- JSON (machine-readable): `reconciliation_annuity_202501.json`
- Markdown (human-readable): `reconciliation_annuity_202501.md`

**References:**
- PRD §952-976 (FR-6.2: Automated Reconciliation)

---

## Story 6.3: Parity Test Integration in CI Pipeline

As a **data engineer**,
I want **reconciliation automatically executed in CI pipeline with merge blocking on parity failures**,
So that **code changes breaking parity are caught before merge, preventing regression**.

### Acceptance Criteria

**Given** I have reconciliation engine from Story 6.2 integrated into CI pipeline
**When** PR submitted with changes to Epic 4 annuity pipeline code
**Then** CI should:
- Provision temporary test database (via Epic 1 Story 1.11 pytest-postgresql or Docker)
- Run Epic 1 Story 1.7 migrations (create schema including `annuity_performance_NEW`)
- Execute new annuity pipeline against test golden dataset: `tests/golden/annuity_performance_test.csv`
- Run reconciliation engine comparing golden vs new output
- Report reconciliation results in CI logs
- Block merge if `status: "FAIL"` (match_percentage < 100%)
- Allow merge if `status: "PASS"` (100% parity) or `status: "WARN"` (tolerance differences only)

**And** When parity test passes (100% match)
**Then** CI logs show:
```
✅ Parity Test PASSED
   Domain: annuity_performance
   Golden Dataset: tests/golden/annuity_performance_test.csv
   Rows Matched: 150/150 (100.0%)
   Divergences: 0
   Status: PASS
```

**And** When parity test fails (divergences detected)
**Then** CI fails with actionable error:
```
❌ Parity Test FAILED
   Domain: annuity_performance
   Golden Dataset: tests/golden/annuity_performance_test.csv
   Rows Matched: 145/150 (96.7%)
   Divergent Rows: 5
   Status: FAIL

   Divergence Details:
   - PK (2025-01-01, ABC123, COMP001): 期末资产规模 differs
     (golden: 1234567.89, new: 1234567.90)

   Action Required:
   1. Review divergences in: tests/results/reconciliation_annuity_test.json
   2. Fix pipeline logic to match legacy behavior OR
   3. Update golden dataset if legacy behavior was incorrect
   4. Re-run CI after fixes
```

**And** When tolerance-level differences detected (match_percentage = 99.99%)
**Then** CI warns but allows merge (configurable threshold):
```
⚠️ Parity Test WARNING
   Status: WARN (tolerance differences only)
   Numeric precision differences: 2 fields with delta <0.01
   Merge allowed (configure PARITY_STRICT_MODE=true to block)
```

**And** When test database provisioning fails
**Then** CI fails fast with infrastructure error (not parity failure)

**And** When multiple domains added (Epic 9 future), each domain has parity test
**Then** CI runs parity tests in parallel for speed (target: <5 min total)

### Prerequisites
- Story 6.2 (reconciliation engine)
- Epic 1 Story 1.11 (CI/CD infrastructure)

### Technical Notes

**pytest Implementation:**
```python
# tests/parity/test_annuity_parity.py

@pytest.mark.parity
def test_annuity_parity(test_db, golden_dataset_path):
    # Execute new pipeline against test database
    result = run_annuity_pipeline(test_db, input_file=golden_dataset_path)

    # Load golden dataset
    golden_df = pd.read_csv(golden_dataset_path)

    # Run reconciliation
    reconciliation = ReconciliationEngine().compare(
        golden=golden_df,
        new_output=test_db.query("SELECT * FROM annuity_performance_NEW"),
        tolerance=0.01
    )

    # Assert 100% parity
    assert reconciliation.status == "PASS", \
        f"Parity test failed: {reconciliation.divergent_rows} divergences. " \
        f"See {reconciliation.report_path} for details."
```

**CI Configuration (GitHub Actions):**
```yaml
- name: Run Parity Tests
  run: pytest -m parity --verbose
  env:
    PARITY_STRICT_MODE: "false"  # Allow tolerance warnings
```

**Test Database Setup:**
- Use pytest fixtures from Epic 1 Story 1.11
- Provision temporary PostgreSQL instance (Docker or pytest-postgresql)
- Run Alembic migrations to create schema
- Clean up after test completion

**Test Golden Dataset:**
- **CI dataset:** Small, synthetic dataset (150 rows) for fast execution
- **Production dataset:** Real data (1000+ rows) for pre-release validation
- Store CI dataset in git: `tests/golden/annuity_performance_test.csv`

**Merge Blocking:**
- GitHub branch protection rule requires "Parity Tests" check pass
- Configure in repository settings: "Require status checks to pass before merging"

**References:**
- PRD §966-976 (FR-6.3: Golden Dataset Test Suite)
- NFR-2.2 (100% parity enforcement)

---

## Story 6.4: Divergence Reporting and SQL Diff Tool

As a **data engineer**,
I want **human-readable divergence reports with SQL queries to reproduce differences**,
So that **I can quickly debug parity failures and verify fixes without manual data inspection**.

### Acceptance Criteria

**Given** I have reconciliation report from Story 6.2 with divergences
**When** I generate divergence report for failed parity test
**Then** Report should include:
- Executive summary: domain, month, match percentage, total divergences
- Divergence breakdown by type: missing rows, extra rows, field mismatches
- Top 10 divergences sorted by significance (largest numeric differences first)
- SQL queries to reproduce each divergence category
- Suggested actions for common divergence patterns

**And** When report generated for 5 divergent rows (field mismatches)
**Then** Markdown report created: `tests/results/divergence_report_annuity_202501.md`

Example report content:
```markdown
# Divergence Report: Annuity Performance (202501)

**Generated:** 2025-11-09 17:15:00
**Status:** FAIL (96.7% match)
**Total Rows:** 150
**Matched:** 145
**Divergent:** 5

---

## Divergence Summary

| Category | Count | Severity |
|----------|-------|----------|
| Field Mismatches | 5 | Medium |
| Missing in New | 0 | - |
| Extra in New | 0 | - |

---

## Field Mismatch Details

### Divergence #1 (Highest Impact)
**Composite PK:** (2025-01-01, ABC123, COMP001)
**Field:** `期末资产规模`
**Golden Value:** 1,234,567.89
**New Value:** 1,234,567.90
**Difference:** +0.01 (0.0008%)

**SQL to Reproduce:**
```sql
-- Golden Dataset (Legacy)
SELECT 月度, 计划代码, company_id, 期末资产规模
FROM golden.annuity_performance_202501
WHERE 月度 = '2025-01-01'
  AND 计划代码 = 'ABC123'
  AND company_id = 'COMP001';
-- Result: 1234567.89

-- New Pipeline Output
SELECT 月度, 计划代码, company_id, 期末资产规模
FROM annuity_performance_NEW
WHERE 月度 = '2025-01-01'
  AND 计划代码 = 'ABC123'
  AND company_id = 'COMP001';
-- Result: 1234567.90
```

**Possible Causes:**
- Floating-point rounding in transformation step
- Different calculation order (e.g., sum then divide vs divide then sum)
- Numeric precision difference between legacy (DECIMAL) and new (FLOAT)

**Suggested Action:**
- Review calculation logic in Epic 4 Story 4.3 transformation pipeline
- Consider using DECIMAL type for currency fields
- Evaluate if ±0.01 tolerance is acceptable for business requirements
```

**And** When divergence is missing row (row in golden, not in new)
**Then** Report includes:
```markdown
### Missing Row #1
**Composite PK:** (2025-01-01, XYZ789, COMP002)

**SQL to Find Missing Row in Legacy:**
```sql
SELECT * FROM golden.annuity_performance_202501
WHERE 月度 = '2025-01-01'
  AND 计划代码 = 'XYZ789'
  AND company_id = 'COMP002';
```

**SQL to Verify Absence in New:**
```sql
SELECT * FROM annuity_performance_NEW
WHERE 月度 = '2025-01-01'
  AND 计划代码 = 'XYZ789'
  AND company_id = 'COMP002';
-- Expected: 0 rows (MISSING)
```

**Possible Causes:**
- Row filtered out during Bronze validation (check `logs/failed_rows_*.csv`)
- Row failed Silver validation (check Pydantic error logs)
- File discovery missed source file (check patterns in `config/data_sources.yml`)
```

**And** When divergence is extra row (row in new, not in golden)
**Then** Report flags for investigation (possible data quality improvement or bug)

**And** When common pattern detected (e.g., all divergences are ±0.01 rounding)
**Then** Report includes pattern analysis:
```markdown
## Pattern Analysis

**Detected Pattern:** All 5 divergences are numeric precision differences ≤0.01
**Affected Fields:** `期末资产规模` (5 rows)
**Recommendation:** Consider adjusting tolerance to 0.01 or using DECIMAL type.
**Config Change:** Set `PARITY_TOLERANCE=0.01` in `.env` to allow these differences.
```

**And** When I view divergence report
**Then** I can copy SQL queries directly to database client for debugging

### Prerequisites
- Story 6.2 (reconciliation engine with divergence details)

### Technical Notes

**Implementation:**
- File: `tests/reconciliation/report_generator.py`
- Input: JSON reconciliation report from Story 6.2
- Output: Markdown report (human-readable) + optional HTML (rich formatting)

**SQL Query Generation:**
- Use composite PK to build WHERE clause
- Escape special characters in field values (SQL injection prevention)
- Format numeric values with proper precision (match database types)

**Pattern Detection Algorithms:**
- **Numeric precision:** All divergences <0.01 → suggest tolerance adjustment
- **Systematic offset:** All divergences +X or -X → suggest calculation bug
- **Specific field:** All divergences in same column → suggest field-specific issue

**Severity Ranking:**
- 🔴 **High:** Missing/extra rows (potential data loss)
- 🟠 **Medium:** Large numeric differences (>1% of value)
- 🟡 **Low:** Small numeric differences (<0.01%), date format differences

**Markdown Formatting:**
- Use tables, code blocks, and severity emojis for readability
- Include actionable suggestions for each divergence type
- Link to relevant story documentation

**CLI Execution:**
```bash
python tests/reconciliation/report_generator.py \
  --input=reconciliation_annuity_202501.json \
  --output=divergence_report.md
```

**References:**
- PRD §966-976 (FR-6: Migration Support - debugging support)
- NFR-5.2 (Debuggability)

---

## Epic 6 Summary

### Stories Overview

| Story | Title | Estimated Effort | Dependencies |
|-------|-------|------------------|--------------|
| 6.1 | Golden Dataset Extraction | 3-4 days | Epic 1.8, Epic 4.5 |
| 6.2 | Automated Reconciliation Engine | 4-5 days | Story 6.1, Epic 4.5 |
| 6.3 | Parity Test Integration in CI | 3-4 days | Story 6.2, Epic 1.11 |
| 6.4 | Divergence Reporting | 2-3 days | Story 6.2 |

**Total Estimated Effort:** 2-3 weeks (1 developer) or 1-2 weeks (2 developers in parallel)

### Parallel Execution Strategy

**Track 1 (Developer A):**
- Story 6.1: Golden Dataset Extraction (3-4 days)
- Story 6.3: Parity Test Integration (3-4 days)

**Track 2 (Developer B):**
- Story 6.2: Automated Reconciliation Engine (4-5 days)
- Story 6.4: Divergence Reporting (2-3 days)

**Synchronization Point:** Story 6.3 requires 6.2 completion, so Track 1 can start Story 6.1 first while Track 2 builds Story 6.2.

### Critical Success Factors

✅ **Golden dataset extraction must capture 100% of legacy output** (no sampling)
✅ **Reconciliation engine must handle all data types** (dates, currency, Chinese strings)
✅ **CI integration must block merge on failures** (enforce 100% parity)
✅ **Divergence reports must provide actionable debugging guidance** (SQL queries + suggestions)

### Value Delivered

🎯 **Enables confident legacy system retirement** (100% parity proven)
🎯 **Reduces manual QA effort** (automated reconciliation vs spreadsheet comparison)
🎯 **Prevents regression via CI enforcement** (parity tests run on every PR)
🎯 **Accelerates debugging** (SQL diff tool pinpoints exact divergences)

### Integration with Existing Epics

**Epic 1 (Foundation):**
- Story 1.8 (Database connection) enables golden dataset extraction
- Story 1.11 (CI/CD) provides infrastructure for parity tests

**Epic 4 (Annuity Migration):**
- Story 4.5 (End-to-end integration) depends on Epic 6 parity validation
- Story 4.6 (Documentation) should include parity test runbook

**Epic 9 (Future Growth Domains):**
- Each new domain will reuse Epic 6 testing infrastructure
- Pattern established: extract golden dataset → build pipeline → validate parity → cutover

### NFR Compliance

| NFR | How Epic 6 Addresses It |
|-----|-------------------------|
| NFR-2.2 (100% legacy parity) | ✅ Automated reconciliation proves parity before cutover |
| NFR-3.2 (>80% test coverage) | ✅ Parity tests cover entire data pipeline end-to-end |
| NFR-5.2 (Debuggability) | ✅ SQL diff tool and divergence reports accelerate debugging |

---

**Epic 6 Status:** ✅ **DEFINED AND READY FOR IMPLEMENTATION**

This epic can now be added to your sprint planning and scheduled for execution in parallel with Epic 4 Stories 4.3-4.4.
