# IO Layer Test Failures - Story 7.2 Code Review

Status: pending-fix
Created: 2025-12-22
Context: Story 7.2 IO Layer Modularization Code Review

## Summary

During the code review for Story 7.2, significant test failures were discovered related to the `FileDiscoveryService` refactoring. The core issues stem from API mismatches and mock configuration issues.

## Test Statistics

| Category | Count |
|----------|-------|
| `tests/unit/io/connectors/test_file_discovery_service.py` | 15 failed, 8 passed |
| `tests/io/*` | ~22 failed, ~311 passed |

## Root Causes Identified

### 1. Template Variable Name Mismatch

**Issue**: Tests use `month="202501"` but template expects `YYYYMM="202501"`

**Location**: `tests/unit/io/connectors/test_file_discovery_service.py` lines 163, 317, 357, 388, 411, 433

**Fix Applied**: Replaced `month=` with `YYYYMM=` in affected tests.

### 2. API Method Name Mismatch

**Issue**: `service.py` called `excel_reader.read_file()` but `ExcelReader` only has `read_sheet()`

**Location**: `src/work_data_hub/io/connectors/discovery/service.py` line 158

**Fix Applied**: Changed to `read_sheet()` and extracted `df` from `ExcelReadResult.df`

### 3. Missing `columns` Attribute

**Issue**: Code accessed `domain_config.columns` but `DomainConfigV2` doesn't have this field

**Location**: `src/work_data_hub/io/connectors/discovery/service.py` line 173

**Fix Applied**: Used `getattr(domain_config, 'columns', None)` for safe access

### 4. Import Path Inconsistency

**Issue**: Test used `src.work_data_hub.infrastructure.settings...` while production uses `work_data_hub.infrastructure.settings...`, causing `isinstance()` checks to fail

**Location**: `tests/unit/io/connectors/test_file_discovery_service.py` line 15

**Fix Applied**: Changed to `work_data_hub.infrastructure.settings...`

### 5. `stage_durations` Key Mismatch

**Issue**: Tests expect `stage_durations["version_detection"]` but service uses `stage_durations["discovery"]` and `stage_durations["read"]`

**Status**: NOT FIXED - Requires test or service update

### 6. Error Stage Identification

**Issue**: `_identify_failed_stage()` returns `"unknown"` or `"read_or_normalization"` but tests expect specific stages like `"excel_reading"`

**Status**: NOT FIXED - Requires implementation of proper stage detection

## Files Modified During Code Review

| File | Changes |
|------|---------|
| `src/work_data_hub/io/connectors/discovery/service.py` | Fixed `read_file` → `read_sheet`, added safe `columns` access, updated `_load_domain_config` for test injection |
| `tests/unit/io/connectors/test_file_discovery_service.py` | Fixed import path, changed `month=` to `YYYYMM=` |

## Remaining Work for Dev Team

1. **Fix `stage_durations` keys**: Align test expectations with actual service implementation
2. **Implement proper `_identify_failed_stage()`**: Add stack trace inspection or exception type checking to accurately identify failure stages
3. **Review `discover_and_load` return structure**: Ensure `DataDiscoveryResult` contains all expected fields
4. **Update test mocks**: Ensure `DummyReader`, `DummyScanner`, `DummyMatcher` match current interfaces

## Raw Test Output

See `io-layer-test-failures-raw.txt` for complete pytest output.

## Related Documents

- Story: [7-2-io-layer-modularization.md](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/7-2-io-layer-modularization.md)
- Code Smell: [duplicate-file-discovery-mechanisms.md](file:///e:/Projects/WorkDataHub/docs/specific/code-smell/duplicate-file-discovery-mechanisms.md)
