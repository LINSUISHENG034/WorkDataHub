# Annuity Performance Cleaner Comparison: Implementation Plan

**Version:** 3.3
**Date:** 2025-12-18
**Status:** Updated
**Domain:** `annuity_performance` (业务."规模明细")

---

## Executive Summary

This document outlines the implementation plan for validating the New Pipeline's data cleansing logic against the Legacy system for the `annuity_performance` domain. The approach focuses on **direct cleaner comparison** rather than database output comparison, eliminating join key matching complexity entirely.

## Senior Developer Review (AI)

**Date:** 2025-12-17  
**Outcome:** done  
**Notes:** Document and scripts aligned on critical checks (row count mismatch, invalid numerics, missing numeric columns) and artifacts layout.

### Key Strategy Shift

| Aspect | Original Approach | New Approach |
|--------|-------------------|--------------|
| Comparison Target | Database records (Legacy vs New) | Cleaner outputs (same input → both cleaners) |
| Join Key Requirement | Required (complex, error-prone) | **Not required** (row-by-row alignment) |
| Difference Traceability | Difficult (multiple causes) | Direct (specific cleansing step) |
| Iteration Speed | Slow (full ETL cycles) | Fast (cleaner functions only) |

---

## 1. Alignment Principles

### 1.1 Numeric Fields: Zero Tolerance

Since this domain is a **data cleansing and ingestion process** (not calculation), numeric values must be **exactly preserved** from source to output.

**Fields:**
- `期初资产规模` (Opening Asset Scale)
- `期末资产规模` (Closing Asset Scale)
- `供款` (Contribution)
- `流失(含待遇支付)` / `流失_含待遇支付` (Outflow including Benefits)
- `流失` (Outflow)
- `待遇支付` (Benefits Payment)

**Comparison Rules:**
- Use `Decimal` type for comparison (avoid floating-point errors)
- `NULL` and `0` are considered **equivalent** (not a difference)
- Any mismatch → **CRITICAL BUG**, must be fixed before proceeding

### 1.2 Derived Fields: Logic Alignment

These fields are computed from source data using mapping tables or transformation rules.

**Fields:**
- `月度` (Month) - Date parsing
- `机构代码` (Branch Code) - Mapped from `机构名称`
- `计划代码` (Plan Code) - Corrections + defaults
- `组合代码` (Portfolio Code) - F-prefix removal + defaults
- `产品线代码` (Product Line Code) - Mapped from `业务类型`

**Comparison Rules:**
- String comparison after normalization
- Differences must be traced to specific mapping/rule differences
- May be acceptable if intentional improvement

### 1.3 Upgrade Fields: Classification Required

These fields have **intentional enhancements** in the New Pipeline.

**Fields:**
- `company_id` - New Pipeline adds EQC API resolution, caching
- `客户名称` (Customer Name) - New Pipeline may have enhanced name cleansing

**Comparison Rules:**
- Differences must be **classified** before acceptance:
  - `upgrade_*` - Intentional improvement, acceptable
  - `regression_*` - Bug, must be fixed
  - `needs_review` - Requires manual business review

---

## 2. Source Code References

### 2.1 Legacy Cleaner

**File:** `legacy/annuity_hub/data_handler/data_cleaner.py`
**Class:** `AnnuityPerformanceCleaner` (lines 194-293)

**Processing Steps:**
1. Load Excel data (`_load_data`)
2. Column renaming (机构→机构名称, 计划号→计划代码)
3. Branch code mapping (`COMPANY_BRANCH_MAPPING`)
4. Date parsing (`parse_to_standard_date`)
5. Plan code corrections (1P0290→P0290) + defaults (AN001/AN002)
6. Portfolio code cleansing (F-prefix removal) + defaults
7. Product line code mapping
8. Customer name cleansing (`clean_company_name`) + preserve original as `年金账户名`
9. Company ID resolution (5-step cascade):
   - Step 1: `计划代码` → `COMPANY_ID1_MAPPING`
   - Step 2: `集团企业客户号` → `COMPANY_ID2_MAPPING`
   - Step 3: Special case with default `600866980`
   - Step 4: `客户名称` → `COMPANY_ID4_MAPPING`
   - Step 5: `年金账户名` → `COMPANY_ID5_MAPPING`
10. Drop invalid columns

### 2.2 New Pipeline

**File:** `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`
**Function:** `build_bronze_to_silver_pipeline` (lines 194-289)

