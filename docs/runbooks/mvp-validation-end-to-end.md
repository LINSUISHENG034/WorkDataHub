# MVP Validation Runbook: End-to-End Pipeline Verification

**Purpose:** 验证 WorkDataHub 两个已实现 domain (`annuity_performance`, `annuity_income`) 的完整工作流，从原始数据发现到数据库写入。

**Prerequisites:**
- Python 3.12+ with `uv` package manager
- PostgreSQL 数据库可访问（配置在 `.env`）
- 真实生产数据位于 `tests/fixtures/real_data/`

**Target Tables:**
- `wdh_dev.annuity_performance_NEW`
- `wdh_dev.annuity_income_NEW`

---

## Phase 1: Environment Verification

### Step 1.1: Verify Python Environment

```bash
uv --version
```

**Expected:** `uv 0.x.x` 或更高版本

### Step 1.2: Verify Dependencies

```bash
uv sync
```

**Expected:** 所有依赖安装成功，无错误

### Step 1.3: Verify Database Connection

```bash
uv run python -c "
from work_data_hub.config import get_settings
settings = get_settings()
print(f'Database URL: {settings.get_database_connection_string()[:50]}...')
print(f'Data Base Dir: {settings.data_base_dir}')
"
```

**Expected:** 显示数据库连接字符串（部分隐藏）和数据目录路径

### Step 1.4: Test Database Connectivity

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader
loader = WarehouseLoader()
print('Database connection: OK')
loader.close()
"
```

**Expected:** `Database connection: OK`

---

## Phase 2: Data Discovery Verification

### Step 2.1: List Available Real Data Files

```bash
uv run python -c "
from pathlib import Path
real_data = Path('tests/fixtures/real_data')
for month_dir in sorted(real_data.iterdir()):
    if month_dir.is_dir():
        print(f'\n=== {month_dir.name} ===')
        for f in month_dir.rglob('*.xlsx'):
            print(f'  {f.relative_to(real_data)}')
"
```

**Expected:** 列出 `202311/`, `202411/`, `202412/` 等目录下的 Excel 文件

### Step 2.2: Test File Discovery Service (annuity_performance)

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService

service = FileDiscoveryService()
# 使用自动版本检测，发现最新数据
result = service.discover_and_load(domain='annuity_performance', month='202412')

print(f'File: {result.file_path}')
print(f'Version: {result.version}')
print(f'Sheet: {result.sheet_name}')
print(f'Rows: {result.row_count}')
print(f'Columns: {result.column_count}')
print(f'Duration: {result.duration_ms}ms')
print(f'Columns: {list(result.df.columns)[:10]}...')
"
```

**Expected:**
- 自动发现最新版本文件（V2 优先于 V1）
- 显示文件路径、版本、行数、列数

### Step 2.3: Test File Discovery Service (annuity_income)

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService

service = FileDiscoveryService()
result = service.discover_and_load(domain='annuity_income', month='202412')

print(f'File: {result.file_path}')
print(f'Version: {result.version}')
print(f'Sheet: {result.sheet_name}')
print(f'Rows: {result.row_count}')
print(f'Columns: {result.column_count}')
print(f'Duration: {result.duration_ms}ms')
print(f'Columns: {list(result.df.columns)[:10]}...')
"
```

**Expected:**
- 发现 `收入明细` sheet
- 显示正确的列（包含 `固费`, `浮费`, `回补`, `税`）

---

## Phase 3: Pipeline Processing Verification (Dry Run)

### Step 3.1: Test annuity_performance Pipeline (No DB Write)

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.domain.annuity_performance.service import process_with_enrichment

# Step 1: Discover file
discovery = FileDiscoveryService()
result = discovery.discover_and_load(domain='annuity_performance', month='202412')
print(f'Discovered: {result.file_path.name}')
print(f'Input rows: {result.row_count}')

# Step 2: Process through pipeline (no DB)
processing = process_with_enrichment(
    rows=result.df.to_dict(orient='records'),
    data_source=str(result.file_path),
    enrichment_service=None,
    sync_lookup_budget=0,
    export_unknown_names=False,
)

print(f'Output records: {len(processing.records)}')
print(f'Processing time: {processing.processing_time_ms}ms')
if processing.enrichment_stats:
    print(f'Enrichment stats: {processing.enrichment_stats}')

# Show sample output
if processing.records:
    sample = processing.records[0]
    print(f'Sample record keys: {list(sample.model_dump().keys())[:10]}...')
"
```

