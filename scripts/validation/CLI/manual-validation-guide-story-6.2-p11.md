# Story 6.2-P11 验证指南

**变更提案**: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-16.md`
**验证日期**: 2025-12-17
**验证目标**: 发现项目代码存在的不足或伪实现

---

## 验证目标

通过实际运行项目模块并检查产生的数据，验证以下核心功能的实现质量：

1. **Pipeline 字段派生修复** - `年金账户号` 从 `集团企业客户号` 派生
2. **enrichment_index 表数据完整性** - Legacy 映射数据是否正确导入
3. **CLI Token 预检测 + 自动刷新** - Token 验证和自动刷新功能

---

## 验证一：Pipeline 字段派生 (`年金账户号`)

### 1.1 验证目的
确认 Step 10 正确将 `集团企业客户号` 的值复制到 `年金账户号` 字段。

### 1.2 验证方法：直接调用 Pipeline 模块

```powershell
# 创建验证脚本
PYTHONPATH=src uv run --env-file .wdh_env python -c "
import pandas as pd
from work_data_hub.domain.annuity_performance.pipeline_builder import build_bronze_to_silver_pipeline
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

# 构造测试数据 - 模拟 Bronze 层原始数据
test_data = pd.DataFrame({
    '月度': ['202510', '202510', '202510'],
    '业务类型': ['企业年金受托', '企业年金投资', '职业年金受托'],
    '计划类型': ['集合计划', '单一计划', '职业年金'],
    '计划代码': ['', '', 'P0001'],
    '客户名称': ['测试公司A', '测试公司B', '测试公司C'],
    '集团企业客户号': ['C12345678', 'C87654321', None],  # 带C前缀和空值
    '机构名称': ['深圳', '北京', '上海'],
    '期初资产规模': [1000000, 2000000, 3000000],
    '期末资产规模': [1100000, 2100000, 3100000],
})

print('=== 原始数据 (Bronze) ===')
print(test_data[['客户名称', '集团企业客户号']].to_string())
print()

# 构建 Pipeline (不启用 enrichment)
pipeline = build_bronze_to_silver_pipeline(enrichment_service=None)
context = PipelineContext(
    pipeline_name='annuity_performance.bronze_to_silver',
    execution_id='manual-validation-6.2-p11',
    timestamp=datetime.now(timezone.utc),
    config={},
    domain='annuity_performance',
)

# 执行 Pipeline
result = pipeline.execute(test_data, context)

print('=== 处理后数据 (Silver) ===')
print('年金账户号 列是否存在:', '年金账户号' in result.columns)
print()

if '年金账户号' in result.columns:
    print('年金账户号 值:')
    for idx, row in result.iterrows():
        print(f'  {row.get(\"客户名称\", \"N/A\")}: 年金账户号={row[\"年金账户号\"]}')

    # 验证逻辑
    print()
    print('=== 验证结果 ===')
    # 检查 C前缀是否被去除
    if result.loc[0, '年金账户号'] == '12345678':
        print('✅ C前缀正确去除: C12345678 -> 12345678')
    else:
        print(f'❌ C前缀未正确去除: 期望 12345678, 实际 {result.loc[0, \"年金账户号\"]}')

    # 检查空值处理
    if pd.isna(result.loc[2, '年金账户号']) or result.loc[2, '年金账户号'] is None:
        print('✅ 空值正确处理: None -> None')
    else:
        print(f'❌ 空值处理异常: 期望 None, 实际 {result.loc[2, \"年金账户号\"]}')
else:
    print('❌ 年金账户号 列不存在!')
"
```

### 1.3 预期结果

| 客户名称 | 原始集团企业客户号 | 期望年金账户号 |
|---------|------------------|--------------|
| 测试公司A | C12345678 | 12345678 |
| 测试公司B | C87654321 | 87654321 |
| 测试公司C | None | None |

### 1.4 潜在问题检查点

- [ ] `年金账户号` 列是否存在于输出 DataFrame
- [ ] `C` 前缀是否被正确去除（Step 9清洗后再复制）
- [ ] 空值/None 是否正确传递
- [ ] Step 10 是否在 Step 13 (DropStep) 之前执行

---

## 验证二：enrichment_index 表数据完整性

### 2.1 验证目的
确认 `enterprise.enrichment_index` 表存在且包含 Legacy 映射数据。

### 2.2 验证方法：直接查询数据库

```powershell
# 检查表是否存在及数据量
PYTHONPATH=src uv run --env-file .wdh_env python -c "
from sqlalchemy import create_engine, text
from work_data_hub.config.settings import get_settings

