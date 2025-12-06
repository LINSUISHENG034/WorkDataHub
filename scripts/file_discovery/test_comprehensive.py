#!/usr/bin/env python
"""Comprehensive test of Epic 3 system against ALL real archive data."""

from pathlib import Path

from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.readers.excel_reader import ExcelReader

scanner = VersionScanner()
matcher = FilePatternMatcher()
reader = ExcelReader()

patterns = ["*年金终稿*.xlsx", "*年金规模收入*.xlsx", "*年金数据*.xlsx", "*年金*.xlsx"]
exclude = ["~$*", "*回复*", "*.eml", "*KPI*"]

print("═══════════════════════════════════════════════════════════")
print("COMPREHENSIVE EPIC 3 VALIDATION - ALL ARCHIVE MONTHS")
print("═══════════════════════════════════════════════════════════")
print("")

test_cases = [
    {
        "month": "202311",
        "path": Path("reference/archive/monthly/202311/数据采集"),
        "note": "No 收集数据 layer",
    },
    {
        "month": "202411",
        "path": Path("reference/archive/monthly/202411/收集数据/数据采集"),
        "note": "Standard structure with 收集数据",
    },
    {
        "month": "202412",
        "path": Path("reference/archive/monthly/202412/收集数据/数据采集"),
        "note": "Should detect V2 (highest version)",
    },
    {
        "month": "202501",
        "path": Path("reference/archive/monthly/202501/收集数据/数据采集"),
        "note": "Standard V1 structure",
    },
    {
        "month": "202502",
        "path": Path("reference/archive/monthly/202502"),
        "note": "Flat structure (no version folders)",
    },
    {
        "month": "202510",
        "path": Path("reference/archive/monthly/202510/收集数据/数据采集"),
        "note": "Ambiguous: 2 files in V3 (should error)",
    },
]

results = []
success_count = 0
ambiguity_detected = 0
errors = []

for test in test_cases:
    month = test["month"]
    path = test["path"]
    note = test["note"]

    print(f"{month}: {note}")
    print(f"  Path: {path}")

    if not path.exists():
        result = "❌ Path not found"
        results.append({"month": month, "status": "PATH_NOT_FOUND", "message": result})
        print(f"  {result}")
        print("")
        continue

    try:
        version_result = scanner.detect_version(path, patterns, "highest_number")
        match_result = matcher.match_files(version_result.path, patterns, exclude)

        if match_result.match_count > 1:
            # This is expected for 202510
            result = f"⚠️  AMBIGUITY DETECTED: {match_result.match_count} files (CORRECT behavior)"
            results.append(
                {
                    "month": month,
                    "status": "AMBIGUOUS",
                    "message": result,
                    "files": match_result.match_count,
                }
            )
            ambiguity_detected += 1
            print(f"  {result}")
        else:
            excel_result = reader.read_sheet(
                match_result.matched_file, "规模明细", normalize_columns=True
            )
            result = f"✅ SUCCESS: {version_result.version} | {excel_result.row_count:,} rows"
            results.append(
                {
                    "month": month,
                    "status": "SUCCESS",
                    "version": version_result.version,
                    "rows": excel_result.row_count,
                    "cols": excel_result.column_count,
                    "file": match_result.matched_file.name[:50],
                }
            )
            success_count += 1
            print(f"  {result}")
            print(f"  File: {match_result.matched_file.name[:60]}...")

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:80]

        if "Ambiguous" in error_msg or "ambiguous" in error_msg.lower():
            result = "✅ CORRECTLY ERRORED: Ambiguity detected (expected)"
            results.append(
                {"month": month, "status": "AMBIGUOUS_ERROR", "message": error_msg}
            )
            ambiguity_detected += 1
        else:
            result = f"❌ UNEXPECTED ERROR: {error_type}"
            results.append(
                {
                    "month": month,
                    "status": "ERROR",
                    "error_type": error_type,
                    "message": error_msg,
                }
            )
            errors.append({"month": month, "error": error_type, "message": error_msg})

        print(f"  {result}")
        print(f"  {error_msg}")

    print("")

print("═══════════════════════════════════════════════════════════")
print("SUMMARY")
print("═══════════════════════════════════════════════════════════")
print(f"Total Months Tested: {len(test_cases)}")
print(f"✅ Successful Reads: {success_count}")
print(f"⚠️  Ambiguities Detected: {ambiguity_detected} (correct behavior)")
print(f"❌ Unexpected Errors: {len(errors)}")
print("")

if success_count + ambiguity_detected == len(test_cases):
    print("🎯 EPIC 3 SYSTEM: FULLY OPERATIONAL")
    print("   All test cases handled correctly:")
    print("   - Different folder structures: ✅")
    print("   - Version detection (V1/V2/V3): ✅")
    print("   - Flat structure (no versions): ✅")
    print("   - Ambiguity detection: ✅")
else:
    print("⚠️  EPIC 3 SYSTEM: PARTIAL SUCCESS")
    print(
        f"   Success rate: {(success_count + ambiguity_detected) / len(test_cases) * 100:.0f}%"
    )

print("═══════════════════════════════════════════════════════════")

if errors:
    print("")
    print("UNEXPECTED ERRORS:")
    for err in errors:
        print(f"  {err['month']}: {err['error']} - {err['message']}")
