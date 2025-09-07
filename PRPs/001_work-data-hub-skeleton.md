# WorkDataHub Skeleton + Connector + Domain Service Implementation

name: "WorkDataHub Core Foundation Implementation"
description: |
  Build the project skeleton and deliver two core components: a config-driven file connector 
  and one domain service (trustee_performance) with Pydantic v2 data contracts. Create a robust, 
  testable foundation for the modernized data processing platform.

---

## Goal

Create the `src/work_data_hub` modular architecture with a robust file discovery connector and one 
complete domain service (trustee_performance). Implement clean layering, configuration-driven 
file discovery, and pure transformation functions with comprehensive Pydantic v2 data contracts.

## Why

- **Foundation for Modernization**: Establishes the architectural skeleton that will replace the monolithic legacy ETL system
- **Domain-Driven Design**: Demonstrates the new pattern of isolated, testable domain services vs. monolithic data_cleaner.py
- **Configuration-Driven Flexibility**: File discovery patterns become configurable YAML instead of hardcoded logic
- **Data Contract Enforcement**: Pydantic v2 models enforce data quality at boundaries, preventing invalid data propagation
- **Testing Foundation**: Pure functions and clear contracts enable comprehensive unit testing (vs. current <10% coverage)

## What

**User-visible behavior:**
- File connector can discover Excel files matching regex patterns from YAML configuration  
- Handles complex filename patterns with Chinese characters and version directories
- Domain service transforms raw Excel rows into validated, typed data structures
- All components are independently testable with clear input/output contracts

**Technical requirements:**
- Clean layered architecture: config/, io/, domain/, utils/
- Unicode-aware regex file discovery with "latest version" selection
- Pure functions for data transformation (no side effects)
- Comprehensive Pydantic v2 data validation
- 90%+ test coverage for new components

### Success Criteria
- [ ] File connector discovers .xlsx files and ignores .eml/temp files using configurable regex patterns
- [ ] Latest version selection works for both (year, month) patterns and mtime fallback
- [ ] Domain service processes Excel rows to typed Pydantic models with validation
- [ ] All functions are pure (no side effects) and fully unit tested
- [ ] Configuration is externalized to YAML files
- [ ] Validation gates pass: ruff check, pytest, mypy (if added)

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window

- url: https://docs.pydantic.dev/latest/concepts/models/
  why: BaseModel patterns, field definitions, ConfigDict usage
  critical: Pydantic v2 uses different syntax than v1 (@field_validator vs @validator)

- url: https://docs.pydantic.dev/latest/concepts/validators/
  why: @field_validator and @model_validator patterns for data validation  
  critical: mode='after' vs mode='before', validator method signatures

- url: https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html
  why: Excel reading parameters, sheet selection, error handling
  critical: openpyxl engine is used automatically for .xlsx files

- url: https://docs.python.org/3/library/re.html
  why: Regex compilation, Unicode support, named groups (?P<name>pattern)
  critical: Need re.UNICODE flag for Chinese characters in filenames

- url: https://docs.python.org/3/library/pathlib.html  
  why: Modern path operations, glob patterns, file metadata
  critical: pathlib.Path.glob() vs os.walk() performance considerations

- file: CLAUDE.md
  why: Project conventions, testing patterns, error handling standards
  critical: 500 line file limit, 50 line function limit, KISS principle

- file: docs/project/01_architecture_analysis_report.md
  why: Context on why we're replacing monolithic data_cleaner.py
  critical: Domain-driven architecture vision, separation of concerns

- file: docs/project/03_specified_data_source_problems_analysis.md  
  why: Real-world file discovery challenges that connector must solve
  critical: Version directories, mixed file types, filename variations