**Processing Steps:**
1. `MappingStep` - Column renaming
2. `CalculationStep` - Preserve `年金账户名 = 客户名称`
3. `ReplacementStep` - Plan code corrections
4. `CalculationStep` - Plan code defaults
5. `CalculationStep` - Branch code mapping
6. `CalculationStep` - Product line code mapping
7. `CalculationStep` - Date parsing (`parse_chinese_date`)
8. `CalculationStep` - Portfolio code defaults
9. `CalculationStep` - Clean `集团企业客户号` (lstrip "C")
10. `CalculationStep` - Derive `年金账户号`
11. `CleansingStep` - Domain-specific cleansing rules
12. `CompanyIdResolutionStep` - New architecture company ID resolution
13. `DropStep` - Remove legacy columns

---

## 3. Deliverables

### 3.1 Directory Structure

```
scripts/validation/CLI/
├── guimo_iter_cleaner_compare.py      # Core comparison script
├── guimo_iter_report_generator.py     # Report generation utilities
├── guimo_iter_config.py               # Configuration constants
├── _artifacts/                        # Output directory
│   └── YYYYMMDD_HHMMSS/                # Per-run directory (UTC timestamp)
│       ├── diff_report_YYYYMMDD_HHMMSS.csv
│       ├── diff_summary_YYYYMMDD_HHMMSS.md
│       └── debug_snapshots/            # Intermediate DataFrames for debugging
│           ├── legacy_output.csv
│           └── new_pipeline_output.csv
└── annuity-performance-cleaner-comparison-plan.md  # This document
```

### 3.2 Core Script: `guimo_iter_cleaner_compare.py`

**Note:** The following code block is an illustrative snapshot. The source of truth is the repository file `scripts/validation/CLI/guimo_iter_cleaner_compare.py`.

