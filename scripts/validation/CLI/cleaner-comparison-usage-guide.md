# Cleaner Comparison - Usage Guide

## Overview

This CLI tool compares the data cleansing output between the **Legacy cleaner** and the **New Pipeline** for any configured domain. It enables row-by-row validation to ensure data integrity during migration.

**Story 6.2-P12**: Refactored to config-driven, domain-agnostic architecture.

## Scripts

| Script | Purpose |
|--------|---------|
| `cleaner_compare.py` | Core comparison script with CLI interface (domain-agnostic) |
| `domain_config.py` | Shared configuration constants (classifications, paths) |
| `report_generator.py` | Report generation (CSV, Markdown, console) |
| `configs/` | Domain-specific configurations |

### Domain Configurations

| Config File | Domain | Description |
|-------------|--------|-------------|
| `configs/annuity_performance.py` | `annuity_performance` | 规模明细 domain |

## Prerequisites

1. **Python Environment**: Use `uv` for package management
2. **Environment File**: `.wdh_env` with database credentials
3. **Legacy Dependencies**: Ensure the legacy cleaner can import (if not, use `--new-only`)

## Usage

### Required Argument: `--domain`

The `--domain` argument is **required** and specifies which domain to compare.

```powershell
# List available domains
$env:PYTHONPATH='src'; uv run python scripts/validation/CLI/cleaner_compare.py --help
```

### Basic Comparison (100 rows)

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance `
    "tests\fixtures\real_data\202311\收集数据\数据采集\V1\【for年金分战区经营分析】24年11月年金规模收入数据1209采集.xlsx" `
    --limit 100 --debug --export
```

### Auto-Discovery Mode (Recommended)

```powershell
# Automatically discover the correct file by month
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance --month 202311 --limit 100 --debug --export
```

### Full Dataset Comparison

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance <excel_path> --limit 0 --debug --export
```

> [!WARNING]
> `--limit 0` runs on the full dataset and may be slow and memory-intensive.

### New Pipeline Only (No Legacy Dependencies)

```powershell
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance <excel_path> --new-only --debug --limit 100
```

### EQC Enrichment Mode (Full Company ID Resolution)

Use `--enrichment` to enable real-time EQC API lookups for unresolved company names.

```powershell
# Full dataset with EQC enrichment enabled
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance --month 202501 --limit 0 --debug --export --enrichment
```

```powershell
# With custom EQC budget (default: 1000)
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance --month 202501 --limit 0 --enrichment --sync-budget 5000
```

### Deterministic Export (Reproducible Comparisons)

Use `--run-id` to create deterministic output directory names for reproducible comparisons.

```powershell
# Baseline run with custom run-id
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_performance --month 202311 --limit 100 --export --run-id baseline-202311
```

This creates outputs in `_artifacts/baseline-202311/` instead of a timestamp-based directory.

> [!TIP]
> Use `--run-id` when comparing results across multiple runs or creating reproducible test baselines.

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--domain` | (required) | Domain to compare (e.g., `annuity_performance`) |
| `excel_path` | (optional) | Path to source Excel file (required if `--month` not used) |
| `--month YYYYMM` | (None) | Auto-discover source file by month |
| `--sheet` | (domain-specific) | Sheet name to process |
| `--limit` | `100` | Row limit (0 = no limit) |
| `--enrichment` | `False` | Enable EQC sync lookups |
| `--debug` | `False` | Save debug snapshots |
| `--export` | `False` | Export CSV and Markdown reports |
| `--new-only` | `False` | Run only New Pipeline |
| `--no-auto-refresh-token` | `False` | Disable automatic token refresh |
| `--sync-budget` | `1000` | EQC sync lookup budget |
| `--run-id` | (timestamp) | Custom run ID for deterministic export |

> [!NOTE]
> When `--enrichment` is enabled and the EQC token is invalid/expired, a QR code popup will automatically appear for token refresh (Story 6.2-P11). Use `--no-auto-refresh-token` to disable this behavior.

## Output Structure

All outputs are saved to a named directory (timestamp or `--run-id`):

```
scripts/validation/CLI/_artifacts/<run_id>/
├── diff_report_<run_id>.csv           # Detailed differences
├── diff_summary_<run_id>.md           # Markdown summary
└── debug_snapshots/                   # Optional (--debug)
    ├── legacy_output.csv
    └── new_pipeline_output.csv
