# Duplicate File Discovery Mechanisms

**Status:** Open
**Created:** 2025-12-21
**Priority:** High (violates Zero Legacy Policy)

## Description

The project contains two duplicate file discovery mechanisms in the same module, violating the Zero Legacy Policy principle.

## Code Locations

### 1. DataSourceConnector.discover() (Legacy)
- **File:** `src/work_data_hub/io/connectors/file_connector.py:148`
- **Lines:** 148-221
- **Status:** Marked as deprecated but still present

### 2. FileDiscoveryService.discover_and_load() (Current)
- **File:** `src/work_data_hub/io/connectors/file_connector.py:781`
- **Lines:** 781-906

## Zero Legacy Policy Violations

1. **❌ Keeping deprecated code:** The DataSourceConnector class is marked as deprecated (lines 55-66) but remains in the codebase
2. **❌ Backward compatibility wrappers:** Deprecation warnings and alias mappings create unnecessary complexity
3. **❌ Not refactoring atomically:** New implementation was added without removing the old one

## Impact

1. **Code bloat:** ~470 lines of deprecated code in a single file
2. **Maintenance burden:** Two implementations to understand and maintain
3. **Confusion:** Developers must decide which API to use
4. **Test duplication:** Tests exist for both mechanisms

## Detailed Analysis

### DataSourceConnector (Legacy)
```python
# Characteristics:
- Uses regex pattern matching
- Supports old schema (pattern + select)
- No template variable support
- Manual file traversal with os.walk()
- Hardcoded year/month extraction from regex groups
```

### FileDiscoveryService (Current)
```python
# Characteristics:
- Uses FilePatternMatcher, VersionScanner, ExcelReader
- Supports new Epic 3 schema (base_path + file_patterns)
- Template variable support ({YYYYMM}, {YYYY}, {MM})
- Structured error handling with DiscoveryError
- Performance metrics and stage durations
```

## Recommendations

### Immediate Action Required
1. **Remove DataSourceConnector class entirely** (lines 51-621)
2. **Remove all deprecation warnings and checks** (lines 108-136)
3. **Remove legacy schema support** from config validation
4. **Update all import statements** to use FileDiscoveryService

### Migration Steps
1. Identify all DataSourceConnector usage in codebase
2. Replace with FileDiscoveryService.discover_file() or discover_and_load()
3. Update configurations from legacy schema to Epic 3 schema
4. Remove tests for DataSourceConnector
5. Update documentation

### Example Migration

**Before:**
```python
connector = DataSourceConnector()
files = connector.discover(domain="annuity_performance")
```

**After:**
```python
service = FileDiscoveryService()
result = service.discover_and_load(domain="annuity_performance", month="202501")
```

## Files Affected

- `src/work_data_hub/io/connectors/file_connector.py` - Remove legacy code
- `tests/` - Remove tests for DataSourceConnector
- Documentation files mentioning DataSourceConnector
- Any code importing or using DataSourceConnector

## Risk Assessment

- **Breaking Change:** Yes - API will change
- **Test Coverage:** Exists for both mechanisms
- **Migration Effort:** Medium (requires config updates)
- **Benefits:** Significant - ~470 lines removed, cleaner API

## Related Issues

- This is related to Epic 3 migration from legacy to Epic 3 schema
- Intersects with Stories 3.1-3.5 (file discovery implementation)

## Decision

**Action:** Remove DataSourceConnector completely as per Zero Legacy Policy.
**Reason:** Project is in pre-production, no need for backward compatibility.
**Timeline:** Should be done in next refactoring sprint.