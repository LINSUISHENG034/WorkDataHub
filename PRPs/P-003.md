# PRP: Dagster Orchestration for Vertical Slice (Connector → Domain → Loader)

## Goal
Create Dagster ops and jobs that compose the existing vertical slice end-to-end: file discovery → Excel reading → trustee_performance domain processing → database loading. Provide CLI execution with database-optional (plan-only) mode to support testing without PostgreSQL dependency.

## Why
- **Orchestration Foundation**: Establishes the core workflow orchestration pattern for WorkDataHub's ETL pipelines
- **Production Readiness**: Moves from ad-hoc execution to structured, observable data pipelines
- **Scalability**: Provides foundation for scheduling, monitoring, and extending to additional domains
- **Testing Strategy**: Enables comprehensive testing without database dependencies via plan-only execution

## What
A complete Dagster-based orchestration layer that:
- Wraps existing components (connector, readers, domain service, loader) as thin Dagster ops
- Provides JSON-serializable data contracts between ops to avoid Dagster type system friction
- Supports CLI execution with configurable parameters (domain, mode, plan-only)
- Maintains database-optional execution for testing scenarios
- Follows modern Dagster patterns using Config classes instead of legacy config_schema

### Success Criteria
- [ ] Four ops created that wrap existing components with JSON-serializable I/O
- [ ] Job composes ops into trustee_performance workflow 
- [ ] CLI supports `--domain`, `--mode`, `--plan-only` arguments
- [ ] Plan-only execution generates SQL plans without database connection
- [ ] All validation gates pass (ruff, mypy, pytest)
- [ ] Smoke test demonstrates end-to-end execution

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Critical for implementation
- file: INITIAL.md
  why: Complete feature requirements and constraints
  
- file: docs/DoR/INITIAL_00.md  
  why: End-to-end slice intent, examples, and acceptance criteria
  
- file: docs/project/04_dependency_and_priority_analysis.md
  why: Dagster job composition pseudo-code patterns to follow
  
- file: tests/test_integration.py
  why: End-to-end flow without Dagster - replicate this pattern within ops
  
- file: src/work_data_hub/config/settings.py
  why: Environment configuration patterns and get_settings() usage
  
- file: src/work_data_hub/config/data_sources.yml
  why: Domain configuration structure - need to extend with table/pk
  
- file: src/work_data_hub/io/connectors/file_connector.py
  why: DataSourceConnector.discover() method patterns
  
- file: src/work_data_hub/io/readers/excel_reader.py  
  why: read_excel_rows() function signature and usage
  
- file: src/work_data_hub/domain/trustee_performance/service.py
  why: process() function signature and pydantic model handling
  
- file: src/work_data_hub/io/loader/warehouse_loader.py
  why: load() function signature, plan_only parameter, return format

- url: https://docs.dagster.io/concepts/ops-jobs-graphs/ops
  why: Modern Dagster ops patterns and Config class usage
  
- url: https://docs.pydantic.dev/latest/
  why: Pydantic v2 model serialization and validation patterns

- url: https://docs.dagster.io/guides/build/ops
  why: 2024 Dagster ops best practices and configuration patterns
  
- url: https://docs.dagster.io/api/dagster/config  
  why: Modern Config class validation with field_validator and model_validator
  
- file: CLAUDE.md
  critical: KISS principles, file limits, UV commands, testing requirements
```

### Current Codebase Structure
```bash
src/work_data_hub/
├── config/
│   ├── settings.py              # Settings with get_settings()
│   └── data_sources.yml         # Domain configurations
├── io/
│   ├── connectors/
│   │   └── file_connector.py    # DataSourceConnector
│   ├── readers/
│   │   └── excel_reader.py      # read_excel_rows()
│   └── loader/
│       └── warehouse_loader.py  # load() with plan_only support
├── domain/
│   └── trustee_performance/
│       ├── models.py            # Pydantic models
│       └── service.py           # process() function
└── utils/
    └── types.py                 # Shared type definitions

