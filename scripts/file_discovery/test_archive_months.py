#!/usr/bin/env python
"""Test Epic 3 file discovery across all archived months."""
from pathlib import Path
from work_data_hub.io.connectors.version_scanner import VersionScanner
from work_data_hub.io.connectors.file_pattern_matcher import FilePatternMatcher
from work_data_hub.io.readers.excel_reader import ExcelReader

# Test all archived months
months = ['202311', '202411', '202412', '202501', '202510']
patterns = ['*年金终稿*.xlsx', '*年金数据*.xlsx', '*年金*.xlsx']
exclude = ['~$*', '*回复*', '*.eml']

scanner = VersionScanner()
matcher = FilePatternMatcher()
reader = ExcelReader()

print('Testing file-pattern-aware system across ALL archive months:')
print('═══════════════════════════════════════════════════════════')
print('')

success_count = 0
results = []

for month in months:
    base_path = Path(f'reference/archive/monthly/{month}/收集数据/数据采集')

    if not base_path.exists():
        result = f'❌ {month}: Path not found'
        results.append(result)
        print(result)
        continue

    try:
        version_result = scanner.detect_version(base_path, patterns, 'highest_number')
        match_result = matcher.match_files(version_result.path, patterns, exclude)
        excel_result = reader.read_sheet(match_result.matched_file, '规模明细', normalize_columns=True)

        result = f'✅ {month}: {version_result.version} | {excel_result.row_count:,} rows | {match_result.matched_file.name[:40]}'
        results.append(result)
        print(result)
        success_count += 1
    except Exception as e:
        result = f'❌ {month}: {type(e).__name__}: {str(e)[:60]}'
        results.append(result)
        print(result)

print('')
print(f'Success Rate: {success_count}/{len(months)} months ({success_count/len(months)*100:.0f}%)')
print('═══════════════════════════════════════════════════════════')
