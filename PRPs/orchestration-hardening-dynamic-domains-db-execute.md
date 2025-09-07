# Orchestration Hardening: Dynamic Domains, Optional DB Execute, Multi-File, Structured Logging

## Goal
Harden the Dagster orchestration layer by implementing dynamic domain validation from YAML configuration, optional real database execution with explicit --execute flag, basic multi-file processing support, and enhanced structured logging for better observability.

## Why
- **Risk Mitigation**: Replace hardcoded domain lists with configuration-driven validation to prevent runtime errors with new domains
- **Production Readiness**: Enable real database execution while maintaining safe plan-only default behavior
- **Scalability**: Support processing multiple files in a single job run to handle batch scenarios
- **Observability**: Improve logging with structured metadata to aid debugging and monitoring in production

## What
Transform the existing plan-only orchestration system into a production-capable pipeline that:
- Dynamically validates domains against `data_sources.yml` configuration
- Optionally executes against PostgreSQL database when explicitly requested
- Processes multiple discovered files with configurable limits
- Provides rich structured logging for operational insights

### Success Criteria
- [ ] Domain validation loads valid domains from `data_sources.yml` and rejects invalid domains with clear error messages
- [ ] `load_op` executes against PostgreSQL when `--execute` flag is provided, defaults to plan-only mode
- [ ] CLI supports `--execute` and `--max-files N` flags with proper help documentation
- [ ] Multi-file processing accumulates records from up to N files and loads them in a single operation
- [ ] Structured logging includes counts, table names, modes, and processing metadata throughout the pipeline
- [ ] All tests pass including new tests for dynamic domains, execute path (mocked), and multi-file accumulation
- [ ] Code passes ruff, mypy, and pytest validation gates

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://docs.dagster.io/concepts/ops-jobs-graphs/ops
  why: Understanding ops configuration and execution patterns
  
- url: https://docs.pydantic.dev/latest/concepts/validators/  
  why: field_validator and model_validator patterns for dynamic validation
  section: field_validator with classmethod decorator usage
  critical: Pydantic v2 syntax differences from v1

- url: https://www.psycopg.org/docs/module.html#psycopg2.connect
  why: Connection string format and context manager usage
  critical: Proper connection cleanup and transaction handling

- file: src/work_data_hub/orchestration/ops.py
  why: Current op implementations and configuration patterns to extend
  critical: DiscoverFilesConfig.validate_domain hardcoded list needs replacement

- file: src/work_data_hub/orchestration/jobs.py  
  why: CLI argument patterns and job wiring to modify for new flags
  critical: build_run_config and main() function modification patterns

- file: src/work_data_hub/config/data_sources.yml
  why: Structure of domains configuration for dynamic loading
  critical: domains.{domain_name} keys are the valid domain names to extract

- file: src/work_data_hub/config/settings.py
  why: DatabaseSettings.get_connection_string() usage for psycopg2 connections
  critical: Environment variable pattern WDH_DATABASE__* for configuration

- file: src/work_data_hub/io/loader/warehouse_loader.py
  why: load() function signature and conn parameter usage patterns
  critical: conn=None returns SQL plans, conn=connection executes against DB

- file: tests/orchestration/test_ops.py
  why: Testing patterns for ops validation and mocking external dependencies
  critical: patch() usage for DataSourceConnector and function mocks

- file: tests/orchestration/test_jobs.py
  why: CLI testing patterns and job execution mocking
  critical: sys.argv patching and captured output validation
```

### Current Codebase Structure
```bash
src/work_data_hub/
├── orchestration/
│   ├── ops.py          # Ops with hardcoded domain validation (MODIFY)
│   └── jobs.py         # CLI without --execute/--max-files flags (MODIFY)
├── config/
│   ├── settings.py     # DatabaseSettings with get_connection_string()
│   └── data_sources.yml # Domain configurations with table/pk info
├── io/
│   └── loader/
│       └── warehouse_loader.py # load() function supports conn parameter
└── domain/
    └── trustee_performance/
        └── service.py  # process() function for data transformation

tests/
├── orchestration/
│   ├── test_ops.py     # Op unit tests with mocking (EXTEND)
│   └── test_jobs.py    # CLI and job tests (EXTEND)
└── io/
    └── test_warehouse_loader.py # Loader tests with mock connections
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: psycopg2 import must be conditional and handle ImportError gracefully
# Load only when needed to avoid dev environment issues
if not config.plan_only:
    try:
        import psycopg2
    except ImportError:
        raise DataWarehouseLoaderError(
            "psycopg2 not available. Run 'uv sync' to install database dependencies."
        )