```python
"""
Annuity Performance Cleaner Comparison Script

Compares Legacy AnnuityPerformanceCleaner output against New Pipeline output
using the same input data, enabling row-by-row comparison without join keys.

Usage:
    python guimo_iter_cleaner_compare.py <excel_path> [--sheet SHEET] [--limit N]

Example:
    python guimo_iter_cleaner_compare.py "data/202412_annuity.xlsx" --limit 100
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Add legacy path for imports
LEGACY_PATH = Path(__file__).parent.parent.parent.parent / "legacy"
sys.path.insert(0, str(LEGACY_PATH))


# =============================================================================
# Configuration
# =============================================================================

NUMERIC_FIELDS = [
    "期初资产规模",
    "期末资产规模",
    "供款",
    "流失(含待遇支付)",  # Legacy column name
    "流失",
    "待遇支付",
]

# Column name mapping for comparison (Legacy → New)
COLUMN_NAME_MAPPING = {
    "流失(含待遇支付)": "流失_含待遇支付",
}

DERIVED_FIELDS = [
    "月度",
    "机构代码",
    "计划代码",
    "组合代码",
    "产品线代码",
]

UPGRADE_FIELDS = [
    "company_id",
    "客户名称",
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class NumericDiff:
    """Represents a numeric field difference."""
    field: str
    diff_type: str  # CRITICAL_NUMERIC_MISMATCH, COLUMN_MISSING
    diff_count: int = 0
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DerivedDiff:
    """Represents a derived field difference."""
    field: str
    diff_count: int
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class UpgradeDiff:
    """Represents an upgrade field difference with classification."""
    field: str
    row: int
    legacy_value: str
    new_value: str
    classification: str  # upgrade_eqc_resolved, regression_*, needs_review


@dataclass
class ComparisonReport:
    """Complete comparison report."""
    excel_path: str
    sheet_name: str
    row_limit: int
    legacy_row_count: int
    new_row_count: int
    legacy_column_count: int
    new_column_count: int
    numeric_diffs: List[NumericDiff] = field(default_factory=list)
    derived_diffs: List[DerivedDiff] = field(default_factory=list)
    upgrade_diffs: List[UpgradeDiff] = field(default_factory=list)
    execution_time_ms: int = 0

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical (numeric) differences."""
        return any(
            d.diff_type == "CRITICAL_NUMERIC_MISMATCH"
            for d in self.numeric_diffs
        )

    @property
    def upgrade_classification_summary(self) -> Dict[str, int]:
        """Summarize upgrade differences by classification."""
        return dict(Counter(d.classification for d in self.upgrade_diffs))


# =============================================================================
# Cleaner Executors
# =============================================================================

def run_legacy_cleaner(
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Execute Legacy AnnuityPerformanceCleaner.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration

    Returns:
        Cleaned DataFrame from Legacy cleaner
    """
    from annuity_hub.data_handler.data_cleaner import AnnuityPerformanceCleaner

    cleaner = AnnuityPerformanceCleaner(excel_path, sheet_name=sheet_name)
    df = cleaner.clean()

    if row_limit and row_limit > 0:
        df = df.head(row_limit)

    return df


def run_new_pipeline(
    excel_path: str,
    sheet_name: str,
    row_limit: Optional[int] = None,
    enable_enrichment: bool = False,
) -> pd.DataFrame:
    """
    Execute New Pipeline cleaner (without DB operations).

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Optional row limit for iteration
        enable_enrichment: Whether to enable EQC enrichment service

    Returns:
        Cleaned DataFrame from New Pipeline
    """
    from work_data_hub.domain.annuity_performance.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )
    from work_data_hub.domain.pipelines.types import PipelineContext

    # Load raw data (same as Legacy cleaner input)
    raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)

    if row_limit and row_limit > 0:
        raw_df = raw_df.head(row_limit)

    # Build pipeline without enrichment service (pure cleansing comparison)
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=None,  # Disable EQC for pure cleansing comparison
        sync_lookup_budget=0,
    )

    # Create minimal context
    context = PipelineContext(
        pipeline_name="cleaner_comparison",
        execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={},
        domain="annuity_performance",
        run_id="compare",
        extra={},
    )

    return pipeline.execute(raw_df.copy(), context)


# =============================================================================
# Comparison Functions
# =============================================================================

def safe_to_decimal(value: Any) -> Decimal:
    """
    Safely convert value to Decimal, treating NULL/empty as 0.

    Args:
        value: Value to convert

    Returns:
        Decimal representation (0 for NULL/empty/invalid)
    """
    if pd.isna(value):
        return Decimal(0)

    str_val = str(value).strip()
    if not str_val:
        return Decimal(0)

    try:
        return Decimal(str_val)
    except InvalidOperation:
        return Decimal(0)


def compare_numeric_fields(
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[NumericDiff]:
    """
    Compare numeric fields with zero tolerance.

    NULL and 0 are treated as equivalent (not a difference).
    Uses Decimal for precise comparison.

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of numeric differences found
    """
    diffs: List[NumericDiff] = []

    for legacy_col in NUMERIC_FIELDS:
        # Handle column name mapping
        new_col = COLUMN_NAME_MAPPING.get(legacy_col, legacy_col)

        # Check column existence
        legacy_has = legacy_col in legacy_df.columns
        new_has = new_col in new_df.columns

        if not legacy_has or not new_has:
            diffs.append(NumericDiff(
                field=legacy_col,
                diff_type="COLUMN_MISSING",
                diff_count=0,
                examples=[{
                    "legacy_has_column": legacy_has,
                    "new_has_column": new_has,
                    "new_column_name": new_col,
                }],
            ))
            continue

        # Convert to Decimal for comparison
        legacy_vals = legacy_df[legacy_col].apply(safe_to_decimal)
        new_vals = new_df[new_col].apply(safe_to_decimal)

        # Find differences
        min_len = min(len(legacy_vals), len(new_vals))
        diff_indices = []

        for idx in range(min_len):
            if legacy_vals.iloc[idx] != new_vals.iloc[idx]:
                diff_indices.append(idx)

        if diff_indices:
            examples = [
                {
                    "row": idx,
                    "legacy_value": str(legacy_vals.iloc[idx]),
                    "new_value": str(new_vals.iloc[idx]),
                }
                for idx in diff_indices[:5]  # First 5 examples
            ]

            diffs.append(NumericDiff(
                field=legacy_col,
                diff_type="CRITICAL_NUMERIC_MISMATCH",
                diff_count=len(diff_indices),
                examples=examples,
            ))

    return diffs


def compare_derived_fields(
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[DerivedDiff]:
    """
    Compare derived fields (mappings, transformations).

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of derived field differences found
    """
    diffs: List[DerivedDiff] = []

    for col in DERIVED_FIELDS:
        if col not in legacy_df.columns or col not in new_df.columns:
            continue

        # Normalize to string for comparison
        legacy_vals = legacy_df[col].astype(str).fillna("").str.strip()
        new_vals = new_df[col].astype(str).fillna("").str.strip()

        # Find differences
        min_len = min(len(legacy_vals), len(new_vals))
        diff_indices = []

        for idx in range(min_len):
            if legacy_vals.iloc[idx] != new_vals.iloc[idx]:
                diff_indices.append(idx)

        if diff_indices:
            examples = [
                {
                    "row": idx,
                    "legacy_value": legacy_vals.iloc[idx],
                    "new_value": new_vals.iloc[idx],
                }
                for idx in diff_indices[:5]
            ]

            diffs.append(DerivedDiff(
                field=col,
                diff_count=len(diff_indices),
                examples=examples,
            ))

    return diffs


def classify_company_id_diff(legacy_val: str, new_val: str) -> str:
    """
    Classify company_id difference.

    Classifications:
    - upgrade_eqc_resolved: New resolved to numeric, Legacy was temp/empty
    - regression_missing_resolution: Legacy was numeric, New is temp ID
    - regression_company_id_mismatch: Both numeric but different
    - needs_review: Cannot be automatically classified

    Args:
        legacy_val: Legacy company_id value
        new_val: New Pipeline company_id value

    Returns:
        Classification string
    """
    legacy_is_numeric = legacy_val.isdigit() and len(legacy_val) > 1
    new_is_numeric = new_val.isdigit() and len(new_val) > 1
    legacy_is_temp = legacy_val.startswith("IN") or legacy_val in ("", "N", "None")
    new_is_temp = new_val.startswith("IN")

    if new_is_numeric and (legacy_is_temp or not legacy_is_numeric):
        return "upgrade_eqc_resolved"

    if legacy_is_numeric and new_is_temp:
        return "regression_missing_resolution"

    if legacy_is_numeric and new_is_numeric:
        return "regression_company_id_mismatch"

    return "needs_review"


def compare_upgrade_fields(
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> List[UpgradeDiff]:
    """
    Compare upgrade fields with classification.

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline

    Returns:
        List of upgrade field differences with classifications
    """
    diffs: List[UpgradeDiff] = []

    # Company ID comparison
    if "company_id" in legacy_df.columns and "company_id" in new_df.columns:
        min_len = min(len(legacy_df), len(new_df))

        for idx in range(min_len):
            legacy_val = str(legacy_df.iloc[idx].get("company_id", "") or "")
            new_val = str(new_df.iloc[idx].get("company_id", "") or "")

            if legacy_val != new_val:
                classification = classify_company_id_diff(legacy_val, new_val)
                diffs.append(UpgradeDiff(
                    field="company_id",
                    row=idx,
                    legacy_value=legacy_val,
                    new_value=new_val,
                    classification=classification,
                ))

    # Customer name comparison (simplified - just flag differences)
    if "客户名称" in legacy_df.columns and "客户名称" in new_df.columns:
        min_len = min(len(legacy_df), len(new_df))

        for idx in range(min_len):
            legacy_val = str(legacy_df.iloc[idx].get("客户名称", "") or "")
            new_val = str(new_df.iloc[idx].get("客户名称", "") or "")

            if legacy_val != new_val:
                # Simple classification for customer name
                classification = "upgrade_name_cleaning" if new_val else "needs_review"
                diffs.append(UpgradeDiff(
                    field="客户名称",
                    row=idx,
                    legacy_value=legacy_val[:50],  # Truncate for readability
                    new_value=new_val[:50],
                    classification=classification,
                ))

    return diffs


# =============================================================================
# Main Comparison Function
# =============================================================================

def run_comparison(
    excel_path: str,
    sheet_name: str = "规模明细",
    row_limit: int = 100,
    enable_enrichment: bool = False,
) -> ComparisonReport:
    """
    Run full comparison between Legacy and New Pipeline cleaners.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name to process
        row_limit: Row limit for iteration (0 = no limit)
        enable_enrichment: Whether to enable EQC enrichment

    Returns:
        ComparisonReport with all differences
    """
    import time
    start_time = time.perf_counter()

    # Run both cleaners
    legacy_df = run_legacy_cleaner(excel_path, sheet_name, row_limit)
    new_df = run_new_pipeline(excel_path, sheet_name, row_limit, enable_enrichment)

    # Run comparisons
    numeric_diffs = compare_numeric_fields(legacy_df, new_df)
    derived_diffs = compare_derived_fields(legacy_df, new_df)
    upgrade_diffs = compare_upgrade_fields(legacy_df, new_df)

    execution_time_ms = int((time.perf_counter() - start_time) * 1000)

    return ComparisonReport(
        excel_path=excel_path,
        sheet_name=sheet_name,
        row_limit=row_limit,
        legacy_row_count=len(legacy_df),
        new_row_count=len(new_df),
        legacy_column_count=len(legacy_df.columns),
        new_column_count=len(new_df.columns),
        numeric_diffs=numeric_diffs,
        derived_diffs=derived_diffs,
        upgrade_diffs=upgrade_diffs,
        execution_time_ms=execution_time_ms,
    )


def print_report(report: ComparisonReport) -> None:
    """Print comparison report to console."""
    print("\n" + "=" * 70)
    print("ANNUITY PERFORMANCE CLEANER COMPARISON REPORT")
    print("=" * 70)

    print(f"\n📁 Input: {report.excel_path}")
    print(f"   Sheet: {report.sheet_name}")
    print(f"   Row Limit: {report.row_limit}")
    print(f"   Execution Time: {report.execution_time_ms}ms")

    print(f"\n📊 Output Dimensions:")
    print(f"   Legacy: {report.legacy_row_count} rows × {report.legacy_column_count} cols")
    print(f"   New:    {report.new_row_count} rows × {report.new_column_count} cols")

    # Numeric fields
    print(f"\n{'─' * 70}")
    print("📐 NUMERIC FIELDS (Zero Tolerance)")
    print(f"{'─' * 70}")

    if report.numeric_diffs:
        for diff in report.numeric_diffs:
            status = "❌ CRITICAL" if diff.diff_type == "CRITICAL_NUMERIC_MISMATCH" else "⚠️"
            print(f"   {status} {diff.field}: {diff.diff_type}")
            if diff.diff_count:
                print(f"      Differences: {diff.diff_count} rows")
            for ex in diff.examples[:3]:
                if "legacy_value" in ex:
                    print(f"      Row {ex['row']}: Legacy={ex['legacy_value']} → New={ex['new_value']}")
    else:
        print("   ✅ All numeric fields match exactly")

    # Derived fields
    print(f"\n{'─' * 70}")
    print("🔧 DERIVED FIELDS")
    print(f"{'─' * 70}")

    if report.derived_diffs:
        for diff in report.derived_diffs:
            print(f"   ⚠️ {diff.field}: {diff.diff_count} differences")
            for ex in diff.examples[:2]:
                print(f"      Row {ex['row']}: '{ex['legacy_value']}' → '{ex['new_value']}'")
    else:
        print("   ✅ All derived fields match")

    # Upgrade fields
    print(f"\n{'─' * 70}")
    print("🚀 UPGRADE FIELDS (Classification)")
    print(f"{'─' * 70}")

    if report.upgrade_diffs:
        summary = report.upgrade_classification_summary
        print("   Classification Summary:")
        for cls, count in sorted(summary.items()):
            emoji = "✅" if cls.startswith("upgrade") else "❌" if cls.startswith("regression") else "❓"
            print(f"      {emoji} {cls}: {count}")
    else:
        print("   ✅ No upgrade field differences")

    # Overall status
    print(f"\n{'=' * 70}")
    if report.has_critical_issues:
        print("❌ RESULT: CRITICAL ISSUES FOUND - Must fix numeric field differences")
    else:
        print("✅ RESULT: No critical issues - Proceed to next iteration")
    print("=" * 70 + "\n")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compare Legacy vs New Pipeline cleaners for annuity_performance"
    )
    parser.add_argument(
        "excel_path",
        help="Path to Excel file containing source data",
    )
    parser.add_argument(
        "--sheet",
        default="规模明细",
        help="Sheet name to process (default: 规模明细)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Row limit for iteration (default: 100, 0 = no limit)",
    )
    parser.add_argument(
        "--enrichment",
        action="store_true",
        help="Enable EQC enrichment service (default: disabled)",
    )

    args = parser.parse_args()

    report = run_comparison(
        excel_path=args.excel_path,
        sheet_name=args.sheet,
        row_limit=args.limit,
        enable_enrichment=args.enrichment,
    )

    print_report(report)

    # Exit with error code if critical issues found
    sys.exit(1 if report.has_critical_issues else 0)


if __name__ == "__main__":
    main()
```

