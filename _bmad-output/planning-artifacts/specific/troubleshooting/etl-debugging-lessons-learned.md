# ETL 问题排查经验教训

> 来源: Story 6.2-P10 I006 诊断过程
> 日期: 2025-12-16
> 作者: AI Assistant (Antigravity)

## 问题概况

**原始问题**: ETL backfill 执行失败 (I006)
**耗时**: 约 20 分钟排查
**根因**: 多层配置问题叠加，非代码逻辑错误

## 排查过程反思

### ❌ 不恰当的排查顺序

1. **假设驱动而非错误驱动**: 过度关注 SQL 生成代码，而非先捕获完整错误堆栈
2. **创建诊断脚本而非直接调试**: 花费时间创建隔离测试，而实际问题在配置层
3. **逐层验证不足**: 没有从 ETL 的最外层开始，逐层向内定位

### ✅ 正确的排查顺序

```
1. 首先获取完整错误堆栈 (--debug --raise-on-error)
2. 从错误堆栈定位具体失败位置
3. 检查该位置的输入数据/配置
4. 验证配置一致性 (YAML ↔ Code ↔ Database)
5. 最后才考虑代码逻辑问题
```

## 实际问题层次

| 层级 | 问题 | 症状 |
|------|------|------|
| 1. 配置层 | `data_sources.yml` 缺少 `output.pk` | `LoadConfig` 验证失败 |
| 2. CLI层 | `build_run_config` 从错误位置读取 `pk` | pk 始终为空列表 |
| 3. Schema层 | DDL 脚本没有 `business.` schema 前缀 | 表创建在 public schema |
| 4. 字段层 | 旧表未重建，字段名仍为 legacy 格式 | 字段不存在错误 |

## 关键经验

### 1. 配置一致性检查清单

在 ETL 执行前应验证:

- [ ] `data_sources.yml` 的 `output.table` 与数据库 schema 匹配
- [ ] `output.pk` 已定义且与 schemas.py 中的 `GOLD_COMPOSITE_KEY` 一致
- [ ] DDL 脚本的 schema 前缀与 `output.schema_name` 一致
- [ ] DDL 脚本的字段名与 Pipeline 输出字段名一致

### 2. 快速定位技巧

```powershell
# 获取完整错误堆栈 (第一步应该做的)
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains <domain> --period <period> --execute \
  --debug --raise-on-error 2>&1 | Select-Object -Last 100
```

### 3. Schema 管理规范

| 表类型 | 管理方式 | 位置 |
|--------|----------|------|
| 英文表 (新架构) | Alembic migrations | `io/schema/migrations/versions/` |
| 中文表 (Legacy 兼容) | DDL 脚本 | `scripts/create_table/ddl/` |

DDL 脚本必须包含完整 schema 前缀 (如 `business."规模明细"`)，否则表会创建到错误位置。

## 修复记录

1. **`config/data_sources.yml`**: 添加 `output.pk` 配置
2. **`src/work_data_hub/cli/etl.py`**: 修复 `pk` 读取逻辑优先从 `output` 部分读取
3. **`scripts/create_table/ddl/annuity_performance.sql`**: 添加 `business.` schema 前缀
4. **执行 DDL 重建**: `uv run ... python -m scripts.create_table.apply_sql --domain annuity_performance`

## 预防措施

1. **添加配置验证**: 考虑在 ETL 启动时验证 `pk` 配置完整性
2. **统一 Schema 管理**: 长期考虑将中文表迁移到 Alembic 管理
3. **CI 检查**: 添加 DDL 文件 schema 前缀一致性检查