```

## Adding a New Domain

This section provides comprehensive guidance for adding comparison support for a new domain with minimal implementation effort.

### Quick Start Checklist

- [ ] 1. Identify field classifications (numeric, derived, upgrade)
- [ ] 2. Create config file in `configs/`
- [ ] 3. Implement lazy imports for Legacy cleaner
- [ ] 4. Implement `build_new_pipeline()` method
- [ ] 5. Register config in `configs/__init__.py`
- [ ] 6. Test with `--limit 10` first
- [ ] 7. Run full validation

### Step 1: Identify Field Classifications

Before writing code, classify the fields in your domain:

| Classification | Purpose | Comparison Rule | Example |
|----------------|---------|-----------------|---------|
| **Numeric** | Financial/quantity fields | Zero tolerance, `Decimal` precision, NULL=0 | 期初资产规模, 供款 |
| **Derived** | Mapping/transformation fields | String comparison after normalization | 月度, 机构代码, 计划代码 |
| **Upgrade** | Fields intentionally enhanced | Classification-based (upgrade/regression) | company_id, 客户名称 |

> [!TIP]
> Check the Legacy cleaner's `clean()` method and the New Pipeline's step definitions to identify which fields are transformed.

### Step 2: Create Config File

Create `configs/<domain_name>.py`:

```python
"""
<Domain Name> Domain Configuration.

Contains all domain-specific values for the <Domain Description> domain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from .base import DomainComparisonConfig

if TYPE_CHECKING:
    import pandas as pd


class <DomainName>Config(DomainComparisonConfig):
    """Configuration for <domain_name> domain comparison."""

    # =========================================================================
    # Required Properties
    # =========================================================================

    @property
    def domain_name(self) -> str:
        """Unique domain identifier. Must match FileDiscoveryService config."""
        return "<domain_name>"

    @property
    def sheet_name(self) -> str:
        """Default Excel sheet name for this domain."""
        return "<Sheet Name>"

    @property
    def numeric_fields(self) -> List[str]:
        """
        Fields requiring zero-tolerance numeric comparison.
        - NULL and 0 are treated as equivalent
        - Uses Decimal precision (no floating point errors)
        - Non-numeric values are flagged as CRITICAL errors
        """
        return [
            # Add financial/quantity fields here
            # Example: "期初资产规模", "期末资产规模", "供款"
        ]

    @property
    def derived_fields(self) -> List[str]:
        """
        Fields computed from source via mappings/transformations.
        - String comparison after normalization
        - Date fields are converted to ISO format
        """
        return [
            # Add mapping/transformation fields here
            # Example: "月度", "机构代码", "计划代码"
        ]

    # =========================================================================
    # Optional Properties (override defaults if needed)
    # =========================================================================

    @property
    def upgrade_fields(self) -> List[str]:
        """Fields intentionally enhanced in New Pipeline. Default: ["company_id"]"""
        return ["company_id"]  # Add more if needed, e.g., "客户名称"

    @property
    def column_name_mapping(self) -> Dict[str, str]:
        """
        Column name mapping: Legacy -> New Pipeline.
        Use when Legacy and New Pipeline have different column names for the same field.
        Default: {} (no mapping needed)
        """
        return {
            # "Legacy Column Name": "New Pipeline Column Name",
        }

    # =========================================================================
    # Required Methods
    # =========================================================================

    def get_legacy_cleaner(self) -> Type:
        """
        Get Legacy cleaner class for this domain.

        IMPORTANT: Use lazy import to enable --new-only mode without Legacy dependencies.
        """
        # Lazy import - only executed when Legacy comparison is needed
        from <legacy_module_path> import <LegacyCleanerClass>
        return <LegacyCleanerClass>

    def build_new_pipeline(
        self,
        excel_path: str,
        sheet_name: str,
        row_limit: Optional[int],
        enable_enrichment: bool,
        sync_lookup_budget: int,
    ) -> "pd.DataFrame":
        """
        Build and execute New Pipeline for this domain.

        This method should:
        1. Load raw data from Excel
        2. Apply row limit if specified
        3. Build and execute the pipeline
        4. Return the cleaned DataFrame

        See annuity_performance.py for a complete implementation example.
        """
        import pandas as pd

        from work_data_hub.config.settings import get_settings
        from work_data_hub.domain.<domain_name>.pipeline_builder import (
            build_bronze_to_silver_pipeline,
            load_plan_override_mapping,  # If applicable
        )
        from work_data_hub.domain.pipelines.types import PipelineContext

        # 1. Load raw data
        raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)

        # 2. Apply row limit
        if row_limit and row_limit > 0:
            raw_df = raw_df.head(row_limit)

        # 3. Load optional mappings
        plan_override_mapping = load_plan_override_mapping()  # If applicable

        # 4. Setup database connection (optional but recommended)
        settings = get_settings()
        engine = None
        try:
            from sqlalchemy import create_engine
            engine = create_engine(settings.get_database_connection_string())
        except Exception as e:
            print(f"   ⚠️ Database engine init failed: {e}")

        # 5. Build and execute pipeline
        if engine is None:
            pipeline = build_bronze_to_silver_pipeline(
                enrichment_service=None,
                plan_override_mapping=plan_override_mapping,
                sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
                mapping_repository=None,
            )
            context = PipelineContext(
                pipeline_name="cleaner_comparison",
                execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={},
                domain=self.domain_name,
                run_id="compare",
                extra={},
            )
            return pipeline.execute(raw_df.copy(), context)

        # With database mapping repository
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            CompanyMappingRepository,
        )
        with engine.connect() as conn:
            mapping_repository = CompanyMappingRepository(conn)
            print("   ✓ Database mapping repository enabled")

            pipeline = build_bronze_to_silver_pipeline(
                enrichment_service=None,
                plan_override_mapping=plan_override_mapping,
                sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
                mapping_repository=mapping_repository,
            )
            context = PipelineContext(
                pipeline_name="cleaner_comparison",
                execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={},
                domain=self.domain_name,
                run_id="compare",
                extra={},
            )
            result_df = pipeline.execute(raw_df.copy(), context)
            conn.commit()  # Persist EQC cache writes
            return result_df


# =========================================================================
# Registration (Required)
# =========================================================================

def _register():
    """Register this config in the domain registry."""
    from . import DOMAIN_CONFIGS
    DOMAIN_CONFIGS["<domain_name>"] = <DomainName>Config

_register()
```

### Step 3: Real Example - annuity_income Domain

Here's how an `annuity_income` config would look:

```python
# configs/annuity_income.py
"""Annuity Income Domain Configuration."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Type
from .base import DomainComparisonConfig

