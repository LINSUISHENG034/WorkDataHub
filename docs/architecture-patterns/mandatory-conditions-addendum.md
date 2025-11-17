# Mandatory Conditions Addendum

**Purpose:** This document specifies the mandatory enhancements to Epic 1 Stories 1.7 and 1.11 required before Epic 4 completion, as identified in the Implementation Readiness Report (2025-11-09).

**Status:** ✅ All 3 mandatory conditions satisfied (documented)

---

## ✅ Condition #1: Epic 6 Stories Defined

**Status:** ✅ COMPLETE
**Document:** `docs/epic-6-testing-validation.md`
**Stories:** 6.1, 6.2, 6.3, 6.4 (4 minimum viable stories)

---

## ✅ Condition #2: Audit Table Schema Added to Story 1.7

**Story:** Epic 1 Story 1.7 - Database Schema Management Framework
**Requirement:** Add `audit.pipeline_executions` table to initial migration for FR-4.3 (Audit Logging)

### Acceptance Criteria Addition

**Given** I am implementing Story 1.7 initial migration
**When** I create the core tables migration
**Then** I must also create `audit.pipeline_executions` table with the following schema:

```sql
-- Migration: YYYYMMDD_HHMM_create_audit_pipeline_executions.py

CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE audit.pipeline_executions (
    -- Primary identification
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pipeline metadata
    pipeline_name VARCHAR(100) NOT NULL,
    domain VARCHAR(50) NOT NULL,

    -- Execution status
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'failed', 'partial')),

    -- File processing metadata
    file_path TEXT,
    file_version VARCHAR(10),  -- e.g., 'V1', 'V2', 'V3'

    -- Data metrics
    rows_discovered INTEGER,
    rows_processed INTEGER,
    rows_loaded INTEGER,
    rows_failed INTEGER,

    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    -- Error tracking
    error_message TEXT,
    error_stack_trace TEXT,

    -- Audit metadata
    created_by VARCHAR(100) DEFAULT CURRENT_USER,
    dagster_run_id VARCHAR(100),  -- Link to Dagster execution (Epic 1.9)

    -- Indexes for common queries
    CONSTRAINT check_completed_at CHECK (
        (status = 'running' AND completed_at IS NULL) OR
        (status IN ('success', 'failed', 'partial') AND completed_at IS NOT NULL)
    )
);

CREATE INDEX idx_pipeline_executions_domain_month
    ON audit.pipeline_executions(domain, started_at DESC);

CREATE INDEX idx_pipeline_executions_status
    ON audit.pipeline_executions(status, started_at DESC);

CREATE INDEX idx_pipeline_executions_dagster_run
    ON audit.pipeline_executions(dagster_run_id);

-- Grant permissions (adjust based on your database roles)
GRANT SELECT, INSERT, UPDATE ON audit.pipeline_executions TO work_data_hub_app;
GRANT SELECT ON audit.pipeline_executions TO work_data_hub_readonly;

COMMENT ON TABLE audit.pipeline_executions IS 'Audit log of all pipeline executions for compliance and debugging (FR-4.3)';
COMMENT ON COLUMN audit.pipeline_executions.status IS 'running: in progress, success: all rows loaded, failed: pipeline error, partial: some rows loaded';
COMMENT ON COLUMN audit.pipeline_executions.file_version IS 'Version detection from Epic 3 Story 3.1 (V1/V2/V3)';
```

### Integration with Epic 4 Story 4.5

**When** implementing Epic 4 Story 4.5 (Annuity End-to-End Integration)
**Then** the pipeline must insert audit records:

```python
# At pipeline start
execution_id = uuid.uuid4()
audit_record = {
    "execution_id": execution_id,
    "pipeline_name": "annuity_performance_pipeline",
    "domain": "annuity_performance",
    "status": "running",
    "file_path": str(input_file_path),
    "file_version": discovery_result.version,  # From Epic 3.1
    "rows_discovered": len(discovery_result.files),
    "started_at": datetime.utcnow()
}
db.insert("audit.pipeline_executions", audit_record)

# At pipeline completion (success)
db.update("audit.pipeline_executions",
    where={"execution_id": execution_id},
    values={
        "status": "success",
        "rows_processed": metrics.rows_processed,
        "rows_loaded": metrics.rows_loaded,
        "rows_failed": metrics.rows_failed,
        "completed_at": datetime.utcnow(),
        "duration_ms": (datetime.utcnow() - started_at).total_seconds() * 1000
    }
)

# At pipeline failure
db.update("audit.pipeline_executions",
    where={"execution_id": execution_id},
    values={
        "status": "failed",
        "completed_at": datetime.utcnow(),
        "error_message": str(error),
        "error_stack_trace": traceback.format_exc()
    }
)
```

### Validation Queries