---

## 4. Iteration Workflow

### 4.1 Phase 1: Numeric Field Alignment (Critical Path)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: Select Source Excel File                                       │
│  → Use recent monthly data (e.g., 202412_annuity.xlsx)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2: Run Comparison (row_limit=100)                                 │
│  → python guimo_iter_cleaner_compare.py <excel_path> --limit 100        │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3: Check Numeric Fields                                           │
│  → CRITICAL_NUMERIC_MISMATCH found?                                     │
│     YES → Investigate root cause, fix, return to Step 2                 │
│     NO  → Proceed to Phase 2                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Phase 2: Derived Field Alignment

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 4: Review Derived Field Differences                               │
│  → Trace each difference to specific mapping/rule                       │
│  → Determine if intentional improvement or bug                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 5: Fix Regressions (if any)                                       │
│  → Update mapping tables or transformation logic                        │
│  → Return to Step 2 to verify fix                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Phase 3: Upgrade Field Classification

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 6: Review Upgrade Field Classifications                           │
│  → upgrade_*: Document and accept                                       │
│  → regression_*: Must fix                                               │
│  → needs_review: Escalate for business decision                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 7: Expand Sample Size                                             │
│  → 100 → 500 → 1000 → Full dataset                                      │
│  → Verify fixes hold at larger scale                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Completion Criteria