tests/
├── test_integration.py          # E2E test patterns to mirror
├── io/                         # Component tests
└── domain/                     # Domain tests
```

### Desired Codebase Structure (New Files)
```bash
src/work_data_hub/
└── orchestration/              # NEW PACKAGE
    ├── __init__.py            # Package init
    ├── ops.py                 # Four Dagster ops wrapping existing components
    └── jobs.py                # trustee_performance_job + CLI main()

# MODIFIED FILES:
src/work_data_hub/config/data_sources.yml  # Add table/pk for trustee_performance
tests/orchestration/                        # NEW: Smoke tests for orchestration
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: Dagster ops must exchange JSON-serializable data only
# ❌ DON'T pass Pydantic models directly between ops
# ✅ DO convert models to dicts: [m.model_dump() for m in models]

# CRITICAL: Use modern Dagster Config classes, not legacy config_schema
# ✅ DO: class MyOpConfig(Config): param: str
# ❌ DON'T: config_schema={"param": str}

# CRITICAL: Keep plan_only=True as default to avoid DB coupling in tests
# The load_op should only connect to DB when explicitly enabled

# CRITICAL: Use get_settings() pattern from existing codebase
# Import and call get_settings() in ops, don't create new config patterns

# CRITICAL: data_sources.yml must include table and pk for loader
# trustee_performance domain needs: table: "trustee_performance", pk: ["report_date", "plan_code", "company_code"]

# DAGSTER SPECIFICS (2024 Best Practices):
# - Use execute_in_process() for CLI execution, not dagster CLI command
# - Config classes automatically handle validation with Pydantic v2
# - Ops should be stateless and small
# - Use context.log for structured logging within ops (creates Dagster events)
# - For high-volume logging, use standard Python logging module instead
# - Use raise_on_error=True for testing, False for scripting
# - Provide DagsterInstance.get() to persist runs in UI for debugging

# MODERN CONFIG VALIDATION PATTERNS:
# Use @field_validator for single field validation:
# @field_validator("domain")
# def validate_domain(cls, v): 
#     if v not in ["trustee_performance"]: raise ValueError("Invalid domain")
#     return v

# Use @model_validator for cross-field validation:
# @model_validator(mode='after') 
# def validate_config_consistency(self): return self

# EXECUTE_IN_PROCESS ERROR HANDLING:
# - Default: raise_on_error=False, check result.success
# - Testing: raise_on_error=True, let exceptions bubble up
# - Access detailed errors via result.all_node_events when needed

# CLI INTEGRATION PATTERNS:
# - Build run_config dict from argparse args
# - Use nested key mapping for complex configs: --ops__my_op__config__param
# - Consider YAML default config + CLI overrides for complex scenarios
```

## Implementation Blueprint

### Data Models and Structure
The existing Pydantic models in `domain/trustee_performance/models.py` are already well-designed. The key is properly serializing them for inter-op communication:

```python
# In process_trustee_performance_op:
processed_models = process(rows, data_source=file_path)
# Convert to JSON-serializable format
return [model.model_dump() for model in processed_models]
```

### Task List (Complete in Order)

```yaml
Task 1 - Create orchestration package:
  CREATE src/work_data_hub/orchestration/__init__.py:
    - Empty init file for package

Task 2 - Extend data_sources.yml configuration:
  MODIFY src/work_data_hub/config/data_sources.yml:
    - FIND trustee_performance domain section
    - ADD table: "trustee_performance" 
    - ADD pk: ["report_date", "plan_code", "company_code"]
    - PRESERVE existing pattern, select, sheet configuration

Task 3 - Create Dagster ops:
  CREATE src/work_data_hub/orchestration/ops.py:
    - IMPORT Config from dagster (not config_schema)
    - CREATE DiscoverFilesConfig class with domain parameter
    - CREATE discover_files_op wrapping DataSourceConnector.discover()
    - CREATE ReadExcelConfig class with sheet parameter  
    - CREATE read_excel_op wrapping read_excel_rows()
    - CREATE process_trustee_performance_op (no config needed)
    - CREATE LoadConfig class with table, mode, pk, plan_only parameters
    - CREATE load_op wrapping warehouse_loader.load()
    - ENSURE all ops return JSON-serializable data types
    - USE context.log for logging within ops