**Test queries to validate audit table:**

```sql
-- Recent pipeline executions
SELECT execution_id, pipeline_name, domain, status,
       rows_loaded, duration_ms, started_at
FROM audit.pipeline_executions
ORDER BY started_at DESC
LIMIT 10;

-- Success rate by domain (for NFR-2.3: >98% success rate)
SELECT
    domain,
    COUNT(*) as total_runs,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
FROM audit.pipeline_executions
WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY domain;

-- Pipeline execution history for Epic 6 reconciliation
SELECT execution_id, file_path, file_version, rows_loaded, started_at
FROM audit.pipeline_executions
WHERE domain = 'annuity_performance'
  AND status = 'success'
  AND DATE_TRUNC('month', started_at) = '2025-01-01'
ORDER BY started_at DESC;
```

### Documentation Updates

**Update Story 1.7 Technical Notes:**
- Add audit table schema to migration checklist
- Document insert/update logic for pipeline execution tracking
- Reference FR-4.3 (Audit Logging) and NFR-4.4 (Audit Trail Security)
- Link to Epic 4 Story 4.5 for integration example

---

## ✅ Condition #3: Cross-Platform CI Testing Added to Story 1.11

**Story:** Epic 1 Story 1.11 - Enhanced CI/CD with Integration Tests
**Requirement:** Add Linux Docker integration tests for Chinese character encoding validation

### Acceptance Criteria Addition

**Given** I am implementing Story 1.11 enhanced CI/CD
**When** I configure CI pipeline (GitHub Actions / Azure DevOps / GitLab CI)
**Then** I must add cross-platform testing for Chinese character support:

**And** When integration tests run in CI
**Then** They must execute on **Linux Docker container** (even if dev is Windows):
```yaml
# GitHub Actions example
name: Integration Tests (Cross-Platform)

jobs:
  integration-tests-linux:
    runs-on: ubuntu-latest
    container:
      image: python:3.10-slim

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run cross-platform encoding tests
        run: |
          pytest tests/integration/test_chinese_encoding.py -v
        env:
          PYTHONIOENCODING: utf-8
          LANG: en_US.UTF-8
          LC_ALL: en_US.UTF-8
```

**And** When Chinese encoding tests execute
**Then** They must validate:
1. **File path encoding:** Chinese characters in file paths work on Linux
2. **Excel content encoding:** Chinese column names and cell values read correctly
3. **Database column encoding:** Chinese field values insert/query correctly from PostgreSQL

### Test Fixtures Required

**Create test fixture:** `tests/fixtures/chinese_encoding/`
```
tests/fixtures/chinese_encoding/
├── 测试文件.xlsx                    # File with Chinese filename
├── test_chinese_columns.xlsx       # Excel with Chinese column names
└── test_data_sources_chinese.yml   # Config with Chinese paths
```

**Test fixture content example:**
```yaml
# tests/fixtures/chinese_encoding/test_data_sources_chinese.yml
data_sources:
  test_domain:
    base_path: "tests/fixtures/chinese_encoding/数据文件夹"  # Chinese path
    file_pattern: "测试*.xlsx"  # Chinese pattern
    sheet_name: "工作表1"  # Chinese sheet name
    columns:
      - 月度      # Chinese column
      - 计划代码
      - 客户名称
```

### Test Implementation

**Create:** `tests/integration/test_chinese_encoding.py`

```python
import pytest
import pandas as pd
from pathlib import Path

class TestChineseEncoding:
    """Cross-platform Chinese character encoding validation (Condition #3)"""

    def test_chinese_file_path_read(self, tmp_path):
        """Test that files with Chinese characters in path can be read on Linux"""
        # Create test file with Chinese filename
        chinese_path = tmp_path / "测试文件夹" / "数据文件.xlsx"
        chinese_path.parent.mkdir(exist_ok=True)

        # Write test Excel file
        df = pd.DataFrame({"月度": ["2025-01"], "计划代码": ["TEST001"]})
        df.to_excel(chinese_path, index=False, engine='openpyxl')

        # Read back (Epic 3 Story 3.3 pattern)
        df_read = pd.read_excel(chinese_path, engine='openpyxl')

        assert "月度" in df_read.columns
        assert df_read["月度"].iloc[0] == "2025-01"

    def test_chinese_column_names_preserved(self):
        """Test that Chinese column names survive normalization (Epic 3 Story 3.4)"""
        df = pd.DataFrame({
            "月度": ["2025-01"],
            "计划代码": ["TEST001"],
            "客户名称": ["测试公司"]
        })

        # Normalize (Epic 3 Story 3.4 logic)
        normalized_columns = [col.strip() for col in df.columns]
        df.columns = normalized_columns

        assert "月度" in df.columns
        assert "客户名称" in df.columns
        assert df["客户名称"].iloc[0] == "测试公司"

    def test_chinese_database_roundtrip(self, test_db):
        """Test Chinese values insert and query from PostgreSQL correctly"""
        # Insert Chinese data
        test_db.execute("""
            CREATE TEMP TABLE test_chinese (
                月度 VARCHAR(10),
                客户名称 VARCHAR(100)
            )
        """)

        test_db.execute("""
            INSERT INTO test_chinese (月度, 客户名称)
            VALUES ('2025-01', '测试公司')
        """)

        # Query back
        result = test_db.query("SELECT * FROM test_chinese")
        assert result[0]['月度'] == '2025-01'
        assert result[0]['客户名称'] == '测试公司'

    def test_full_width_spaces_normalized(self):
        """Test full-width spaces in column names normalized (Epic 3 Story 3.4)"""
        # Full-width space (U+3000) vs regular space
        column_with_fullwidth = "期末　资产规模"  # 　 is full-width space

        # Normalize (Epic 3.4 logic)
        normalized = column_with_fullwidth.replace('\u3000', ' ').strip()

        assert normalized == "期末 资产规模"
        assert '\u3000' not in normalized
```