### 5.1 Phase 1 Exit Criteria (Numeric Alignment)

| Metric | Target | Description |
|--------|--------|-------------|
| Numeric field differences | **= 0** | Zero tolerance for any numeric mismatch |
| Row count alignment | 100% | Both cleaners must output same row count |

### 5.2 Phase 2 Exit Criteria (Derived Alignment)

| Metric | Target | Description |
|--------|--------|-------------|
| Derived field differences | 0 or documented | All differences must be explained |
| Unexplained differences | = 0 | No "mystery" differences allowed |

### 5.3 Phase 3 Exit Criteria (Upgrade Classification)

| Metric | Target | Description |
|--------|--------|-------------|
| `regression_*` count | = 0 | All regressions must be fixed |
| `needs_review` count | Minimized | Business review completed for remaining |
| `upgrade_*` count | Documented | All improvements documented in changelog |

### 5.4 Final Validation

| Metric | Target | Description |
|--------|--------|-------------|
| Sample size | Full dataset | All criteria met on complete data |
| Documentation | Complete | All differences documented with classification |

---

## 6. Known Differences and Expected Behaviors

### 6.1 Column Name Differences

| Legacy Column | New Pipeline Column | Notes |
|---------------|---------------------|-------|
| `流失(含待遇支付)` | `流失_含待遇支付` | Parentheses vs underscore |