if TYPE_CHECKING:
    import pandas as pd


class AnnuityIncomeConfig(DomainComparisonConfig):
    """Configuration for annuity_income (收入明细) domain comparison."""

    @property
    def domain_name(self) -> str:
        return "annuity_income"

    @property
    def sheet_name(self) -> str:
        return "收入明细"

    @property
    def numeric_fields(self) -> List[str]:
        return [
            "保费收入",
            "首年保费",
            "续期保费",
            "趸交保费",
        ]

    @property
    def derived_fields(self) -> List[str]:
        return [
            "月度",
            "机构代码",
            "产品代码",
        ]

    def get_legacy_cleaner(self) -> Type:
        from annuity_hub.data_handler.data_cleaner import AnnuityIncomeCleaner
        return AnnuityIncomeCleaner

    def build_new_pipeline(
        self,
        excel_path: str,
        sheet_name: str,
        row_limit: Optional[int],
        enable_enrichment: bool,
        sync_lookup_budget: int,
    ) -> "pd.DataFrame":
        import pandas as pd
        from work_data_hub.domain.annuity_income.pipeline_builder import (
            build_bronze_to_silver_pipeline,
        )
        from work_data_hub.domain.pipelines.types import PipelineContext

        raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)
        if row_limit and row_limit > 0:
            raw_df = raw_df.head(row_limit)

        pipeline = build_bronze_to_silver_pipeline()
        context = PipelineContext(
            pipeline_name="cleaner_comparison",
            execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(timezone.utc),
            config={},
            domain=self.domain_name,
            run_id="compare",
            extra={},
        )
        return pipeline.execute(raw_df.copy(), context)


def _register():
    from . import DOMAIN_CONFIGS
    DOMAIN_CONFIGS["annuity_income"] = AnnuityIncomeConfig

_register()
```

### Step 4: Register Config

Add import to `configs/__init__.py`:

```python
def _load_domain_configs() -> None:
    """Load all domain configuration modules to trigger registration."""
    try:
        from . import annuity_performance  # noqa: F401
    except ImportError:
        pass

    # Add new domain here:
    try:
        from . import annuity_income  # noqa: F401
    except ImportError:
        pass

_load_domain_configs()
```

### Step 5: Test Your Config

```powershell
# 1. Verify config is registered
$env:PYTHONPATH='src'; uv run python scripts/validation/CLI/cleaner_compare.py --help
# Should show: --domain {annuity_performance,annuity_income}