```

### Current Codebase Structure
```bash
# Current state
.
├── CLAUDE.md (project conventions)
├── INITIAL.md (detailed requirements)
├── pyproject.toml (deps: dagster, pandas, pydantic, psycopg2-binary)
├── src/work_data_hub/ (empty directory)
├── tests/ (empty directory) 
├── docs/project/ (analysis reports)
└── legacy/annuity_hub/ (old monolithic system)
```

### Desired Codebase Structure
```bash
# Target structure to create
src/work_data_hub/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py              # Environment-based settings loader
│   └── data_sources.yml         # Domain regex patterns and selection strategies
├── io/
│   ├── __init__.py
│   ├── connectors/
│   │   ├── __init__.py
│   │   └── file_connector.py    # DataSourceConnector class
│   └── readers/
│       ├── __init__.py
│       └── excel_reader.py      # Pandas Excel reading wrapper
├── domain/
│   ├── __init__.py
│   └── trustee_performance/
│       ├── __init__.py
│       ├── models.py           # Pydantic v2 input/output models
│       └── service.py          # Pure transformation service
└── utils/
    ├── __init__.py
    └── types.py                # DiscoveredFile type and shared utilities

tests/
├── __init__.py
├── io/
│   ├── __init__.py
│   └── test_file_connector.py
├── domain/
│   ├── __init__.py
│   └── trustee_performance/
│       ├── __init__.py
│       └── test_service.py
└── fixtures/
    ├── __init__.py
    └── sample_data/            # Test Excel files and mock data
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: Pydantic v2 uses different decorator syntax than v1
# OLD (v1): @validator('field_name')
# NEW (v2): @field_validator('field_name')

# CRITICAL: pandas needs openpyxl for .xlsx files
# If missing: ImportError: Missing optional dependency 'openpyxl'
# Solution: Add to pyproject.toml dependencies

# CRITICAL: Chinese characters in filenames require Unicode-aware regex
import re
pattern = re.compile(r".*受托业绩.*\.xlsx$", re.UNICODE)

# CRITICAL: ConfigDict replaces inner Config class in Pydantic v2
# OLD (v1): class Config: ...
# NEW (v2): model_config = ConfigDict(...)

# CRITICAL: Latest version logic must handle missing year/month
# Fallback to file modification time when regex groups don't match

# CRITICAL: Keep domain services pure functions
# NO side effects: no file I/O, no database calls, no logging
# Input -> Process -> Output only

# CRITICAL: Excel reading can fail on missing sheets or corrupted files
# Always wrap in try/catch and provide clear error messages
```

## Implementation Blueprint

### Data Models and Structure

```python
# Core data types to establish type safety and validation contracts

from typing import Optional, Dict, Any, List
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from pathlib import Path

# utils/types.py - Core discovery types
@dataclass
class DiscoveredFile:
    """Represents a discovered data file with extracted metadata"""
    domain: str
    path: str  
    year: Optional[int]
    month: Optional[int]
    metadata: Dict[str, Any]

# domain/trustee_performance/models.py - Pydantic v2 models
class TrusteePerformanceIn(BaseModel):
    """Raw input data from Excel with flexible schema"""
    model_config = ConfigDict(extra='allow', str_strip_whitespace=True)
    
    # Add specific fields after inspecting actual Excel files
    report_period: Optional[str] = None
    year: Optional[int] = None  
    month: Optional[int] = None
    
class TrusteePerformanceOut(BaseModel):
    """Validated output model for warehouse loading"""
    model_config = ConfigDict(validate_default=True, use_enum_values=True)
    
    report_date: date
    # TODO: Add normalized fields after understanding business requirements
    
    @model_validator(mode='after') 
    def validate_report_date(self) -> 'TrusteePerformanceOut':
        if not self.report_date:
            raise ValueError("report_date is required")
        return self
```

### Task List (Implementation Order)

```yaml
Task 1: Project Structure Setup
CREATE directory structure:
  - All directories from target structure above
  - All __init__.py files for proper Python packages
  - Ensure proper module imports work

Task 2: Core Types and Configuration  
CREATE utils/types.py:
  - DiscoveredFile dataclass with all required fields
  - Helper functions for file metadata extraction
  