### 6.2 Date Parsing Differences

| Aspect | Legacy | New Pipeline |
|--------|--------|--------------|
| Parser function | `parse_to_standard_date` | `parse_chinese_date` |
| Output format | Date object | Date object |
| Edge cases | TBD | TBD |

### 6.3 Company ID Resolution Differences

| Aspect | Legacy | New Pipeline |
|--------|--------|--------------|
| Resolution steps | 5-step cascade with static mappings | `CompanyIdResolver` with 6-step dynamic strategies |
| EQC integration | None | Optional (via `enrichment_service`) |
| Temp ID format | N/A (uses static mappings) | `IN{hash}` format |
| Caching | None | `enrichment_index` table |
| Default fallback | `600866980` for empty customer_name | Same (Step 4.5) |
| Alphanumeric IDs | Supports (e.g., `602671512X`) | Supports (e.g., `602671512X`) |

---

## 7. Troubleshooting Guide

### 7.1 Common Issues

#### Import Errors

```
ModuleNotFoundError: No module named 'annuity_hub'
```

**Solution:** Ensure legacy path is correctly added to `sys.path`:
```python
LEGACY_PATH = Path(__file__).parent.parent.parent.parent / "legacy"
sys.path.insert(0, str(LEGACY_PATH))
```

#### Row Count Mismatch

If Legacy and New Pipeline produce different row counts:
1. Check if either cleaner drops rows during processing
2. Verify both are reading the same sheet
3. Check for filtering logic differences

#### Decimal Conversion Errors

If numeric comparison fails with conversion errors:
1. Check for non-numeric values in numeric columns
2. Verify source data encoding
3. Treat invalid numerics as **CRITICAL** (fix the source or cleaner; do not silently coerce to 0)

### 7.2 Debug Mode