**Expected:**
- 输入行数 > 30,000
- 输出记录数接近输入行数（少量因验证失败被丢弃）
- 处理时间 < 30 秒

### Step 3.2: Test annuity_income Pipeline (No DB Write)

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.domain.annuity_income.service import process_with_enrichment

# Step 1: Discover file
discovery = FileDiscoveryService()
result = discovery.discover_and_load(domain='annuity_income', month='202412')
print(f'Discovered: {result.file_path.name}')
print(f'Input rows: {result.row_count}')

# Step 2: Process through pipeline (no DB)
processing = process_with_enrichment(
    rows=result.df.to_dict(orient='records'),
    data_source=str(result.file_path),
    enrichment_service=None,
    sync_lookup_budget=0,
    export_unknown_names=False,
)

print(f'Output records: {len(processing.records)}')
print(f'Processing time: {processing.processing_time_ms}ms')
if processing.enrichment_stats:
    print(f'Enrichment stats: {processing.enrichment_stats}')

# Show sample output
if processing.records:
    sample = processing.records[0]
    print(f'Sample record keys: {list(sample.model_dump().keys())[:10]}...')
"
```

**Expected:**
- 输入行数 > 2,000
- 输出记录数接近输入行数
- 包含正确的收入字段（固费、浮费、回补、税）

---

## Phase 4: Database Schema Verification

### Step 4.1: Check Target Tables Exist

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()

# Check annuity_performance_NEW
try:
    cols = loader.get_allowed_columns('annuity_performance_NEW', 'wdh_dev')
    print(f'annuity_performance_NEW columns ({len(cols)}):')
    print(f'  {cols[:10]}...')
except Exception as e:
    print(f'annuity_performance_NEW: ERROR - {e}')

# Check annuity_income_NEW
try:
    cols = loader.get_allowed_columns('annuity_income_NEW', 'wdh_dev')
    print(f'annuity_income_NEW columns ({len(cols)}):')
    print(f'  {cols[:10]}...')
except Exception as e:
    print(f'annuity_income_NEW: ERROR - {e}')

loader.close()
"
```

**Expected:** 两个表都存在，显示列名列表

### Step 4.2: Check Current Row Counts (Before Load)

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM wdh_dev.annuity_performance_NEW')
        perf_count = cur.fetchone()[0]
        print(f'annuity_performance_NEW: {perf_count} rows')

        cur.execute('SELECT COUNT(*) FROM wdh_dev.annuity_income_NEW')
        income_count = cur.fetchone()[0]
        print(f'annuity_income_NEW: {income_count} rows')
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:** 显示当前行数（可能为 0 或之前测试的数据）

---

## Phase 5: Full End-to-End Validation (With Database Write)

### Step 5.1: Execute annuity_performance Full Pipeline

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader
from work_data_hub.domain.annuity_performance.service import process_annuity_performance

# Initialize services
file_discovery = FileDiscoveryService()
warehouse_loader = WarehouseLoader()

try:
    # Execute full pipeline
    result = process_annuity_performance(
        month='202412',
        file_discovery=file_discovery,
        warehouse_loader=warehouse_loader,
        enrichment_service=None,
        domain='annuity_performance',
        table_name='annuity_performance_NEW',
        schema='wdh_dev',
        sync_lookup_budget=0,
        export_unknown_names=True,
        upsert_keys=['月度', '计划代码', 'company_id'],
    )

    print('=' * 60)
    print('ANNUITY_PERFORMANCE PIPELINE RESULT')
    print('=' * 60)
    print(f'Success: {result.success}')
    print(f'File: {result.file_path}')
    print(f'Version: {result.version}')
    print(f'Rows Loaded: {result.rows_loaded}')
    print(f'Rows Failed: {result.rows_failed}')
    print(f'Duration: {result.duration_ms:.2f}ms')
    print('=' * 60)

