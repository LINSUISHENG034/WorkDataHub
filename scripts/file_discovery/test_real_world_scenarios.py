#!/usr/bin/env python
"""Test Epic 3 system against real-world edge cases identified by Link."""

from pathlib import Path

from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.readers.excel_reader import ExcelReader

scanner = VersionScanner()
matcher = FilePatternMatcher()
reader = ExcelReader()

patterns = ["*年金终稿*.xlsx", "*年金数据*.xlsx", "*年金规模收入*.xlsx", "*年金*.xlsx"]
exclude = ["~$*", "*回复*", "*.eml"]

print("═══════════════════════════════════════════════════════════")
print("REAL-WORLD EDGE CASE VALIDATION")
print("═══════════════════════════════════════════════════════════")
print("")

# Test Case 1: 202311 - Different folder structure (no 收集数据 layer)
print("Test Case 1: 202311 - Different Folder Structure")
print("Expected path: 数据采集/V1/ (no 收集数据 layer)")
print("-" * 60)

test_paths_202311 = [
    Path("reference/archive/monthly/202311/收集数据/数据采集"),  # Expected by system
    Path("reference/archive/monthly/202311/数据采集"),  # Actual structure
]

for path in test_paths_202311:
    print(f"  Testing: {path}")
    if not path.exists():
        print("    ❌ Path does not exist")
        continue

    try:
        version_result = scanner.detect_version(path, patterns, "highest_number")
        match_result = matcher.match_files(version_result.path, patterns, exclude)
        excel_result = reader.read_sheet(
            match_result.matched_file, "规模明细", normalize_columns=True
        )
        print(
            f"    ✅ SUCCESS: {version_result.version} | {excel_result.row_count:,} rows"
        )
        print(f"       File: {match_result.matched_file.name}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {str(e)[:80]}")

print("")

# Test Case 2: 202510 - Ambiguous file matching (2 files in V3)
print("Test Case 2: 202510 - Multiple Files in Same Version")
print("Expected: System should detect ambiguity and report warning/error")
print("Files: 年金规模收入数据 1110.xlsx and 1111.xlsx")
print("-" * 60)

base_path_202510 = Path("reference/archive/monthly/202510/收集数据/数据采集")
print(f"  Testing: {base_path_202510}")

try:
    version_result = scanner.detect_version(
        base_path_202510, patterns, "highest_number"
    )
    print(f"    ✅ Version Detection: {version_result.version}")

    match_result = matcher.match_files(version_result.path, patterns, exclude)
    print(f"    Match count: {match_result.match_count}")

    if match_result.match_count > 1:
        print(f"    ⚠️  AMBIGUITY DETECTED: {match_result.match_count} files matched")
        print(
            f"    ❌ ISSUE: System should raise error but returned: {match_result.matched_file.name}"
        )
    else:
        excel_result = reader.read_sheet(
            match_result.matched_file, "规模明细", normalize_columns=True
        )
        print(f"    ✅ SUCCESS: {excel_result.row_count:,} rows")
        print(f"       File: {match_result.matched_file.name}")
except Exception as e:
    print(f"    ✅ CORRECTLY FAILED: {type(e).__name__}")
    print(f"       Message: {str(e)[:100]}")

print("")

# Test Case 3: 202502 - Version detection capability test
print("Test Case 3: 202502 - Version Detection Test")
print("Testing ability to detect highest version number")
print("-" * 60)

base_path_202502 = Path("reference/archive/monthly/202502/收集数据/数据采集")
print(f"  Testing: {base_path_202502}")

if not base_path_202502.exists():
    print("    ❌ Path does not exist")
else:
    # Check what versions exist
    versions = sorted([v.name for v in base_path_202502.glob("V*") if v.is_dir()])
    print(f"    Versions found: {versions}")

    try:
        version_result = scanner.detect_version(
            base_path_202502, patterns, "highest_number"
        )
        print(f"    ✅ Version Detection: Selected {version_result.version}")
        print(f"       Rejected: {version_result.rejected_versions}")

        match_result = matcher.match_files(version_result.path, patterns, exclude)
        excel_result = reader.read_sheet(
            match_result.matched_file, "规模明细", normalize_columns=True
        )
        print(f"    ✅ SUCCESS: {excel_result.row_count:,} rows")
        print(f"       File: {match_result.matched_file.name}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {str(e)[:80]}")

print("")
print("═══════════════════════════════════════════════════════════")
print("SUMMARY OF FINDINGS")
print("═══════════════════════════════════════════════════════════")
print("")
print("Issue 1: 202311 folder structure difference")
print("  Root Cause: System assumes 收集数据/ layer always exists")
print("  Impact: Cannot handle legacy/different folder structures")
print("")
print("Issue 2: 202510 multiple file ambiguity")
print("  Root Cause: FilePatternMatcher ambiguity detection may not work")
print("  Impact: System may select wrong file or not warn user")
print("")
print("Issue 3: 202502 version detection")
print("  Status: To be determined by test results")
print("═══════════════════════════════════════════════════════════")
