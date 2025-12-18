"""
Report generation utilities for Cleaner Comparison.

Provides functions to generate CSV and Markdown reports from comparison results.
This is a domain-agnostic version that works with any configured domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from domain_config import (
    ARTIFACTS_DIR,
    DEBUG_SNAPSHOTS_SUBDIR,
    MAX_EXAMPLES_PER_DIFF,
    REPORT_DATE_FORMAT,
    REPORT_PREFIX,
    SUMMARY_PREFIX,
)


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
        """Check if there are any critical issues that should fail the run."""
        critical_numeric_types = {
            "CRITICAL_NUMERIC_MISMATCH",
            "COLUMN_MISSING",
            "INVALID_NUMERIC_VALUE",
            "ROW_COUNT_MISMATCH",
        }
        return any(d.diff_type in critical_numeric_types for d in self.numeric_diffs)

    @property
    def upgrade_classification_summary(self) -> Dict[str, int]:
        """Summarize upgrade differences by classification."""
        from collections import Counter

        return dict(Counter(d.classification for d in self.upgrade_diffs))


# =============================================================================
# Console Report Printer
# =============================================================================


def print_report(report: ComparisonReport) -> None:
    """Print comparison report to console."""
    print("\n" + "=" * 70)
    print("CLEANER COMPARISON REPORT")
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
        critical_numeric_types = {
            "CRITICAL_NUMERIC_MISMATCH",
            "COLUMN_MISSING",
            "INVALID_NUMERIC_VALUE",
            "ROW_COUNT_MISMATCH",
        }
        for diff in report.numeric_diffs:
            status = "❌ CRITICAL" if diff.diff_type in critical_numeric_types else "⚠️"
            print(f"   {status} {diff.field}: {diff.diff_type}")
            if diff.diff_count:
                print(f"      Differences: {diff.diff_count} rows")
            for ex in diff.examples[:3]:
                if diff.diff_type == "ROW_COUNT_MISMATCH":
                    print(
                        f"      Legacy rows={ex.get('legacy_row_count')} "
                        f"New rows={ex.get('new_row_count')}"
                    )
                elif diff.diff_type == "COLUMN_MISSING":
                    print(
                        f"      Columns: legacy_has={ex.get('legacy_has_column')} "
                        f"new_has={ex.get('new_has_column')} "
                        f"(new name: {ex.get('new_column_name')})"
                    )
                elif diff.diff_type == "INVALID_NUMERIC_VALUE":
                    print(
                        f"      Row {ex.get('row')}: "
                        f"LegacyRaw={ex.get('legacy_raw')} → NewRaw={ex.get('new_raw')}"
                    )
                elif "legacy_value" in ex:
                    print(
                        f"      Row {ex['row']}: "
                        f"Legacy={ex['legacy_value']} → New={ex['new_value']}"
                    )
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
# File Report Generators
# =============================================================================


def generate_csv_report(
    report: ComparisonReport,
    output_path: Optional[Path] = None,
    run_id: Optional[str] = None,
) -> Path:
    """
    Generate detailed CSV report of all differences.

    Args:
        report: ComparisonReport object
        output_path: Optional custom output path
        run_id: Optional run ID for directory naming

    Returns:
        Path to generated CSV file
    """
    if output_path is None:
        if run_id is None:
            run_id = datetime.now(timezone.utc).strftime(REPORT_DATE_FORMAT)
        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        output_path = run_dir / f"{REPORT_PREFIX}_{run_id}.csv"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    # Add numeric differences
    for diff in report.numeric_diffs:
        for ex in diff.examples:
            legacy_value = ex.get("legacy_value", "")
            new_value = ex.get("new_value", "")
            if diff.diff_type == "INVALID_NUMERIC_VALUE":
                legacy_value = ex.get("legacy_raw", legacy_value)
                new_value = ex.get("new_raw", new_value)
            elif diff.diff_type == "ROW_COUNT_MISMATCH":
                legacy_value = ex.get("legacy_row_count", legacy_value)
                new_value = ex.get("new_row_count", new_value)
            elif diff.diff_type == "COLUMN_MISSING":
                legacy_value = ex.get("legacy_has_column", legacy_value)
                new_value = ex.get("new_has_column", new_value)

            rows.append(
                {
                    "category": "NUMERIC",
                    "field": diff.field,
                    "diff_type": diff.diff_type,
                    "row": ex.get("row", ""),
                    "legacy_value": legacy_value,
                    "new_value": new_value,
                    "classification": "",
                    "notes": f"Total: {diff.diff_count} differences",
                }
            )

    # Add derived differences
    for diff in report.derived_diffs:
        for ex in diff.examples:
            rows.append(
                {
                    "category": "DERIVED",
                    "field": diff.field,
                    "diff_type": "DERIVED_MISMATCH",
                    "row": ex.get("row", ""),
                    "legacy_value": ex.get("legacy_value", ""),
                    "new_value": ex.get("new_value", ""),
                    "classification": "",
                    "notes": f"Total: {diff.diff_count} differences",
                }
            )

    # Add upgrade differences
    for diff in report.upgrade_diffs:
        rows.append(
            {
                "category": "UPGRADE",
                "field": diff.field,
                "diff_type": "UPGRADE_DIFF",
                "row": diff.row,
                "legacy_value": diff.legacy_value,
                "new_value": diff.new_value,
                "classification": diff.classification,
                "notes": "",
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    return output_path


def generate_markdown_summary(
    report: ComparisonReport,
    output_path: Optional[Path] = None,
    run_id: Optional[str] = None,
) -> Path:
    """
    Generate Markdown summary report.

    Args:
        report: ComparisonReport object
        output_path: Optional custom output path
        run_id: Optional run ID for directory naming

    Returns:
        Path to generated Markdown file
    """
    if output_path is None:
        if run_id is None:
            run_id = datetime.now(timezone.utc).strftime(REPORT_DATE_FORMAT)
        run_dir = ARTIFACTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        output_path = run_dir / f"{SUMMARY_PREFIX}_{run_id}.md"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = [
        "# Cleaner Comparison Summary",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Input:** `{report.excel_path}`",
        f"**Sheet:** {report.sheet_name}",
        f"**Row Limit:** {report.row_limit}",
        f"**Execution Time:** {report.execution_time_ms}ms",
        "",
        "---",
        "",
        "## Output Dimensions",
        "",
        "| System | Rows | Columns |",
        "|--------|------|---------|",
        f"| Legacy | {report.legacy_row_count} | {report.legacy_column_count} |",
        f"| New Pipeline | {report.new_row_count} | {report.new_column_count} |",
        "",
        "---",
        "",
    ]

    # Numeric fields section
    lines.extend(
        [
            "## Numeric Fields (Zero Tolerance)",
            "",
        ]
    )

    if report.numeric_diffs:
        lines.append("| Field | Status | Count |")
        lines.append("|-------|--------|-------|")
        for diff in report.numeric_diffs:
            status = "❌ CRITICAL" if diff.diff_type == "CRITICAL_NUMERIC_MISMATCH" else "⚠️ Warning"
            lines.append(f"| {diff.field} | {status} | {diff.diff_count} |")
    else:
        lines.append("✅ **All numeric fields match exactly**")

    lines.extend(["", "---", ""])

    # Derived fields section
    lines.extend(
        [
            "## Derived Fields",
            "",
        ]
    )

    if report.derived_diffs:
        lines.append("| Field | Differences |")
        lines.append("|-------|-------------|")
        for diff in report.derived_diffs:
            lines.append(f"| {diff.field} | {diff.diff_count} |")
    else:
        lines.append("✅ **All derived fields match**")

    lines.extend(["", "---", ""])

    # Upgrade fields section
    lines.extend(
        [
            "## Upgrade Fields Classification",
            "",
        ]
    )

    if report.upgrade_diffs:
        summary = report.upgrade_classification_summary
        lines.append("| Classification | Count |")
        lines.append("|----------------|-------|")
        for cls, count in sorted(summary.items()):
            emoji = "✅" if cls.startswith("upgrade") else "❌" if cls.startswith("regression") else "❓"
            lines.append(f"| {emoji} {cls} | {count} |")
    else:
        lines.append("✅ **No upgrade field differences**")

    lines.extend(["", "---", ""])

    # Overall result
    if report.has_critical_issues:
        lines.extend(
            [
                "## ❌ Result: CRITICAL ISSUES FOUND",
                "",
                "Must fix numeric field differences before proceeding.",
            ]
        )
    else:
        lines.extend(
            [
                "## ✅ Result: No Critical Issues",
                "",
                "Proceed to next iteration or increase sample size.",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path


# =============================================================================
# Debug Snapshot Utilities
# =============================================================================


def save_debug_snapshots(
    legacy_df: pd.DataFrame,
    new_df: pd.DataFrame,
    run_id: Optional[str] = None,
) -> Path:
    """
    Save DataFrames for debugging purposes.

    Args:
        legacy_df: DataFrame from Legacy cleaner
        new_df: DataFrame from New Pipeline
        run_id: Optional run ID (timestamp). If None, generates one.

    Returns:
        Path to the run directory containing snapshots
    """
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime(REPORT_DATE_FORMAT)

    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshots_dir = run_dir / DEBUG_SNAPSHOTS_SUBDIR
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    legacy_path = snapshots_dir / "legacy_output.csv"
    new_path = snapshots_dir / "new_pipeline_output.csv"

    legacy_df.to_csv(legacy_path, index=False, encoding="utf-8-sig")
    new_df.to_csv(new_path, index=False, encoding="utf-8-sig")

    print(f"📸 Debug snapshots saved to: {snapshots_dir}")
    print(f"   Legacy: {legacy_path.name}")
    print(f"   New:    {new_path.name}")

    return run_dir