finally:
    warehouse_loader.close()
"
```

**Expected:**
- `Success: True`
- `Rows Loaded: > 30,000`
- `Rows Failed: < 100` (少量验证失败是正常的)

### Step 5.2: Execute annuity_income Full Pipeline

```bash
uv run python -c "
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader
from work_data_hub.domain.annuity_income.service import process_annuity_income

# Initialize services
file_discovery = FileDiscoveryService()
warehouse_loader = WarehouseLoader()

try:
    # Execute full pipeline
    result = process_annuity_income(
        month='202412',
        file_discovery=file_discovery,
        warehouse_loader=warehouse_loader,
        enrichment_service=None,
        domain='annuity_income',
        table_name='annuity_income_NEW',
        schema='wdh_dev',
        sync_lookup_budget=0,
        export_unknown_names=True,
        upsert_keys=['月度', '计划号', 'company_id'],
    )

    print('=' * 60)
    print('ANNUITY_INCOME PIPELINE RESULT')
    print('=' * 60)
    print(f'Success: {result.success}')
    print(f'File: {result.file_path}')
    print(f'Version: {result.version}')
    print(f'Rows Loaded: {result.rows_loaded}')
    print(f'Rows Failed: {result.rows_failed}')
    print(f'Duration: {result.duration_ms:.2f}ms')
    print('=' * 60)

finally:
    warehouse_loader.close()
"
```

**Expected:**
- `Success: True`
- `Rows Loaded: > 2,000`
- `Rows Failed: < 50`

---

## Phase 6: Database Verification (Final Acceptance)

### Step 6.1: Verify Row Counts After Load

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM wdh_dev.annuity_performance_NEW')
        perf_count = cur.fetchone()[0]
        print(f'annuity_performance_NEW: {perf_count} rows')

        cur.execute('SELECT COUNT(*) FROM wdh_dev.annuity_income_NEW')
        income_count = cur.fetchone()[0]
        print(f'annuity_income_NEW: {income_count} rows')
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:** 行数与 Step 5.1/5.2 的 `Rows Loaded` 一致

### Step 6.2: Sample Data Verification (annuity_performance)

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader
import pandas as pd

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    query = '''
    SELECT 月度, 计划代码, company_id, 客户名称, 业务类型, 期末规模
    FROM wdh_dev.annuity_performance_NEW
    LIMIT 5
    '''
    df = pd.read_sql(query, conn)
    print('Sample annuity_performance_NEW data:')
    print(df.to_string())
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:** 显示 5 行样本数据，包含正确的列值

### Step 6.3: Sample Data Verification (annuity_income)

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader
import pandas as pd

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    query = '''
    SELECT 月度, 计划号, company_id, 客户名称, 固费, 浮费, 回补, 税
    FROM wdh_dev.annuity_income_NEW
    LIMIT 5
    '''
    df = pd.read_sql(query, conn)
    print('Sample annuity_income_NEW data:')
    print(df.to_string())
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:** 显示 5 行样本数据，包含正确的收入字段

### Step 6.4: Data Integrity Check

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    with conn.cursor() as cur:
        # Check for NULL company_id (should be minimal)
        cur.execute('''
            SELECT
                'annuity_performance_NEW' as table_name,
                COUNT(*) as total,
                COUNT(company_id) as with_company_id,
                COUNT(*) - COUNT(company_id) as null_company_id
            FROM wdh_dev.annuity_performance_NEW
            UNION ALL
            SELECT
                'annuity_income_NEW',
                COUNT(*),
                COUNT(company_id),
                COUNT(*) - COUNT(company_id)
            FROM wdh_dev.annuity_income_NEW
        ''')

        print('Data Integrity Check:')
        print(f'{\"Table\":<30} {\"Total\":>10} {\"With ID\":>10} {\"Null ID\":>10}')
        print('-' * 62)
        for row in cur.fetchall():
            print(f'{row[0]:<30} {row[1]:>10} {row[2]:>10} {row[3]:>10}')
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:**
- `Null ID` 数量应该很少（< 5% 的总行数）
- 大部分记录应该有有效的 `company_id`

### Step 6.5: Unique Key Verification

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    with conn.cursor() as cur:
        # Check for duplicate keys in annuity_performance_NEW
        cur.execute('''
            SELECT COUNT(*) as duplicates FROM (
                SELECT 月度, 计划代码, company_id, COUNT(*) as cnt
                FROM wdh_dev.annuity_performance_NEW
                GROUP BY 月度, 计划代码, company_id
                HAVING COUNT(*) > 1
            ) t
        ''')
        perf_dups = cur.fetchone()[0]

        # Check for duplicate keys in annuity_income_NEW
        cur.execute('''
            SELECT COUNT(*) as duplicates FROM (
                SELECT 月度, 计划号, company_id, COUNT(*) as cnt
                FROM wdh_dev.annuity_income_NEW
                GROUP BY 月度, 计划号, company_id
                HAVING COUNT(*) > 1
            ) t
        ''')
        income_dups = cur.fetchone()[0]

        print('Unique Key Verification:')
        print(f'annuity_performance_NEW duplicate keys: {perf_dups}')
        print(f'annuity_income_NEW duplicate keys: {income_dups}')

        if perf_dups == 0 and income_dups == 0:
            print('\\n✅ All unique key constraints satisfied!')
        else:
            print('\\n⚠️ WARNING: Duplicate keys detected!')
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

**Expected:**
- `duplicate keys: 0` for both tables
- `✅ All unique key constraints satisfied!`

---

## Phase 7: Cleanup (Optional)

### Step 7.1: Clear Test Data (If Needed)

```bash
uv run python -c "
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