CREATE config/settings.py:
  - Pydantic BaseSettings for environment variable loading
  - DATA_BASE_DIR and DATA_SOURCES_YML configuration
  - Sensible defaults for development

CREATE config/data_sources.yml:
  - Example configuration for trustee_performance domain
  - Pattern with Unicode regex and named groups
  - latest_by_year_month selection strategy

Task 3: Excel Reading Infrastructure
CREATE io/readers/excel_reader.py:
  - read_rows(path, sheet=0) -> List[Dict] function
  - Pandas read_excel wrapper with error handling
  - Robust handling of missing sheets, empty files
  - PRESERVE: No real file dependency for unit tests

Task 4: File Discovery Connector  
CREATE io/connectors/file_connector.py:
  - DataSourceConnector class with discover() method
  - YAML config loading and regex compilation
  - Recursive directory scanning with os.walk()
  - Latest version selection algorithm implementation
  - CRITICAL: Unicode-aware regex for Chinese filenames

Task 5: Domain Models
CREATE domain/trustee_performance/models.py:
  - TrusteePerformanceIn/Out Pydantic v2 models
  - Field validators for data quality rules
  - Model validators for cross-field validation
  - Proper ConfigDict configuration

Task 6: Domain Service
CREATE domain/trustee_performance/service.py:
  - Pure process(rows: List[Dict]) -> List[TrusteePerformanceOut] function
  - Input validation and transformation logic
  - Error handling with ValueError for invalid data
  - PRESERVE: No side effects, fully testable

Task 7: Comprehensive Testing
CREATE test files with pytest patterns:
  - File connector tests with mock filesystem
  - Domain service tests with parameterized inputs
  - Excel reader tests without real file dependencies
  - Integration test for full pipeline

Task 8: Dependencies and Validation
UPDATE pyproject.toml:
  - Add openpyxl for Excel support
  - Add PyYAML for configuration loading  
  - Add mypy for type checking (optional-dependencies.dev)
RUN validation gates and fix all issues
```

### Task 4 Pseudocode (File Connector - Most Complex)

```python
# io/connectors/file_connector.py - Core discovery logic

class DataSourceConnector:
    def __init__(self, config_path: str):
        # PATTERN: Load YAML config in __init__, compile regex patterns
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # CRITICAL: Pre-compile regex with Unicode support
        self.compiled_patterns = {}
        for domain, config in self.config['domains'].items():
            pattern = config['pattern']
            self.compiled_patterns[domain] = re.compile(pattern, re.UNICODE)
    
    def discover(self, domain: Optional[str] = None) -> List[DiscoveredFile]:
        # PATTERN: Filter by domain if specified, otherwise all domains
        domains_to_scan = [domain] if domain else self.config['domains'].keys()
        
        discovered = []
        for domain_name in domains_to_scan:
            domain_config = self.config['domains'][domain_name]
            pattern = self.compiled_patterns[domain_name]
            
            # CRITICAL: Recursive scanning with os.walk for performance
            for root, dirs, files in os.walk(settings.DATA_BASE_DIR):
                for file in files:
                    # GOTCHA: Skip non-xlsx files early
                    if not file.lower().endswith('.xlsx'):
                        continue
                        
                    # CRITICAL: Apply Unicode-aware regex match
                    match = pattern.search(file)
                    if match:
                        file_path = os.path.join(root, file)
                        
                        # Extract year/month from named groups if present
                        year = int(match.group('year')) if 'year' in match.groupdict() else None
                        month = int(match.group('month')) if 'month' in match.groupdict() else None
                        
                        discovered.append(DiscoveredFile(
                            domain=domain_name,
                            path=file_path,
                            year=year,
                            month=month, 
                            metadata={'match_groups': match.groupdict()}
                        ))
        
        # CRITICAL: Apply selection strategy (latest_by_year_month)
        return self._apply_selection_strategy(discovered)
    
    def _apply_selection_strategy(self, files: List[DiscoveredFile]) -> List[DiscoveredFile]:
        # PATTERN: Group by domain, then apply strategy per domain
        by_domain = {}
        for file in files:
            if file.domain not in by_domain:
                by_domain[file.domain] = []
            by_domain[file.domain].append(file)
        
        selected = []
        for domain, domain_files in by_domain.items():
            strategy = self.config['domains'][domain]['select']
            
            if strategy == 'latest_by_year_month':
                # CRITICAL: Handle both year/month patterns and mtime fallback
                with_dates = [f for f in domain_files if f.year and f.month]
                without_dates = [f for f in domain_files if not (f.year and f.month)]
                
                if with_dates:
                    # Sort by (year, month) descending and take first
                    latest = max(with_dates, key=lambda f: (f.year, f.month))
                    selected.append(latest)
                elif without_dates:
                    # Fallback to newest mtime
                    latest = max(without_dates, key=lambda f: Path(f.path).stat().st_mtime)
                    selected.append(latest)
        
        return selected