To save intermediate DataFrames for debugging, use `--debug`.
This writes snapshots under `_artifacts/<run_id>/debug_snapshots/`.

---

## 8. References

### 8.1 Related Documents

- Sprint change proposal: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-api-full-coverage.md`
- EQC validation reference: `scripts/validation/EQC/`

### 8.2 Source Code

- Legacy cleaner: `legacy/annuity_hub/data_handler/data_cleaner.py`
- New Pipeline builder: `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`
- New Pipeline service: `src/work_data_hub/domain/annuity_performance/service.py`

---

---

## 9. Appendix A: EQC Troubleshooting Guide

This appendix consolidates troubleshooting experience for EQC (Enterprise Query Client) integration issues.

### 9.1 Token Validation

#### Quick Token Check Command

```powershell
$env:PYTHONPATH='src'
uv run --env-file .wdh_env python -c "
from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token
from work_data_hub.config.settings import get_settings
s=get_settings()
print(validate_eqc_token(s.eqc_token, s.eqc_base_url))
"
```

**Expected output:** `True` if token is valid, `False` otherwise.

#### Full CLI Token Validation

```powershell
$env:PYTHONPATH='src'
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202510 \
  --enrichment-enabled \
  --debug
```

**Key log indicators:**
- `🔐 Validating EQC token... ✅ Token valid` - Token is working
- `company_id_resolver.eqc_provider_completed` with `eqc_hits > 0` - EQC queries succeeded

### 9.2 Common EQC Issues

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| `EQC request forbidden` / 403 | Token invalid/expired | Refresh token via QR login |
| All `company_id` become `IN*` | `sync_lookup_budget=0` | Set `--enrichment-sync-budget > 0` |
| EQC hits but no DB persistence | Missing `api_fetched_at` update | Check `base_info` write logic |
| Same token not working | Settings cache | Restart process or clear `lru_cache` |

### 9.3 Temp ID Format Note

- **Generated format:** `IN_<base32>` (with underscore)
- **Stored format:** `IN<base32>` (underscore stripped during normalization)
- **Filter pattern:** Use `startswith('IN')` not `startswith('IN_')`

---

## 10. Appendix B: Database Verification Queries

### 10.1 EQC Persistence Verification

```sql
-- Check enrichment_index source distribution
SELECT source, COUNT(*)
FROM enterprise.enrichment_index
GROUP BY source
ORDER BY 2 DESC;

-- Check recent EQC API results
SELECT * FROM enterprise.enrichment_index
WHERE source = 'eqc_api'
ORDER BY updated_at DESC
LIMIT 10;

-- Check base_info raw data persistence
SELECT
    company_id,
    search_key_word,
    api_fetched_at,
    raw_data IS NOT NULL AS has_raw_data,
    raw_business_info IS NOT NULL AS has_raw_business_info,
    raw_biz_label IS NOT NULL AS has_raw_biz_label
FROM enterprise.base_info
ORDER BY api_fetched_at DESC
LIMIT 10;
```

### 10.2 Annuity Performance Data Verification

```sql
-- Check data loaded by month
SELECT COUNT(*), 月度
FROM business."规模明细"
GROUP BY 月度
ORDER BY 月度 DESC
LIMIT 5;

-- Check company_id resolution rate
SELECT
    COUNT(*) AS total,
    COUNT(CASE WHEN company_id NOT LIKE 'IN%' THEN 1 END) AS resolved,
    COUNT(CASE WHEN company_id LIKE 'IN%' THEN 1 END) AS temp_ids
FROM business."规模明细"
WHERE 月度 = '2025-10-01';

-- Check 年金账户号 population rate
SELECT
    COUNT(*) AS total,
    COUNT("年金账户号") AS with_account_number,
    ROUND(COUNT("年金账户号")::numeric / COUNT(*) * 100, 2) AS population_rate_pct
FROM business."规模明细"
WHERE 月度 = '2025-10-01';
```

### 10.3 Enrichment Index Completeness

```sql
-- Check lookup_type distribution
SELECT lookup_type, COUNT(*) AS cnt
FROM enterprise.enrichment_index
GROUP BY lookup_type
ORDER BY cnt DESC;

-- Check for invalid company_id values
SELECT lookup_key, company_id, lookup_type, source
FROM enterprise.enrichment_index
WHERE company_id IN ('N', '', 'None')
   OR company_id IS NULL
