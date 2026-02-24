# CLI Architecture ETL Backfill Issues Diagnosis

**Date**: 2025-12-16
**Story**: 6.2-P6 (CLI Architecture Unification)
**Status**: Blocked - Multiple Issues Found

---

## Executive Summary

在验证 `manual-validation-guide-cli-architecture.md` 指南时，发现 ETL 命令的 `generic_backfill_refs_op` 步骤存在多个问题，导致无法成功写入数据库。本文档记录了所有发现的问题及其初步修复尝试。

---

## 1. Issues Discovered

### I001: Windows PowerShell Command Format Incompatibility
**Severity**: Medium | **Status**: Documented

**Description**: 
指南中使用的 `PYTHONPATH=src uv run ...` 语法在 Windows PowerShell 中无法识别。

**Solution**: 
```powershell
# Windows PowerShell format:
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python -m work_data_hub.cli ...
```

---

### I002: Missing Schema Qualification in SQL Queries
**Severity**: High | **Status**: Partially Fixed

**Description**: 
`GenericBackfillService.backfill_table()` 方法中的 SQL 查询未使用 schema 前缀。

**Location**: `src/work_data_hub/domain/reference_backfill/generic_service.py`

**Problem Code**:
```python
existing_query = text(f"""
    SELECT {config.target_key} FROM {config.target_table}  # Missing schema
    ...
""")
```

**Fix Applied**:
```python
def _qualified_table_name(config: ForeignKeyConfig) -> str:
    """Get fully qualified table name with schema."""
    return f'{config.target_schema}."{config.target_table}"'

# Then use: SELECT ... FROM {qualified_table}
```

**Verification Status**: ⚠️ Partially applied - needs comprehensive review

---

### I003: Missing Column Quoting in SQL Statements
**Severity**: High | **Status**: Partially Fixed

**Description**: 
PostgreSQL 需要对中文列名使用双引号，但 INSERT 语句中列名未加引号。

**Before**:
```sql
INSERT INTO mapping."年金计划" (年金计划号, 计划名称, ...)
```

**After**:
```sql
INSERT INTO mapping."年金计划" ("年金计划号", "计划名称", ...)
```

**Fix Applied**: 修改 `generic_service.py` 中列名使用 `f'"{c}"'` 格式

---

### I004: Column Name Mismatch in backfill_columns Configuration
**Severity**: High | **Status**: Partially Fixed

**Description**: 
`config/data_sources.yml` 中的 `backfill_columns` 目标列名与实际表结构不匹配。

**Actual Table Columns** (`mapping.年金计划`):
- id, 年金计划号, 计划简称, 计划全称, 主拓代码, 计划类型, 客户名称
- company_id, 管理资格, 计划状态, 主拓机构, 组合数, 北京统括, 备注

**Configuration Mismatches**:
| Config Target | Actual Column | Status |
|---------------|---------------|--------|
| `计划名称` | `计划全称` | ✅ Fixed |
| `资格` | `管理资格` | ✅ Fixed |

---

### I005: Tracking Fields Not Supported by mapping Schema Tables
**Severity**: High | **Status**: Fixed

**Description**: 
`GenericBackfillService` 默认添加 tracking fields (`_source`, `_needs_review`, `_derived_from_domain`, `_derived_at`)，但 `mapping` schema 中的表没有这些列。

**Location**: `src/work_data_hub/cli/etl.py` line 166

**Fix Applied**:
```python
"add_tracking_fields": False,  # mapping schema tables don't have tracking fields
```

---

### I006: Remaining Unknown Error
**Severity**: Critical | **Status**: ✅ RESOLVED

**Root Cause Analysis (2025-12-16):**

The original hypothesis that I006 was caused by SQL generation issues was **incorrect**.

**Actual Root Cause:**
1. `LoadConfig` Pydantic validation failure in `orchestration/ops.py` (line 720-721)
2. Error message: `"delete_insert mode requires primary key columns"`
3. Cause: `data_sources.yml` missing `pk` field in `output` section for both domains
4. Additional bug: CLI `build_run_config` was reading `pk` from wrong location

**Fixes Applied:**
1. Added `pk` configuration to `annuity_performance` and `annuity_income` in `data_sources.yml`
2. Fixed `cli/etl.py` `build_run_config()` to read `pk` from `output` section