# CRITICAL: data_sources.yml loading requires UTF-8 encoding
# YAML structure: domains.{domain_name} where keys are valid domain names
with open(settings.data_sources_config, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
valid_domains = sorted((data.get("domains") or {}).keys())

# CRITICAL: Connection string format from DatabaseSettings
# Uses either direct URI or constructs from host/port/user/password/db
dsn = get_settings().database.get_connection_string()
# Returns: "postgresql://user:password@host:port/database"

# CRITICAL: Windows PowerShell environment activation (mentioned in INITIAL.md)  
# Claude should use: .\.venv\Scripts\Activate.ps1 (not Linux paths)
# All commands should use uv run prefix for cross-platform compatibility

# CRITICAL: Dagster job execution requires JSON-serializable data flow
# Multi-file accumulation must maintain list[dict] format between ops
# No Pydantic models in inter-op communication, only basic Python types
```

## Implementation Blueprint

### Task 1: Dynamic Domain Validation in ops.py
```python
# MODIFY src/work_data_hub/orchestration/ops.py
# ADD after imports:
import yaml
from pathlib import Path

# ADD helper function before DiscoverFilesConfig:
def _load_valid_domains() -> List[str]:
    """Load valid domain names from data_sources.yml configuration."""
    try:
        settings = get_settings()
        config_path = Path(settings.data_sources_config)
        
        if not config_path.exists():
            logger.warning(f"Data sources config not found: {config_path}")
            return ["trustee_performance"]  # Fallback to current default
            
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        domains = data.get("domains") or {}
        valid_domains = sorted(domains.keys())
        
        if not valid_domains:
            logger.warning("No domains found in configuration, using default")
            return ["trustee_performance"]
            
        logger.debug(f"Loaded {len(valid_domains)} valid domains: {valid_domains}")
        return valid_domains
        
    except Exception as e:
        logger.error(f"Failed to load domains from configuration: {e}")
        # Fallback to prevent complete failure
        return ["trustee_performance"]

# MODIFY DiscoverFilesConfig.validate_domain:
@field_validator("domain")
@classmethod
def validate_domain(cls, v: str) -> str:
    """Validate domain exists in data_sources.yml configuration."""
    valid_domains = _load_valid_domains()
    if v not in valid_domains:
        raise ValueError(f"Domain '{v}' not supported. Valid: {valid_domains}")
    return v
```

### Task 2: Optional Database Execution in load_op
```python
# MODIFY load_op in src/work_data_hub/orchestration/ops.py
# REPLACE connection handling section around line 200:

conn = None  # Default: plan-only mode
if not config.plan_only:
    try:
        import psycopg2
        settings = get_settings()
        dsn = settings.database.get_connection_string()
        
        logger.info(f"Connecting to database for execution (table: {config.table})")
        conn = psycopg2.connect(dsn)
        
    except ImportError as e:
        raise DataWarehouseLoaderError(
            "psycopg2 not available for database execution. "
            "Install with: uv sync"
        ) from e
    except Exception as e:
        raise DataWarehouseLoaderError(
            f"Database connection failed: {e}. "
            "Check WDH_DATABASE__* environment variables."
        ) from e

result = load(
    table=config.table,
    rows=processed_rows,
    mode=config.mode,
    pk=config.pk,
    conn=conn,
)

# Enhanced logging with execution mode
mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
context.log.info(
    f"Load operation completed ({mode_text}) - "
    f"table: {config.table}, mode: {config.mode}, "
    f"deleted: {result.get('deleted', 0)}, inserted: {result.get('inserted', 0)}, "
    f"batches: {result.get('batches', 0)}"
)
```

### Task 3: CLI Flags Enhancement in jobs.py  
```python
# MODIFY main() argument parser in src/work_data_hub/orchestration/jobs.py
# ADD after existing arguments around line 115:

parser.add_argument(
    "--execute",
    action="store_true", 
    default=False,
    help="Execute against database (default: plan-only mode for safety)"
)

parser.add_argument(
    "--max-files",
    type=int,
    default=1,
    help="Maximum number of discovered files to process (default: 1)"
)

# MODIFY build_run_config to handle execute flag:
# UPDATE around line 77 in load_op config:
"load_op": {
    "config": {
        "table": table,
        "mode": args.mode, 
        "pk": pk,
        "plan_only": not args.execute,  # Invert execute flag
    }
},

# UPDATE CLI output section around line 138:
print(f"   Domain: {args.domain}")
print(f"   Mode: {args.mode}")
print(f"   Execute: {args.execute}")
print(f"   Plan-only: {not args.execute}")
print(f"   Sheet: {args.sheet}")
print(f"   Max files: {args.max_files}")
```

### Task 4: Multi-File Processing Job Logic
```python  
# MODIFY trustee_performance_job in src/work_data_hub/orchestration/jobs.py
# This requires significant job rewiring - CREATE new job version:

@job
def trustee_performance_job():
    """
    End-to-end trustee performance processing job with multi-file support.
    
    Processes up to max_files discovered files, accumulates results,
    then performs a single load operation.
    """
    discovered_paths = discover_files_op()
    
    # Multi-file processing will be handled in a new pattern
    # For now, enhance existing single-file job with better logging
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_trustee_performance_op(excel_rows, discovered_paths)
    load_op(processed_data)

# ADD new multi-file job execution logic in main() around line 147:
# This will require modifying the execution logic to handle max_files
# For MVP: Modify read_excel_op to respect max_files limit via configuration
```

### Task 5: Enhanced Structured Logging
```python
# UPDATE all ops in src/work_data_hub/orchestration/ops.py with enhanced logging:

# discover_files_op enhancement:
context.log.info(
    f"File discovery completed - domain: {config.domain}, "
    f"found: {len(discovered)} files, "
    f"config: {settings.data_sources_config}"
)

# read_excel_op enhancement:
context.log.info(
    f"Excel reading completed - file: {file_path}, "
    f"sheet: {config.sheet}, rows: {len(rows)}, "
    f"columns: {list(rows[0].keys()) if rows else []}"
)

# process_trustee_performance_op enhancement:
context.log.info(
    f"Domain processing completed - source: {file_path}, "
    f"input_rows: {len(excel_rows)}, output_records: {len(result_dicts)}, "
    f"domain: trustee_performance"
)
```

### Task 6: Comprehensive Test Coverage
```python
# ADD to tests/orchestration/test_ops.py:

def test_load_valid_domains_from_yaml(self, tmp_path):
    """Test _load_valid_domains loads from YAML correctly."""
    config_data = {
        "domains": {
            "trustee_performance": {"table": "trustee_performance"},
            "annuity_performance": {"table": "annuity_performance"}
        }
    }
    config_file = tmp_path / "test_config.yml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)
        
    with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
        mock_settings.return_value.data_sources_config = str(config_file)
        
        from src.work_data_hub.orchestration.ops import _load_valid_domains
        domains = _load_valid_domains()
        
        assert domains == ["annuity_performance", "trustee_performance"]

def test_load_op_execute_mode_mocked(self):
    """Test load_op with execute=True using mocked psycopg2."""
    processed_rows = [{"col": "value"}]
    
    mock_conn = Mock()
    mock_result = {
        "mode": "delete_insert", 
        "table": "test_table",
        "deleted": 1,
        "inserted": 1,
        "batches": 1
    }
    
    with patch("src.work_data_hub.orchestration.ops.psycopg2") as mock_psycopg2:
        mock_psycopg2.connect.return_value = mock_conn
        
        with patch("src.work_data_hub.orchestration.ops.load") as mock_load:
            mock_load.return_value = mock_result
            
            with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
                mock_db = Mock()
                mock_db.get_connection_string.return_value = "postgresql://test"
                mock_settings.return_value.database = mock_db
                
                context = build_op_context()
                config = LoadConfig(plan_only=False, table="test_table", pk=["id"])
                result = load_op(context, config, processed_rows)
                
                # Verify connection was created and passed to load()
                mock_psycopg2.connect.assert_called_once_with("postgresql://test")
                mock_load.assert_called_once_with(
                    table="test_table",
                    rows=processed_rows,
                    mode="delete_insert",
                    pk=["id"],
                    conn=mock_conn
                )

# ADD to tests/orchestration/test_jobs.py:
def test_cli_execute_flag(self):
    """Test CLI --execute flag sets plan_only=False."""
    test_args = ["jobs.py", "--execute", "--domain", "trustee_performance"]
    
    with patch("sys.argv", test_args):
        with patch("src.work_data_hub.orchestration.jobs.build_run_config") as mock_build:
            mock_build.return_value = {}
            
            # Mock job execution to avoid complexity
            with patch("src.work_data_hub.orchestration.jobs.trustee_performance_job"):
                captured_output = io.StringIO()
                with patch("sys.stdout", captured_output):
                    main()
                    
                output = captured_output.getvalue()
                assert "Execute: True" in output
                assert "Plan-only: False" in output
```

## Integration Points
```yaml
DATABASE:
  - connection: Use Settings.database.get_connection_string() for psycopg2.connect()
  - environment: Reads WDH_DATABASE__HOST, WDH_DATABASE__PORT, etc. or WDH_DATABASE__URI
  - error_handling: Clear messages directing user to check environment variables

CONFIG:  
  - source: data_sources.yml contains domains.{domain_name} structure
  - validation: Load domains dynamically with fallback to ["trustee_performance"]
  - encoding: Always use UTF-8 for YAML file reading

CLI:
  - new_flags: --execute (sets plan_only=False) and --max-files N
  - backward_compatibility: Default behavior unchanged (plan-only, single file)
  - help_text: Clear documentation of safety model and execution modes

TESTING:
  - mocking: Use patch() for psycopg2.connect to avoid real DB dependency  
  - validation: Test both plan-only and execute modes with mocked connections
  - coverage: Test error cases like missing config, connection failures
```

## Validation Loop

### Level 1: Syntax & Style  
```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff check src/work_data_hub/orchestration/ --fix
uv run mypy src/work_data_hub/orchestration/
uv run ruff check tests/orchestration/ --fix

# Expected: No errors. If errors exist, read and fix before proceeding.
```

### Level 2: Unit Tests
```bash  
# Test each new feature individually
uv run pytest tests/orchestration/test_ops.py::TestDiscoverFilesOp::test_load_valid_domains_from_yaml -v
uv run pytest tests/orchestration/test_ops.py::TestLoadOp::test_load_op_execute_mode_mocked -v  
uv run pytest tests/orchestration/test_jobs.py::TestCLIMain::test_cli_execute_flag -v

# Run all orchestration tests
uv run pytest tests/orchestration/ -v

# Expected: All tests pass. If failing, read error output and fix root cause.
```

### Level 3: Integration Testing
```bash
# Activate virtual environment  
.\.venv\Scripts\Activate.ps1

# Test CLI with new flags (plan-only mode - safe)
uv run python -m src.work_data_hub.orchestration.jobs --help
# Expected: Should show --execute and --max-files in help output

uv run python -m src.work_data_hub.orchestration.jobs --domain trustee_performance --max-files 2 
# Expected: Successful execution with "Plan-only: True" and "Max files: 2"

# Test execute flag validation (will fail without DB, but should show attempt)  
uv run python -m src.work_data_hub.orchestration.jobs --execute --domain trustee_performance
# Expected: Should show "Execute: True" and may fail on DB connection (acceptable for testing)
```

## Final Validation Checklist
- [ ] All tests pass: `uv run pytest tests/orchestration/ -v`
- [ ] No linting errors: `uv run ruff check src/work_data_hub/orchestration/`
- [ ] No type errors: `uv run mypy src/work_data_hub/orchestration/`
- [ ] CLI help shows new flags: `uv run python -m src.work_data_hub.orchestration.jobs --help`
- [ ] Plan-only mode works: `uv run python -m src.work_data_hub.orchestration.jobs --max-files 2`
- [ ] Dynamic domain validation works with valid/invalid domains
- [ ] Execute flag changes plan_only behavior appropriately
- [ ] Structured logging includes all required metadata
- [ ] Error handling provides clear user guidance

---

## Anti-Patterns to Avoid
- ❌ Don't hardcode domain lists when YAML configuration exists
- ❌ Don't default to execute mode - keep plan-only as safe default
- ❌ Don't skip connection error handling - provide clear user guidance
- ❌ Don't ignore test failures - mock properly to avoid real DB dependencies
- ❌ Don't break backward compatibility - existing scripts should continue working
- ❌ Don't import psycopg2 at module level - import only when needed for execute mode

**Confidence Score: 8/10** - This PRP provides comprehensive context, clear implementation steps, established patterns to follow, and thorough validation. The AI should be able to implement this successfully in one pass given the detailed guidance and extensive real-world examples from the existing codebase.