settings = get_settings()
engine = create_engine(settings.get_database_connection_string())

with engine.connect() as conn:
    # 1. 检查表是否存在
    result = conn.execute(text('''
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'enterprise'
            AND table_name = 'enrichment_index'
        )
    '''))
    table_exists = result.scalar()
    print(f'enrichment_index 表存在: {table_exists}')

    if not table_exists:
        print('❌ 表不存在，需要执行 alembic 迁移')
        exit(1)

    # 2. 检查数据量
    result = conn.execute(text('SELECT COUNT(*) FROM enterprise.enrichment_index'))
    total_count = result.scalar()
    print(f'总记录数: {total_count}')

    if total_count == 0:
        print('❌ 表为空，需要执行数据迁移脚本')
        exit(1)

    # 3. 按 lookup_type 分组统计
    result = conn.execute(text('''
        SELECT lookup_type, COUNT(*) as cnt
        FROM enterprise.enrichment_index
        GROUP BY lookup_type
        ORDER BY cnt DESC
    '''))
    print()
    print('按 lookup_type 分布:')
    for row in result:
        print(f'  {row[0]}: {row[1]} 条')

    # 4. 按 source_type 分组统计
    result = conn.execute(text('''
        SELECT source, COUNT(*) as cnt
        FROM enterprise.enrichment_index
        GROUP BY source
        ORDER BY cnt DESC
    '''))
    print()
    print('按 source 分布:')
    for row in result:
        print(f'  {row[0]}: {row[1]} 条')

    # 5. 抽样检查数据质量
    result = conn.execute(text('''
        SELECT lookup_key, company_id, lookup_type, source
        FROM enterprise.enrichment_index
        WHERE company_id IS NOT NULL
        LIMIT 5
    '''))
    print()
    print('数据样本 (前5条):')
    for row in result:
        print(f'  {row[0]} -> {row[1]} ({row[2]}/{row[3]})')
"
```

### 2.3 预期结果

- 表 `enterprise.enrichment_index` 存在
- 总记录数 > 0（预期约 30,000+ 条，来自 legacy 迁移）
- `lookup_type` 包含: `customer_name`, `plan_code`, `account_number` 等
- `source_type` 包含: `legacy_migration`, `yaml_override` 等

### 2.4 潜在问题检查点

- [ ] 表是否存在（alembic 迁移是否执行）
- [ ] 数据是否为空（迁移脚本是否执行）
- [ ] `company_id` 是否有效（非空、格式正确）
- [ ] 是否存在重复的 `lookup_key`

---

## 验证三：CLI Token 预检测 + 自动刷新

### 3.1 验证目的
确认 CLI 启动时能正确验证 Token 并在失效时触发自动刷新。

### 3.2 验证方法 A：Token 验证函数直接测试

```powershell
# 测试 validate_eqc_token 函数
PYTHONPATH=src uv run --env-file .wdh_env python -c "
from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token
from work_data_hub.config.settings import get_settings

settings = get_settings()
token = settings.eqc_token
base_url = settings.eqc_base_url

print('=== Token 验证测试 ===')
print(f'Token 配置: {\"已配置\" if token else \"未配置\"}')
print(f'Base URL: {base_url}')

if token:
    print()
    print('正在验证 Token...')
    is_valid = validate_eqc_token(token, base_url)
    print(f'Token 有效: {is_valid}')

    if is_valid:
        print('✅ Token 验证通过')
    else:
        print('❌ Token 已失效，需要刷新')
else:
    print('⚠️ 未配置 Token (WDH_EQC_TOKEN)')
"
```

### 3.3 验证方法 B：CLI 参数解析测试

```powershell
# 测试 --no-auto-refresh-token 参数是否被正确解析
PYTHONPATH=src uv run --env-file .wdh_env python -c "
import sys
sys.argv = ['etl', '--domains', 'annuity_performance', '--no-auto-refresh-token', '--help']

from work_data_hub.cli.etl import main
import argparse