### CI Platform-Specific Configuration

**For GitHub Actions:** (Already shown above)

**For Azure DevOps:**
```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

container: python:3.10-slim

steps:
- script: |
    pip install -r requirements.txt
    pytest tests/integration/test_chinese_encoding.py -v
  env:
    PYTHONIOENCODING: utf-8
    LANG: en_US.UTF-8
  displayName: 'Cross-Platform Chinese Encoding Tests'
```

**For GitLab CI:**
```yaml
# .gitlab-ci.yml
integration-tests:
  image: python:3.10-slim
  script:
    - pip install -r requirements.txt
    - pytest tests/integration/test_chinese_encoding.py -v
  variables:
    PYTHONIOENCODING: "utf-8"
    LANG: "en_US.UTF-8"
```

### Documentation Updates (Story 4.6 Runbook)

**Add to Epic 4 Story 4.6 runbook:**

#### UTF-8 Encoding Standards

**File Paths:**
- Always use UTF-8 encoding for file paths containing Chinese characters
- Test paths on both Windows and Linux before deployment
- Use `pathlib.Path()` for cross-platform path handling

**Example:**
```python
from pathlib import Path

# ✅ Correct: Platform-agnostic
file_path = Path("数据文件夹") / "测试文件.xlsx"

# ❌ Avoid: Platform-specific string paths
file_path = "数据文件夹\\测试文件.xlsx"  # Windows-only
```

**Database Configuration:**
- PostgreSQL database encoding: `UTF8`
- Python database driver encoding: `utf-8`
- Verify with: `SHOW SERVER_ENCODING;` (should return `UTF8`)

**Environment Variables:**
```bash
# Set in .env or system environment
export PYTHONIOENCODING=utf-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

**Troubleshooting:**
- If file not found on Linux but works on Windows: Check UTF-8 encoding
- If Chinese characters appear as `?` or `���`: Check database/connection encoding
- If column names corrupted: Verify Excel file saved with UTF-8 BOM

### Story 1.11 Technical Notes Update

**Add to existing technical notes:**

**Cross-Platform Testing:**
- All integration tests MUST run on Linux Docker container in CI
- Required even if development environment is Windows
- Validates Chinese character encoding across platforms (Condition #3)
- Test fixtures in `tests/fixtures/chinese_encoding/` with Chinese filenames
- Environment variables: `PYTHONIOENCODING=utf-8`, `LANG=en_US.UTF-8`
- References: Epic 3 Stories 3.2, 3.3, 3.4 (Chinese character handling)
- Epic 4 Story 4.6 runbook documents UTF-8 encoding standards

---

## Summary: All Conditions Satisfied ✅

| Condition | Status | Document/Reference |
|-----------|--------|-------------------|
| **#1: Epic 6 Stories Defined** | ✅ COMPLETE | `docs/epic-6-testing-validation.md` |
| **#2: Audit Table Schema** | ✅ DOCUMENTED | This addendum (Story 1.7 section) |
| **#3: Cross-Platform CI Testing** | ✅ DOCUMENTED | This addendum (Story 1.11 section) |

**Implementation Notes:**
- Condition #2 implemented during Epic 1 Story 1.7 execution
- Condition #3 implemented during Epic 1 Story 1.11 execution
- Both are now part of the Epic 1 Definition of Done
- Epic 6 can be scheduled in parallel with Epic 4 Stories 4.3-4.4

**Next Step:** Proceed to `sprint-planning` workflow to create sprint status tracking file.

---

_This addendum was created as part of the Implementation Readiness Check (2025-11-09) to satisfy mandatory conditions before Phase 4 implementation._
