# Sprint Change Proposal: ETL Execution Robustness Enhancement

**Date**: 2025-12-20  
**Triggered by**: ETL validation for 202510 period  
**Scope**: Minor (Development team implementation)  
**Epic**: 6.2 - Generic Reference Data Management

---

## Issue Summary

During validation of the 6.2-P15 (Complex Mapping Backfill Enhancement) implementation, executing the ETL command `etl --domains annuity_performance --period 202510` revealed **4 interconnected issues** that block successful data processing.

| # | Issue | Severity | Code Location |
|---|-------|----------|---------------|
| I001 | File discovery ambiguity | High | `file_pattern_matcher.py:92-103` |
| I002 | Database connection failure | High | `ops.py:456` |
| I003 | Backfill cascade failure | Medium | Dependent on I002 |
| I004 | EQC Token validation defect | Medium | `etl.py:40-87` |

---

## Impact Analysis

### Epic Impact
- **Epic 6.2**: Current sprint - blocks completion validation
- **Epic 7**: Future sprint - testing infrastructure depends on reliable ETL

### PRD Alignment
All issues align with PRD goals:
- FR-1.1: Intelligent file detection (I001)
- FR-2.1: Reliable pipeline execution (I002, I003)
- NFR-5: Usability and developer experience (I004)

### Artifact Conflicts
- **None**: Issues are implementation bugs, not design conflicts

---

## Detailed Issue Analysis

### I001: File Discovery Ambiguity Error

**Problem**: When multiple files match include patterns, `FilePatternMatcher.match_files()` throws an error instead of using selection strategy.

**Code Location**: [file_pattern_matcher.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/io/connectors/file_pattern_matcher.py#L92-L103)

```python
# Current behavior (raises on any ambiguity)
if len(matched) > 1:
    raise DiscoveryError(
        domain="unknown",
        failed_stage="file_matching",
        message=f"Ambiguous match: Found {len(matched)} files {matched}..."
    )
```

**Root Cause**: 
- `--max-files` parameter is processed AFTER file matching
- No selection strategy for multiple matches (e.g., newest file, date in filename)

**Proposed Solution**:
1. Add `strategy` parameter to `match_files()`: `"newest"`, `"oldest"`, `"first"`, `"error"`
2. Default strategy: `"error"` (backward compatible)
3. Integrate with CLI `--max-files` parameter

---

### I002: Database Connection Failure

**Problem**: ETL fails with "user 'user' Password authentication failed" despite correct `.wdh_env` configuration.

**Evidence**:
```
# .wdh_env (correct)
WDH_DATABASE_USER=postgres

# Error message (incorrect default used)
用户 "user" Password 认证失败
```

**Code Location**: [ops.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/orchestration/ops.py#L456)

**Root Cause Analysis Required**:
- Settings module may not be loading `.wdh_env` correctly
- Possible `.env` file taking precedence
- `get_database_connection_string()` may have fallback logic using default values

**Proposed Solution**:
1. Add diagnostic logging before database connection
2. Validate DSN components before `psycopg2.connect()`
3. Add pre-flight database connectivity check in CLI

---

### I003: Backfill Validation Failure (Cascade)

**Problem**: `mapping."年金计划"` table remains empty because I002 blocks pipeline execution.

**Dependency**: Resolves automatically when I002 is fixed.

**No code changes required** - this is a cascade failure.

---

### I004: EQC Token Validation Defect

**Problem**: User reports "每次CLI启动都强制重新获取Token" (token refresh on every CLI run).

**Code Analysis**: [etl.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl.py#L40-L87)

The `_validate_and_refresh_token()` function **correctly validates** existing token before refresh:

```python
# Line 68-72: Token validation DOES happen first
print("🔐 Validating EQC token...", end=" ", flush=True)
if validate_eqc_token(token, base_url):
    print("✅ Token valid")
    return True
```

**Possible Root Causes**:
1. `validate_eqc_token()` returning `False` incorrectly
2. Token expiring between validation and use
3. Network issues causing validation failure

**Proposed Solution**:
1. Add diagnostic logging in `validate_eqc_token()`
2. Investigate `EQCClient` token validation logic
3. Consider caching validation result for session duration

---

## Recommended Path Forward

**Option Selected**: Direct Adjustment (Low Risk, Medium Effort)

### Rationale
- Issues are localized bugs, not architectural problems
- No rollback needed
- MVP scope unchanged
- Straightforward fixes with clear test paths

---

## Proposed Changes

### Story 6.2-P16: ETL Execution Robustness

#### Task T1: File Discovery Selection Strategy

[MODIFY] [file_pattern_matcher.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/io/connectors/file_pattern_matcher.py)

- Add `selection_strategy` parameter to `match_files()`
- Implement strategies: `newest`, `oldest`, `first`, `error`
- Add file modification time sorting

---

#### Task T2: Database Connection Diagnostics

[MODIFY] [ops.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/orchestration/ops.py)

- Add DSN component logging before connect
- Add pre-connect validation with friendly error messages

[MODIFY] [etl.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl.py)

- Add `--check-db` pre-flight option
- Add database connectivity check before pipeline execution

---

#### Task T3: Token Validation Diagnostics

[MODIFY] [eqc_provider.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/infrastructure/enrichment/eqc_provider.py)

- Add detailed logging in `validate_eqc_token()`
- Log validation result and response details

---

## Verification Plan

### Automated Tests

1. **File Discovery Tests**:
   ```bash
   pytest tests/io/connectors/test_file_pattern_matcher.py -v
   ```
   - Verify selection strategy parameter works
   - Test each strategy with multiple matching files

2. **Database Connection Tests**:
   ```bash
   pytest tests/orchestration/test_ops.py -v -k "connection"
   ```
   - Verify DSN construction from settings
   - Test error handling for connection failures

### Manual Verification

1. **Reproduce I001**:
   - Place two matching files in test data folder
   - Run ETL with `--max-files 1`
   - Verify newest file is selected (not error)

2. **Verify I002 Fix**:
   - Run `etl --domains annuity_performance --period 202510 --execute`
   - Confirm database connection succeeds

3. **Verify I004 Logging**:
   - Run ETL twice with valid token
   - Confirm token validation passes on both runs without QR prompt

---

## Effort Estimate

| Task | Effort | Risk |
|------|--------|------|
| T1: Selection Strategy | 2-3 hours | Low |
| T2: DB Diagnostics | 1-2 hours | Low |
| T3: Token Logging | 1 hour | Low |
| Testing | 2 hours | Low |
| **Total** | **6-8 hours** | **Low** |

---

## Agent Handoff

| Role | Responsibility |
|------|----------------|
| Development Team | Implement T1-T3, write tests |
| SM (on approval) | Create story file, update sprint status |