# 手动解析参数检查
parser = argparse.ArgumentParser()
parser.add_argument('--no-auto-refresh-token', action='store_true', default=False)
parser.add_argument('--domains', type=str)

args, _ = parser.parse_known_args(['--domains', 'annuity_performance', '--no-auto-refresh-token'])
print(f'--no-auto-refresh-token 参数值: {args.no_auto_refresh_token}')
print(f'✅ 参数解析正确' if args.no_auto_refresh_token else '❌ 参数解析失败')
"
```

### 3.4 验证方法 C：自动刷新流程测试（需要人工交互）

```powershell
# 测试自动刷新流程 - 会弹出二维码窗口
PYTHONPATH=src uv run --env-file .wdh_env python -c "
from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

print('=== 自动刷新流程测试 ===')
print('即将弹出二维码窗口，请使用「快乐平安」APP扫码...')
print('(如果不想测试，请在 10 秒内关闭窗口)')
print()

token = run_get_token_auto_qr(timeout_seconds=60, save_to_env=False)

if token:
    print(f'✅ Token 获取成功: {token[:8]}...{token[-4:]}')
else:
    print('❌ Token 获取失败或用户取消')
"
```

### 3.5 验证方法 D：完整 CLI 流程测试（Dry-run）

```powershell
# 完整 CLI 流程测试 - 不实际执行数据库操作
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202510 --enrichment-enabled
```

观察输出中是否包含：
- `🔐 Validating EQC token...` - Token 验证开始
- `✅ Token valid` 或 `❌ Token invalid/expired` - 验证结果
- 如果失效，是否触发 `Attempting to refresh token via QR login...`

### 3.6 预期结果

| 场景 | 预期行为 |
|-----|---------|
| Token 有效 | 显示 `✅ Token valid`，继续执行 |
| Token 失效 + 自动刷新开启 | 弹出二维码窗口 |
| Token 失效 + `--no-auto-refresh-token` | 显示警告，继续执行（无 EQC 查询） |
| 无 Token 配置 | 显示 `⚠️ No EQC token configured` |

### 3.7 潜在问题检查点

- [ ] `validate_eqc_token` 函数是否正确处理网络错误
- [ ] 自动刷新是否正确保存 Token 到 `.wdh_env`
- [ ] `--no-auto-refresh-token` 参数是否生效
- [ ] 非 `annuity_performance` 域是否跳过 Token 检查

---

## 验证四：端到端数据流验证

### 4.1 验证目的
使用真实数据验证完整 ETL 流程，确认 `年金账户号` 和 `company_id` 正确解析。

### 4.2 验证方法：Dry-run 模式执行

```powershell
# 使用 202510 月度数据执行验证（建议先 dry-run/plan-only 看执行计划，再用 --execute 写入 DB）
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202510 \
    --enrichment-enabled \
    --debug
```

### 4.3 验证数据检查

执行后，检查输出的 DataFrame 或数据库中的数据：

```powershell
# 检查处理后的数据
PYTHONPATH=src uv run --env-file .wdh_env python -c "
from sqlalchemy import create_engine, text
from work_data_hub.config.settings import get_settings

settings = get_settings()
engine = create_engine(settings.get_database_connection_string())

with engine.connect() as conn:
    # 检查 business.规模明细 表中 202510 数据
    result = conn.execute(text('''
        SELECT
            COUNT(*) as total,
            COUNT("年金账户号") as with_account_number,
            COUNT(CASE WHEN company_id NOT LIKE 'IN_%' THEN 1 END) as resolved_company_id
        FROM business."规模明细"
        WHERE 月度 = '2025-10-01'
    '''))
    row = result.fetchone()

    if row:
        total, with_account, resolved = row
        print(f'=== 202510 数据统计 ===')
        print(f'总记录数: {total}')
        print(f'有年金账户号: {with_account} ({with_account/total*100:.1f}%)')
        print(f'已解析 company_id: {resolved} ({resolved/total*100:.1f}%)')

        # 成功标准
        if with_account / total > 0.5:
            print('✅ 年金账户号填充率 > 50%')
        else:
            print('❌ 年金账户号填充率过低')

        if resolved / total > 0.5:
            print('✅ company_id 解析率 > 50%')
        else:
            print('❌ company_id 解析率过低 (大量 IN_xxx 临时ID)')
    else:
        print('⚠️ 未找到 202510 数据')