```

### Integration Points
```yaml
DEPENDENCIES:
  - add to pyproject.toml: openpyxl, PyYAML
  - optional-dev: mypy for type checking

CONFIG:  
  - Environment variables: DATA_BASE_DIR, DATA_SOURCES_YML
  - Default locations: ./data, ./config/data_sources.yml

TESTING:
  - pytest fixtures for mock filesystem and sample data
  - Parameterized tests for different filename patterns
  - Integration test combining connector + domain service
```

## Validation Loop

### Level 1: Syntax & Style  
```bash
# Run these FIRST - fix any errors before proceeding
uv add openpyxl PyYAML  # Add missing dependencies
uv sync                  # Sync environment

uv run ruff check src/work_data_hub --fix  # Auto-fix formatting
uv run ruff format src/work_data_hub       # Consistent formatting

# If mypy is added:
uv add --dev mypy
uv run mypy src/work_data_hub

# Expected: No errors. If errors, READ the error message and fix.
```

### Level 2: Unit Tests (Create comprehensive test suite)
```python
# tests/io/test_file_connector.py - Key test cases
import pytest
from unittest.mock import patch, mock_open
import tempfile
from pathlib import Path

def test_discovers_xlsx_ignores_eml(tmp_path):
    """Test connector finds .xlsx files and ignores .eml files"""
    # Create mock file structure  
    (tmp_path / "test1.xlsx").touch()
    (tmp_path / "test.eml").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "test2.xlsx").touch()
    
    connector = DataSourceConnector(config_path="test_config.yml")
    # Mock settings.DATA_BASE_DIR to point to tmp_path
    
    discovered = connector.discover()
    
    paths = [f.path for f in discovered]
    assert any("test1.xlsx" in p for p in paths)
    assert any("test2.xlsx" in p for p in paths) 
    assert not any(".eml" in p for p in paths)

def test_extracts_year_month_from_filename():
    """Test regex extraction of year/month from Chinese filenames"""
    # Test with pattern: "(?P<year>20\\d{2})[-_/]?(?P<month>0?[1-9]|1[0-2]).*受托业绩.*\\.xlsx$"
    connector = DataSourceConnector(config_path="test_config.yml")
    
    # Mock file with Chinese filename
    test_files = [
        "2024_11_受托业绩报告.xlsx",  # Should extract year=2024, month=11
        "2023-12-受托业绩数据.xlsx",   # Should extract year=2023, month=12
        "some_other_file.xlsx"      # Should not match
    ]
    
    # Test extraction logic
    # ...assert year and month are extracted correctly

def test_latest_by_year_month_selection():
    """Test selection of latest version by year/month"""
    files = [
        DiscoveredFile("trustee", "2024_01_file.xlsx", 2024, 1, {}),
        DiscoveredFile("trustee", "2024_12_file.xlsx", 2024, 12, {}),
        DiscoveredFile("trustee", "2023_06_file.xlsx", 2023, 6, {})
    ]
    
    connector = DataSourceConnector(config_path="test_config.yml")
    result = connector._apply_selection_strategy(files)
    
    assert len(result) == 1
    assert result[0].year == 2024
    assert result[0].month == 12