Task 4 - Create job and CLI:
  CREATE src/work_data_hub/orchestration/jobs.py:
    - IMPORT job, execute_in_process from dagster
    - CREATE trustee_performance_job composing the four ops  
    - CREATE main() function with argparse for CLI
    - SUPPORT --domain, --mode, --plan-only arguments
    - USE execute_in_process() for synchronous execution
    - PRINT result summary (success, row counts, plans if plan_only)

Task 5 - Add smoke tests:
  CREATE tests/orchestration/__init__.py:
    - Empty init file
  CREATE tests/orchestration/test_ops.py:
    - Test each op individually with minimal fixtures
    - Use plan_only=True by default
    - Mock external dependencies as needed
  CREATE tests/orchestration/test_jobs.py:
    - Test execute_in_process() with plan_only mode
    - Verify CLI argument parsing
    - Test end-to-end flow without database
```

### Per-Task Pseudocode

#### Task 3 - ops.py Structure
```python
from dagster import op, Config, OpExecutionContext, MetadataValue
from typing import List, Dict, Any
from pydantic import field_validator, model_validator
from ..config.settings import get_settings
from ..io.connectors.file_connector import DataSourceConnector

class DiscoverFilesConfig(Config):
    domain: str = "trustee_performance"
    
    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain exists in configuration."""
        valid_domains = ["trustee_performance"]  # Could load from settings
        if v not in valid_domains:
            raise ValueError(f"Domain '{v}' not supported. Valid: {valid_domains}")
        return v

@op
def discover_files_op(context: OpExecutionContext, config: DiscoverFilesConfig) -> List[str]:
    """Discover files for specified domain, return file paths as strings."""
    settings = get_settings()
    connector = DataSourceConnector(settings.data_sources_config)
    
    try:
        discovered = connector.discover(config.domain)
        
        # Structured logging with metadata
        context.log.info(
            f"File discovery completed for domain '{config.domain}'",
            metadata={
                "domain": config.domain,
                "files_found": MetadataValue.int(len(discovered)),
                "discovery_details": MetadataValue.json({
                    "files": [{"path": f.path, "year": f.year, "month": f.month} for f in discovered]
                })
            }
        )
        
        # CRITICAL: Return JSON-serializable paths, not DiscoveredFile objects
        return [file.path for file in discovered]
        
    except Exception as e:
        context.log.error(f"File discovery failed for domain '{config.domain}': {e}")
        raise

class ReadExcelConfig(Config):
    sheet: int = 0
    
    @field_validator("sheet")
    @classmethod  
    def validate_sheet(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Sheet index must be non-negative")
        return v

@op
def read_excel_op(context: OpExecutionContext, config: ReadExcelConfig, file_path: str) -> List[Dict[str, Any]]:
    """Read Excel file and return rows as list of dictionaries."""
    from ..io.readers.excel_reader import read_excel_rows
    
    try:
        rows = read_excel_rows(file_path, sheet=config.sheet)
        
        context.log.info(
            f"Excel reading completed",
            metadata={
                "file_path": file_path,
                "sheet": config.sheet,
                "rows_read": MetadataValue.int(len(rows)),
                "sample_columns": MetadataValue.json(list(rows[0].keys()) if rows else [])
            }
        )
        
        return rows
        
    except Exception as e:
        context.log.error(f"Excel reading failed for '{file_path}': {e}")
        raise

# No config needed for domain processing - uses data_source from file path
@op  
def process_trustee_performance_op(context: OpExecutionContext, excel_rows: List[Dict[str, Any]], file_path: str) -> List[Dict[str, Any]]:
    """Process trustee performance data and return validated records as dicts."""
    from ..domain.trustee_performance.service import process
    
    try:
        # Process using existing domain service
        processed_models = process(excel_rows, data_source=file_path)
        
        # Convert Pydantic models to JSON-serializable dicts
        result_dicts = [model.model_dump() for model in processed_models]
        
        context.log.info(
            f"Domain processing completed",
            metadata={
                "input_rows": MetadataValue.int(len(excel_rows)),
                "processed_records": MetadataValue.int(len(result_dicts)),
                "data_source": file_path,
                "sample_record": MetadataValue.json(result_dicts[0] if result_dicts else {})
            }
        )
        
        return result_dicts
        
    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise

class LoadConfig(Config):
    table: str = "trustee_performance"
    mode: str = "delete_insert" 
    pk: List[str] = ["report_date", "plan_code", "company_code"]
    plan_only: bool = True
    
    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid_modes = ["delete_insert", "append"]
        if v not in valid_modes:
            raise ValueError(f"Mode '{v}' not supported. Valid: {valid_modes}")
        return v
    
    @model_validator(mode='after')
    def validate_delete_insert_requirements(self) -> 'LoadConfig':
        """Ensure delete_insert mode has primary key defined."""
        if self.mode == "delete_insert" and not self.pk:
            raise ValueError("delete_insert mode requires primary key columns")
        return self

@op
def load_op(context: OpExecutionContext, config: LoadConfig, processed_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Load processed data to database or return execution plan."""
    from ..io.loader.warehouse_loader import load
    
    try:
        # Connection is None for plan_only mode (testing)
        conn = None if config.plan_only else "TODO: get DB connection"
        
        result = load(
            table=config.table,
            rows=processed_rows,
            mode=config.mode,
            pk=config.pk,
            conn=conn
        )
        
        # Enhanced logging with execution details
        context.log.info(
            f"Load operation completed ({'PLAN-ONLY' if config.plan_only else 'EXECUTED'})",
            metadata={
                "table": config.table,
                "mode": config.mode,
                "plan_only": config.plan_only,
                "execution_summary": MetadataValue.json({
                    "deleted": result.get("deleted", 0),
                    "inserted": result.get("inserted", 0),
                    "batches": result.get("batches", 0)
                })
            }
        )
        
        return result
        
    except Exception as e:
        context.log.error(f"Load operation failed: {e}")
        raise