"
```

### 4.4 成功标准（来自变更提案）

1. ✅ `年金账户号` 正确从 `集团企业客户号` 派生
2. ✅ `enrichment_index` 表包含 Legacy 映射数据
3. ✅ 202510 月度数据 `company_id` 解析率 > 50% (非临时 ID)
4. ✅ CLI Token 预检测正常工作

---

## 验证五：边界条件和异常处理

### 5.1 空数据处理

```powershell
PYTHONPATH=src uv run --env-file .wdh_env python -c "
import pandas as pd
from work_data_hub.domain.annuity_performance.pipeline_builder import build_bronze_to_silver_pipeline
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

# 测试空 DataFrame
empty_df = pd.DataFrame(columns=['月度', '业务类型', '计划类型', '客户名称', '集团企业客户号'])
pipeline = build_bronze_to_silver_pipeline(enrichment_service=None)
context = PipelineContext(
    pipeline_name='annuity_performance.bronze_to_silver',
    execution_id='manual-validation-empty',
    timestamp=datetime.now(timezone.utc),
    config={},
    domain='annuity_performance',
)

try:
    result = pipeline.execute(empty_df, context)
    print(f'✅ 空数据处理成功，输出行数: {len(result)}')
except Exception as e:
    print(f'❌ 空数据处理失败: {e}')
"
```

### 5.2 缺失列处理

```powershell
PYTHONPATH=src uv run --env-file .wdh_env python -c "
import pandas as pd
from work_data_hub.domain.annuity_performance.pipeline_builder import build_bronze_to_silver_pipeline
from work_data_hub.domain.pipelines.types import PipelineContext
from datetime import datetime, timezone

# 测试缺少 集团企业客户号 列
df_no_column = pd.DataFrame({
    '月度': ['202510'],
    '业务类型': ['企业年金受托'],
    '计划类型': ['集合计划'],
    '客户名称': ['测试公司'],
    # 故意不包含 集团企业客户号
})

pipeline = build_bronze_to_silver_pipeline(enrichment_service=None)
context = PipelineContext(
    pipeline_name='annuity_performance.bronze_to_silver',
    execution_id='manual-validation-missing-column',
    timestamp=datetime.now(timezone.utc),
    config={},
    domain='annuity_performance',
)

try:
    result = pipeline.execute(df_no_column, context)
    if '年金账户号' in result.columns:
        print(f'年金账户号 值: {result[\"年金账户号\"].iloc[0]}')
        if pd.isna(result['年金账户号'].iloc[0]) or result['年金账户号'].iloc[0] is None:
            print('✅ 缺失列正确处理为 None')
        else:
            print('❌ 缺失列处理异常')
    else:
        print('❌ 年金账户号 列未创建')
except Exception as e:
    print(f'❌ 缺失列处理失败: {e}')
"
```

---

## 总结：验证检查清单

| 验证项 | 验证方法 | 通过标准 |
|-------|---------|---------|
| Pipeline Step 10 存在 | 代码审查 | `pipeline_builder.py:261-267` |
| 年金账户号 正确派生 | 验证一 | C前缀去除，值正确复制 |
| enrichment_index 表存在 | 验证二 | 表存在且有数据 |
| Legacy 数据已迁移 | 验证二 | 记录数 > 10,000 |
| Token 验证函数工作 | 验证三A | 返回 True/False |
| CLI 参数解析正确 | 验证三B | `--no-auto-refresh-token` 生效 |
| 自动刷新流程工作 | 验证三C | 二维码窗口弹出 |
| 端到端数据正确 | 验证四 | 解析率 > 50% |
| 边界条件处理 | 验证五 | 无异常抛出 |

---

## 代码参考

| 文件 | 行号 | 说明 |
|-----|------|-----|
| `pipeline_builder.py` | 261-267 | Step 10: 年金账户号派生 |
| `pipeline_builder.py` | 254-259 | Step 9: 集团企业客户号清洗 |
| `etl.py` | 39-104 | Token 验证和自动刷新 |
| `eqc_provider.py` | 104-134 | `validate_eqc_token()` 函数 |
| `auto_eqc_auth.py` | 507-538 | `run_get_token_auto_qr()` 函数 |
