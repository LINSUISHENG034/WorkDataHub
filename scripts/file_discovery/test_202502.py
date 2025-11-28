#!/usr/bin/env python
"""Test 202502 flat structure."""
from pathlib import Path
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.readers.excel_reader import ExcelReader

scanner = VersionScanner()
matcher = FilePatternMatcher()
reader = ExcelReader()

patterns = ['*年金终稿*.xlsx', '*年金数据*.xlsx']
exclude = ['~$*']

print('Test Case 3: 202502 - Flat Structure (No Version Folders)')
print('=' * 60)

# Test flat structure (file directly in root)
base_path = Path('reference/archive/monthly/202502')
print(f'Path: {base_path}')
print(f'Structure: File directly in root (no V1/V2/V3 folders)')
print('')

try:
    version_result = scanner.detect_version(base_path, patterns, 'highest_number')
    print(f'✅ Version Detection: {version_result.version}')
    print(f'   Selected Path: {version_result.path}')

    match_result = matcher.match_files(version_result.path, patterns, exclude)
    print(f'✅ File Matching: {match_result.matched_file.name}')

    excel_result = reader.read_sheet(match_result.matched_file, '规模明细', normalize_columns=True)
    print(f'✅ Excel Reading: {excel_result.row_count:,} rows, {excel_result.column_count} columns')
    print('')
    print('✅ SUCCESS: System handles flat structure!')
except Exception as e:
    print(f'❌ FAILED: {type(e).__name__}')
    print(f'   Message: {str(e)[:100]}')