```

#### Task 4 - jobs.py Structure
```python
from dagster import job, DagsterInstance
import argparse
import yaml
from typing import Dict, Any
from .ops import discover_files_op, read_excel_op, process_trustee_performance_op, load_op

@job
def trustee_performance_job():
    """End-to-end trustee performance processing job."""
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()
    
    # For MVP: process first discovered file
    # TODO: Add dynamic mapping for multiple files in future
    excel_rows = read_excel_op(discovered_paths[0])  # Pass first file path
    processed_data = process_trustee_performance_op(excel_rows, discovered_paths[0])  # Also pass path for data_source
    load_result = load_op(processed_data)
    
    return load_result

def build_run_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Build Dagster run_config from CLI arguments."""
    # Load table/pk from data_sources.yml if needed
    from ..config.settings import get_settings
    
    settings = get_settings()
    try:
        with open(settings.data_sources_config, 'r', encoding='utf-8') as f:
            data_sources = yaml.safe_load(f)
            
        domain_config = data_sources.get('domains', {}).get(args.domain, {})
        table = domain_config.get('table', args.domain)  # Fallback to domain name
        pk = domain_config.get('pk', [])  # Empty list if not defined
        
    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        table = args.domain
        pk = []
    
    run_config = {
        "ops": {
            "discover_files_op": {
                "config": {
                    "domain": args.domain
                }
            },
            "read_excel_op": {
                "config": {
                    "sheet": args.sheet
                }
            },
            # process_trustee_performance_op has no config
            "load_op": {
                "config": {
                    "table": table,
                    "mode": args.mode,
                    "pk": pk,
                    "plan_only": args.plan_only
                }
            }
        }
    }
    
    return run_config

def main():
    """CLI entry point for local execution."""
    parser = argparse.ArgumentParser(
        description="Run WorkDataHub trustee performance job",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Core arguments
    parser.add_argument(
        "--domain", 
        default="trustee_performance",
        help="Domain to process"
    )
    parser.add_argument(
        "--mode", 
        choices=["delete_insert", "append"], 
        default="delete_insert",
        help="Load mode for database operations"
    )
    parser.add_argument(
        "--plan-only", 
        action="store_true", 
        default=True,
        help="Generate execution plan without database connection"
    )
    parser.add_argument(
        "--sheet", 
        type=int, 
        default=0,
        help="Excel sheet index to process"
    )
    
    # Advanced options
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug logging and persist run in Dagster UI"
    )
    parser.add_argument(
        "--raise-on-error", 
        action="store_true",
        help="Raise exceptions immediately (useful for testing)"
    )
    
    args = parser.parse_args()
    
    # Build run configuration from CLI arguments
    run_config = build_run_config(args)
    
    print(f"🚀 Starting trustee performance job...")
    print(f"   Domain: {args.domain}")
    print(f"   Mode: {args.mode}")
    print(f"   Plan-only: {args.plan_only}")
    print(f"   Sheet: {args.sheet}")
    print("=" * 50)
    
    # Execute job with appropriate settings
    try:
        # Use DagsterInstance for debug mode to persist run in UI
        instance = DagsterInstance.get() if args.debug else None
        
        result = trustee_performance_job.execute_in_process(
            run_config=run_config,
            instance=instance,
            raise_on_error=args.raise_on_error
        )
        
        # Report results
        print(f"✅ Job completed successfully: {result.success}")
        
        if result.success:
            # Extract and display execution summary
            load_result = result.output_for_node("load_op")
            
            if args.plan_only and "sql_plans" in load_result:
                print("\n📋 SQL Execution Plan:")
                print("-" * 30)
                for i, (op_type, sql, params) in enumerate(load_result["sql_plans"], 1):
                    print(f"{i}. {op_type}:")
                    print(f"   {sql}")
                    if params:
                        print(f"   Parameters: {len(params)} values")
                    print()
            
            # Display execution statistics
            print(f"\n📊 Execution Summary:")
            print(f"   Table: {load_result.get('table', 'N/A')}")
            print(f"   Mode: {load_result.get('mode', 'N/A')}")
            print(f"   Deleted: {load_result.get('deleted', 0)} rows")
            print(f"   Inserted: {load_result.get('inserted', 0)} rows")
            print(f"   Batches: {load_result.get('batches', 0)}")
            
        else:
            print("❌ Job completed with failures")
            if not args.raise_on_error:
                # Print error details when not raising
                for event in result.all_node_events:
                    if event.is_failure:
                        print(f"   Error in {event.node_name}: {event.event_specific_data}")
                        
    except Exception as e:
        print(f"💥 Job execution failed: {e}")
        if args.debug:
            import traceback
            print("\n🐛 Full traceback:")
            traceback.print_exc()
        return 1  # Exit code for failure
    
    return 0  # Exit code for success

if __name__ == "__main__":
    exit(main())
```

### Integration Points
```yaml
CONFIG:
  - EXTEND data_sources.yml with table/pk under trustee_performance domain
  - USE get_settings() pattern from existing codebase
  - LEVERAGE existing WDH_ environment variable prefix

DATA_FLOW:
  - discover_files_op → List[str] (file paths)
  - read_excel_op → List[Dict[str, Any]] (raw Excel rows) 
  - process_trustee_performance_op → List[Dict[str, Any]] (validated models as dicts)
  - load_op → Dict[str, Any] (execution metadata/plans)

CLI:
  - PATTERN: python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --plan-only
  - ALTERNATIVE: Add console_scripts entry to pyproject.toml (future enhancement)
```

## Validation Loop

### Level 1: Syntax & Style  
```bash
# MUST pass before proceeding
uv run ruff check src/work_data_hub/orchestration/ --fix
uv run mypy src/work_data_hub/orchestration/

# Expected: No errors. Fix any issues before continuing.
```

### Level 2: Unit Tests
```bash
# Create and run tests for each component
uv run pytest tests/orchestration/ -v

# Tests should verify:
# - Ops handle valid inputs correctly
# - JSON serialization works properly  
# - Plan-only mode generates expected SQL plans
# - CLI argument parsing works
# - Error handling for invalid inputs
# - Config validation with @field_validator works
# - Structured logging creates proper Dagster events

# Example test patterns to implement:
def test_discover_files_op_success(tmp_path):
    """Test successful file discovery with metadata logging."""
    # Setup test files and config
    # Execute op with execute_in_process(raise_on_error=True)
    # Assert JSON-serializable output and proper logging

def test_config_validation_errors():
    """Test Config class validators raise appropriate errors."""
    # Test invalid domain, mode, sheet values
    # Use pytest.raises to verify ValidationError
    
def test_load_op_plan_only_mode():
    """Test load_op generates SQL plans without database."""
    # Execute with plan_only=True
    # Assert sql_plans in result and proper structure
```

### Level 3: Integration Test
```bash
# Test CLI execution with plan-only mode (no DB required)
uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --plan-only

# Expected output (enhanced format):
# 🚀 Starting trustee performance job...
#    Domain: trustee_performance
#    Mode: delete_insert
#    Plan-only: True
#    Sheet: 0
# ==================================================
# ✅ Job completed successfully: True
# 
# 📋 SQL Execution Plan:
# ------------------------------
# 1. DELETE:
#    DELETE FROM trustee_performance WHERE (report_date, plan_code, company_code) IN ...
# 
# 2. INSERT:
#    INSERT INTO trustee_performance (...) VALUES ...
#    Parameters: 100 values
# 
# 📊 Execution Summary:
#    Table: trustee_performance
#    Mode: delete_insert
#    Deleted: 3 rows
#    Inserted: 3 rows
#    Batches: 1

# Test with debug mode to verify UI persistence
uv run python -m src.work_data_hub.orchestration.jobs --plan-only --debug

# Test error handling
uv run python -m src.work_data_hub.orchestration.jobs --domain invalid_domain --raise-on-error
# Should raise ValidationError due to @field_validator

# Test with sample data directory if available
WDH_DATA_BASE_DIR=/path/to/sample/data uv run python -m src.work_data_hub.orchestration.jobs --plan-only
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest -v`
- [ ] No linting errors: `uv run ruff check src/ --fix`
- [ ] No type errors: `uv run mypy src/`
- [ ] CLI execution works: `uv run python -m src.work_data_hub.orchestration.jobs --plan-only`
- [ ] Plan-only generates SQL without database connection
- [ ] data_sources.yml properly extended with table/pk information
- [ ] Ops exchange only JSON-serializable data
- [ ] Error handling follows existing patterns

---

## Anti-Patterns to Avoid
- ❌ Don't pass Pydantic models directly between ops - use model_dump()
- ❌ Don't use legacy config_schema - use modern Config classes
- ❌ Don't require database for default testing - keep plan_only=True
- ❌ Don't reinvent configuration patterns - use existing get_settings()
- ❌ Don't ignore existing error handling patterns - follow module conventions
- ❌ Don't create massive ops - keep them thin wrappers around existing components

---

**PRP Confidence Score: 9.5/10** - Comprehensive context with 2024 best practices, detailed implementation patterns, executable validation gates, enhanced error handling, structured logging, and robust CLI integration for highest one-pass success probability.

## Research-Enhanced Features (2024)

### Modern Dagster Patterns Integrated:
- ✅ **Config Classes with Validation**: `@field_validator` and `@model_validator` for robust parameter validation
- ✅ **Structured Logging**: `MetadataValue.json()` and `context.log` with proper event creation
- ✅ **Enhanced Error Handling**: `raise_on_error` parameter usage for testing vs scripting
- ✅ **Debug Mode Support**: `DagsterInstance.get()` integration for UI persistence
- ✅ **Advanced CLI Patterns**: Comprehensive argparse with nested configuration building

### Implementation Robustness:
- ✅ **JSON Serialization Safety**: Explicit model_dump() conversions with validation
- ✅ **Configuration Validation**: Multi-level validation with clear error messages  
- ✅ **Comprehensive Error Reporting**: Detailed CLI output with emojis and structured summaries
- ✅ **Testing Patterns**: Specific test examples with modern pytest patterns
- ✅ **Documentation URLs**: Current 2024 Dagster documentation links

This PRP provides everything needed for successful one-pass implementation of modern Dagster orchestration while maintaining existing codebase patterns and comprehensive testing strategies.