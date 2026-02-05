# Sprint Change Proposal: ETL Specified File Support

**Date**: 2026-01-08  
**Author**: Correct Course Workflow  
**Status**: ✅ APPROVED  
**Scope Classification**: Minor  
**Approved by**: Link (2026-01-08 22:06)

---

## 1. Issue Summary

### Problem Statement
During ETL database write verification, it was discovered that the current ETL system only supports fixed-path automatic data scanning via `data_sources.yml` configuration. There is no capability to process a specified file directly with a specified domain.

### Context
- **Discovered during**: Database data write verification for `annuity_performance` domain
- **Example scenario**: Cannot process `tests\fixtures\real_data\Legacy Database Data\annuity_performance_20260108_213817.csv` with the `annuity_performance` domain pipeline

### Evidence
- Current `FileDiscoveryService.discover_and_load()` only accepts `domain` and `month` parameters
- File path is determined entirely by `base_path` template + version detection
- No CLI parameter exists for direct file input

---

## 2. Impact Analysis

### Epic Impact
| Epic | Impact Level | Details |
|------|--------------|---------|
| Epic 3: Intelligent File Discovery | **Modified** | Extend `FileDiscoveryService` with new method |
| Epic 4-9 | No Impact | No changes required |

### Story Impact
- **Current Stories**: No modifications to existing stories required
- **New Functionality**: Pure additive change, extends Epic 3 capabilities

### Artifact Conflicts
| Artifact | Status | Action |
|----------|--------|--------|
| PRD | ✅ No conflict | Aligns with "Intelligent Automation" goal |
| Architecture | ✅ No conflict | Follows existing patterns |
| Tests | ⚠️ Additions needed | New unit tests for `load_from_file()` |

### Technical Impact
- **Code changes**: ~100-150 lines across 2-3 files
- **Breaking changes**: None
- **Dependencies**: None new

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment (Option 1)

**Rationale**:
- Pure additive change with no modifications to existing functionality
- Low effort (~2-4 hours implementation)
- Low risk (no breaking changes)
- Immediate value for testing/validation scenarios

### Effort Estimate
| Task | Estimate |
|------|----------|
| FileDiscoveryService.load_from_file() | 1-2 hours |
| CLI --file parameter | 1 hour |
| Unit tests | 1 hour |
| **Total** | **3-4 hours** |

### Risk Assessment
- **Technical Risk**: Low - follows established patterns
- **Timeline Impact**: Minimal - can be completed in single session
- **Testing Risk**: Low - isolated functionality with clear test cases

---

## 4. Detailed Change Proposals

### Proposal 1: FileDiscoveryService Extension

**File**: `src/work_data_hub/io/connectors/discovery/service.py`

**Change**: Add new method `load_from_file()`

```python
def load_from_file(
    self,
    file_path: str | Path,
    domain: str,
    sheet_name: Optional[str | int] = None,
) -> DataDiscoveryResult:
    """
    Load data directly from a specified file path, bypassing automatic discovery.
    
    Args:
        file_path: Path to data file (Excel or CSV)
        domain: Domain name for configuration lookup
        sheet_name: Override sheet name (optional, ignored for CSV)
    
    Returns:
        DataDiscoveryResult with loaded DataFrame and metadata
    """
    path = Path(file_path)
    
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
    elif path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        sheet = sheet_name or self._get_domain_sheet_name(domain)
        df = self.excel_reader.read(path, sheet)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    
    df = normalize_columns(df)
    return DataDiscoveryResult(df=df, file_path=path, ...)
```

---

### Proposal 2: CLI Extension

**File**: `src/work_data_hub/cli/etl/main.py`

**Change**: Add `--file` argument

```python
parser.add_argument(
    "--file",
    type=str,
    default=None,
    help=(
        "Process a specific file directly (bypasses automatic discovery). "
        "Supports Excel (.xlsx, .xls) and CSV (.csv) formats. "
        "Must be used with --domains for a single domain."
    ),
)
```

**Validation**:
- `--file` requires exactly one domain via `--domains`
- `--file` is mutually exclusive with `--period`
- File existence is validated at argument parsing

---

### Proposal 3: Test Additions

**File**: `tests/unit/io/connectors/test_file_discovery_service.py`

**Change**: Add `TestLoadFromFile` test class

```python
class TestLoadFromFile:
    def test_load_csv_file_success(self, ...): ...
    def test_load_excel_file_with_sheet(self, ...): ...
    def test_file_not_found_raises_error(self, ...): ...
    def test_unsupported_extension_raises_error(self, ...): ...
```

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

This change can be implemented directly by the development team without backlog reorganization.

### Handoff Recipients
| Role | Responsibility |
|------|----------------|
| Developer | Implement all 3 proposals |
| QA | Verify test coverage and functionality |

### Success Criteria
1. ✅ `--file` parameter accepts CSV and Excel files
2. ✅ Single domain processing works with specified file
3. ✅ All unit tests pass
4. ✅ Example command works:
   ```bash
   python -m work_data_hub.cli etl \
       --domains annuity_performance \
       --file "tests/fixtures/real_data/annuity_performance.csv" \
       --execute
   ```

---

## Verification Plan

### Automated Tests
```bash
# Run new unit tests
pytest tests/unit/io/connectors/test_file_discovery_service.py::TestLoadFromFile -v
```

### Manual Verification
```bash
# Test CSV file processing
python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --file "tests/fixtures/real_data/Legacy Database Data/annuity_performance_20260108_213817.csv" \
    --plan-only

# Verify output shows file loaded correctly
```

---

## Approval

- [x] **User Approval**: Approved by Link (2026-01-08)
- [x] **Implementation Start**: Ready for implementation

---

*Generated by Correct Course Workflow on 2026-01-08*