LIMIT 20;
```

---

## 11. Appendix C: CLI Quick Reference

### 11.1 ETL Commands

```bash
# Single domain - plan only (safe)
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202411

# Single domain - execute
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202411 \
    --execute

# With enrichment enabled
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202411 \
    --enrichment-enabled \
    --enrichment-sync-budget 50 \
    --execute

# Multi-domain batch
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance,annuity_income \
    --period 202411 \
    --execute

# All domains
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --all-domains \
    --period 202411 \
    --execute
```

### 11.2 Auth Commands

```bash
# Refresh EQC token via QR login
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli auth refresh

# With custom timeout
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli auth refresh --timeout 120
```

### 11.3 EQC Refresh Commands

```bash
# Check freshness status
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli eqc-refresh --status

# Dry run refresh
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli eqc-refresh \
    --refresh-stale \
    --dry-run
```

---

## 12. Appendix D: Edge Case Testing

### 12.1 Empty DataFrame Handling

```python
"""Test that pipeline handles empty input gracefully."""
import pandas as pd
from work_data_hub.domain.annuity_performance.pipeline_builder import build_bronze_to_silver_pipeline
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

empty_df = pd.DataFrame(columns=[
    '月度', '业务类型', '计划类型', '客户名称', '集团企业客户号'
])

pipeline = build_bronze_to_silver_pipeline(enrichment_service=None)
context = PipelineContext(
    pipeline_name='test_empty',
    execution_id='test-empty',
    timestamp=datetime.now(timezone.utc),
    config={},
    domain='annuity_performance',
)

result = pipeline.execute(empty_df, context)
assert len(result) == 0, "Empty input should produce empty output"
print("✅ Empty DataFrame handled correctly")
```

### 12.2 Missing Column Handling

```python
"""Test that pipeline handles missing columns gracefully."""
import pandas as pd
from work_data_hub.domain.annuity_performance.pipeline_builder import build_bronze_to_silver_pipeline
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

# Missing 集团企业客户号 column
df_missing = pd.DataFrame({
    '月度': ['202510'],
    '业务类型': ['企业年金受托'],
    '计划类型': ['集合计划'],
    '客户名称': ['测试公司'],
    # 集团企业客户号 intentionally missing
})

pipeline = build_bronze_to_silver_pipeline(enrichment_service=None)
context = PipelineContext(
    pipeline_name='test_missing',
    execution_id='test-missing',
    timestamp=datetime.now(timezone.utc),
    config={},
    domain='annuity_performance',
)

result = pipeline.execute(df_missing, context)
assert '年金账户号' in result.columns, "年金账户号 column should be created"
assert pd.isna(result['年金账户号'].iloc[0]), "年金账户号 should be None when source is missing"
print("✅ Missing column handled correctly")
```

### 12.3 Special Character Handling

```python
"""Test C-prefix removal and special characters in 集团企业客户号."""
test_cases = [
    ("C12345678", "12345678"),      # Normal C-prefix
    ("12345678", "12345678"),       # No prefix
    ("CC12345678", "C12345678"),    # Double C (only first removed)
    ("", None),                      # Empty string
    (None, None),                    # None value
]

for input_val, expected in test_cases:
    # Test logic here
    pass
```

---

## 13. Appendix E: Legacy Document Archive

The following documents have been consolidated into this guide and are archived for reference:

| Original Document | Content Integrated | Status |
|-------------------|-------------------|--------|
| `eqc-investigation-notes-20251217.md` | Appendix A (EQC Troubleshooting) | **Archived** |
| `manual-validation-guide-cli-architecture.md` | Appendix C (CLI Reference) | **Archived** |
| `manual-validation-guide-story-6.2-p11.md` | Appendix D (Edge Cases) | **Archived** |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.3 | 2025-12-18 | Added Step 4.5 (600866980 fallback for empty customer_name); relaxed alphanumeric company_id validation; updated resolution priority docs |
| 3.2 | 2025-12-17 | Synced key sections with current scripts; strengthened critical checks (row count mismatch, invalid numerics, missing numeric columns) and aligned artifacts layout. |
| 3.1 | 2024-12-17 | Added Appendix A-E consolidating legacy documents |
| 3.0 | 2024-12-17 | Complete rewrite: Cleaner comparison approach |
| 2.0 | 2024-12-17 | Added numeric zero-tolerance, iteration workflow |
| 1.0 | 2024-12-14 | Initial DB comparison approach |