loader = WarehouseLoader()
conn = loader._pool.getconn()

try:
    with conn.cursor() as cur:
        # CAUTION: This will delete all data!
        # cur.execute('TRUNCATE TABLE wdh_dev.annuity_performance_NEW')
        # cur.execute('TRUNCATE TABLE wdh_dev.annuity_income_NEW')
        # conn.commit()
        print('Cleanup commands commented out for safety.')
        print('Uncomment and run manually if needed.')
finally:
    loader._pool.putconn(conn)
    loader.close()
"
```

---

## Validation Checklist

| Phase | Step | Status | Notes |
|-------|------|--------|-------|
| 1 | Environment Verification | ⬜ | |
| 2 | Data Discovery | ⬜ | |
| 3 | Pipeline Processing (Dry Run) | ⬜ | |
| 4 | Database Schema | ⬜ | |
| 5 | Full E2E (DB Write) | ⬜ | |
| 6 | Database Verification | ⬜ | |

---

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - 检查 `.env` 文件中的数据库配置
   - 确保 PostgreSQL 服务正在运行
   - 验证网络连接和防火墙设置

2. **File Discovery Failed**
   - 检查 `tests/fixtures/real_data/` 目录是否存在
   - 验证文件名格式是否符合 pattern
   - 检查 `src/work_data_hub/config/data_sources.yml` 配置

3. **Pipeline Processing Errors**
   - 检查日志输出中的具体错误信息
   - 验证数据列名是否与 schema 匹配
   - 检查数据类型转换问题

4. **Database Write Errors**
   - 确保目标表存在且结构正确
   - 检查列名映射是否正确
   - 验证 upsert keys 是否有效

---

**Document Version:** 1.0
**Created:** 2025-12-06
**Author:** WorkDataHub Team (Epic 5.5 Retrospective)