**Verification:**
- Isolated `GenericBackfillService.backfill_table()` test: SUCCESS (1 record)
- Full `GenericBackfillService.run()` test: SUCCESS (8 records across 4 tables)
- Core SQL generation logic is working correctly with proper quoting and schema qualification

**Post-Fix Status:**
ETL progresses past backfill but encounters a new issue:
- Database column `流失_含待遇支付` does not exist in `规模明细` table
- This is a separate schema migration issue, not related to I006

---

## 2. Files Modified During Troubleshooting

| File | Changes Made | Needs Review |
|------|-------------|--------------|
| `src/work_data_hub/domain/reference_backfill/generic_service.py` | Added `_qualified_table_name()`, schema/column quoting | ⚠️ Yes |
| `config/data_sources.yml` | Fixed target column names | ⚠️ Yes |
| `src/work_data_hub/cli/etl.py` | Set `add_tracking_fields: False` | ⚠️ Yes |

---

## 3. Database Schema Analysis

### 3.1 mapping.年金计划 Table Structure
```
Columns in mapping.年金计划:
  - id: integer
  - 年金计划号: character varying
  - 计划简称: character varying
  - 计划全称: character varying
  - 主拓代码: character varying
  - 计划类型: character varying
  - 客户名称: character varying
  - company_id: character varying
  - 管理资格: character varying
  - 计划状态: character varying
  - 主拓机构: character varying
  - 组合数: integer
  - 北京统括: smallint
  - 备注: text
```

### 3.2 Schema Ownership
- `mapping` schema: Legacy reference tables (年金计划, 组合计划, 产品线, 组织架构)
- `business` schema: Fact tables with tracking fields (Story 6.2.2 enhanced)
- `enterprise` schema: EQC enrichment tables

---

## 4. Resolution Plan

**Story Reference:** [6.2-P10 (ETL Backfill Bug Fixes & SQL Module Architecture)](../sprint-artifacts/stories/6.2-p10-etl-backfill-sql-module.md)
**Sprint Change Proposal:** [sprint-change-proposal-2025-12-16-etl-backfill-sql-module.md](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-16-etl-backfill-sql-module.md)
**Status:** ✅ Completed (Phase 1-3), Phase 4 Optional

### Phase 1: Diagnose I006 Root Cause (Critical) ✅

- [x] Task 1.1: Enable verbose logging for ETL backfill operation
- [x] Task 1.2: Capture complete error stack trace
- [x] Task 1.3: Identify failure point (psycopg2, SQLAlchemy, or application code)
- [x] Task 1.4: Document root cause in this file

### Phase 2: Fix Known Issues I001-I005 (High) ✅

- [x] Task 2.1: Review and validate all `_qualified_table_name()` usages
- [x] Task 2.2: Ensure consistent column quoting across all SQL statements
- [x] Task 2.3: Validate `data_sources.yml` backfill_columns against actual schemas
- [x] Task 2.4: Add unit tests for SQL generation edge cases

### Phase 3: SQL Module Architecture (Medium) ✅

- [x] Task 3.1: Create `infrastructure/sql/core/` with base classes
- [x] Task 3.2: Create `infrastructure/sql/dialects/` for PostgreSQL support
- [x] Task 3.3: Create `infrastructure/sql/operations/` for INSERT/SELECT builders
- [x] Task 3.4: Refactor `generic_service.py` to use new SQL module
- [x] Task 3.5: Add comprehensive unit tests for SQL module

### Phase 4: Documentation & Validation (Low) ⏳

- [ ] Update CLI guide with Windows PowerShell compatible commands
- [ ] Update architecture documentation with SQL module
- [ ] Create FK config validation script

---

## 5. Temporary Workaround Files

以下临时脚本在排查过程中创建，修复完成后可删除：
- `scripts/fix_schema_refs.py` - Python fix scripts
- `scripts/query_table.py` - Table structure query script

---

## Appendix: Related Documentation

- [manual-validation-guide-cli-architecture.md](file:///e:/Projects/WorkDataHub/scripts/validation/CLI/manual-validation-guide-cli-architecture.md)
- [cli-validation-issues.md](file:///e:/Projects/WorkDataHub/scripts/validation/CLI/cli-validation-issues.md)