# tests/domain/trustee_performance/test_service.py
def test_process_valid_rows():
    """Test domain service transforms valid input to typed output"""
    rows = [
        {"年": "2024", "月": "11", "some_field": "value1"},
        {"年": "2024", "月": "11", "some_field": "value2"}
    ]
    
    result = process(rows)
    
    assert len(result) == 2
    assert all(isinstance(item, TrusteePerformanceOut) for item in result)
    assert all(item.report_date.year == 2024 for item in result)
    assert all(item.report_date.month == 11 for item in result)

def test_process_invalid_rows_raises_validation_error():
    """Test domain service raises ValidationError for invalid input"""
    invalid_rows = [
        {"invalid_field": "no year or month data"}
    ]
    
    with pytest.raises(ValueError) as exc_info:
        process(invalid_rows)
    
    assert "validation" in str(exc_info.value).lower()
```

```bash
# Run tests and iterate until passing:
uv run pytest tests/ -v --cov=src/work_data_hub
# Target: 90%+ coverage, all tests passing
# If failing: Read error, understand root cause, fix code (never mock to pass)
```

### Level 3: Integration Test
```bash
# Create sample config and test end-to-end flow
echo 'domains:
  trustee_performance:
    pattern: "(?P<year>20\\d{2})[-_/]?(?P<month>0?[1-9]|1[0-2]).*受托业绩.*\\.xlsx$"
    select: latest_by_year_month
    sheet: 0' > test_config.yml

# Test file discovery
uv run python -c "
from src.work_data_hub.io.connectors.file_connector import DataSourceConnector
connector = DataSourceConnector('test_config.yml')
files = connector.discover('trustee_performance')  
print(f'Discovered {len(files)} files')
for f in files:
    print(f'  {f.domain}: {f.path} (year={f.year}, month={f.month})')
"

# Expected: Discovers files matching pattern, shows latest version selected
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] No linting errors: `uv run ruff check src/work_data_hub/`
- [ ] No type errors (if mypy added): `uv run mypy src/work_data_hub/`
- [ ] Integration test discovers files correctly
- [ ] Domain service processes sample data without errors
- [ ] Configuration loading works with YAML files
- [ ] Unicode filenames with Chinese characters handled correctly
- [ ] Latest version selection algorithm works for both date patterns and mtime fallback
- [ ] All functions are pure (no side effects) and testable
- [ ] Code follows CLAUDE.md conventions (file/function size limits)

---

## Anti-Patterns to Avoid
- ❌ Don't hardcode file paths or patterns - use YAML configuration
- ❌ Don't create impure functions with side effects in domain services
- ❌ Don't ignore Unicode handling - Chinese filenames will break simple regex
- ❌ Don't skip error handling for file I/O and Excel parsing failures  
- ❌ Don't use Pydantic v1 patterns (@validator, inner Config class)
- ❌ Don't couple file discovery to specific business logic - keep generic
- ❌ Don't create files > 500 lines or functions > 50 lines (CLAUDE.md limit)
- ❌ Don't write tests that depend on real files - use mocks and fixtures
- ❌ Don't proceed if validation gates fail - fix errors first

---

**Confidence Score: 9/10**

This PRP provides comprehensive context, clear implementation steps, robust validation gates, and addresses all known gotchas. The high confidence comes from:
- Detailed requirements analysis and architectural context
- Specific technical patterns and library usage examples  
- Comprehensive error handling and edge case coverage
- Clear validation strategy with executable tests
- All necessary documentation links and code patterns included

**Risk Factors (Low):**
- Unicode regex complexity (mitigated with examples and testing)
- Pydantic v2 migration patterns (mitigated with comprehensive documentation)
- File system edge cases (mitigated with robust testing strategy)