# 2. Quick test (10 rows)
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_income --month 202510 --limit 10 --debug

# 3. New Pipeline only (skip Legacy dependencies)
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_income --month 202510 --limit 10 --new-only --debug

# 4. Full comparison
$env:PYTHONPATH='src'; uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py `
    --domain annuity_income --month 202510 --limit 100 --debug --export --enrichment
```

### Common Pitfalls & Solutions

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` for Legacy cleaner | Use `--new-only` mode, or ensure Legacy dependencies are installed |
| `KeyError: '<domain>'` | Ensure `_register()` is called at module bottom and config is imported in `__init__.py` |
| Empty DataFrame from Legacy | Check Legacy cleaner's internal error handling; some cleaners silently return empty on error |
| Column name mismatch | Use `column_name_mapping` property to map Legacy → New column names |
| Date comparison fails | Dates are auto-normalized to ISO format; ensure both systems produce compatible formats |
| `--month` auto-discovery fails | Check `config/data_sources.yml` has correct pattern for your domain |

### Lazy Import Pattern

> [!IMPORTANT]
> Always use **lazy imports** in `get_legacy_cleaner()` and `build_new_pipeline()` to enable `--new-only` mode.

```python
# ❌ WRONG - Import at module level breaks --new-only
from annuity_hub.data_handler.data_cleaner import AnnuityIncomeCleaner

class AnnuityIncomeConfig(DomainComparisonConfig):
    def get_legacy_cleaner(self):
        return AnnuityIncomeCleaner  # Already imported, fails if Legacy not installed

# ✅ CORRECT - Lazy import inside method
class AnnuityIncomeConfig(DomainComparisonConfig):
    def get_legacy_cleaner(self):
        # Import only when this method is called
        from annuity_hub.data_handler.data_cleaner import AnnuityIncomeCleaner
        return AnnuityIncomeCleaner
```

### Implementation Time Estimate

| Task | Time |
|------|------|
| Identify field classifications | 10 min |
| Create config file (copy template) | 5 min |
| Customize field lists | 10 min |
| Implement `get_legacy_cleaner()` | 2 min |
| Implement `build_new_pipeline()` | 15-30 min |
| Testing & debugging | 15 min |
| **Total** | **~1 hour** |



## Comparison Categories

### Numeric Fields (Zero Tolerance)

Fields compared with `Decimal` precision. `NULL` and `0` are treated as equivalent.

### Derived Fields

Fields derived from mappings or transformations.

### Upgrade Fields (company_id)

Classifications for `company_id` differences:

| Classification | Meaning |
|----------------|---------|
| `upgrade_eqc_resolved` | ✅ New resolved, Legacy was empty/invalid |
| `regression_missing_resolution` | ❌ Legacy had ID, New returns temp ID |
| `regression_company_id_mismatch` | ❌ Both numeric but different |
| `needs_review` | ❓ Manual review required |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No critical issues |
| `1` | Critical issues found |

## Artifact Equivalence Rules

When comparing results from different runs:

1. **With `--run-id`**: Output directories and filenames are deterministic
2. **Without `--run-id`**: Ignore the run directory name (timestamp-based) and the "Generated" timestamp line in markdown summaries

All other content (diff counts, classifications, examples) should be identical for equivalent runs.

## Legacy Script Migration

The following scripts have been deprecated:

| Old Script | New Equivalent |
|------------|----------------|
| `guimo_iter_cleaner_compare.py` | `cleaner_compare.py --domain annuity_performance` |
| `guimo_iter_config.py` | `domain_config.py` + `configs/annuity_performance.py` |
| `guimo_iter_report_generator.py` | `report_generator.py` |

## Resolution Priority (New Pipeline)

1. **YAML Overrides** (5 levels: plan → account → hardcode → name → account_name)
2. **Database Cache** (`enterprise.enrichment_index`)
3. **Existing Column Passthrough** (numeric values only)
4. **EQC Sync Lookup** (budgeted)
5. **Default Fallback** (`600866980` for empty customer_name)
6. **Temporary ID Generation** (HMAC-SHA1)

## Change Log

| Date | Change |
|------|--------|
| 2025-12-18 | **Story 6.2-P12**: Refactored to config-driven, domain-agnostic architecture. Added `--domain` (required) and `--run-id` arguments. Renamed scripts. |
| 2025-12-18 | Added deterministic export support via `--run-id` |
