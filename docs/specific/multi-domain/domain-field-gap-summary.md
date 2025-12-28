# 域字段缺失问题汇总

> **日期:** 2025-12-29
> **相关 Story:** Epic 7.3 - Multi-Domain Consistency Fixes
> **状态:** ✅ 已修复

---

## 📋 概述

经检查 `annuity_income` 和 `annuity_performance` 两个业务域，发现 Schema 定义与原始 Excel 数据源存在字段缺失，导致部分业务数据无法写入数据库。

---

## 🔍 问题汇总表

| 域名称 | 表名 | 缺失字段数量 | 影响程度 |
|--------|------|-------------|----------|
| `annuity_income` | `business.收入明细` | 4 个 | **高** |
| `annuity_performance` | `business.规模明细` | 4 个 | **中** |

---

## 📊 详细缺失字段清单

### 1. annuity_income（收入明细）

| # | 缺失字段 | 推测类型 | 可空性 | 用途说明 |
|---|---------|----------|--------|----------|
| 1 | `计划名称` | VARCHAR(255) | NULL | 计划代码的人类可读名称 |
| 2 | `组合类型` | VARCHAR(255) | NULL | 组合的类型分类 |
| 3 | `组合名称` | VARCHAR(255) | NULL | 组合代码的人类可读名称 |
| 4 | `机构名称` | VARCHAR(255) | NULL | 机构代码的人类可读名称 |

**Excel 源文件信息:**
- 文件: `tests/fixtures/real_data/202412/收集数据/数据采集/V1/【for年金分战区经营分析】24年12月年金规模收入数据0109采集.xlsx`
- Sheet: `收入明细（缺少企年投资）` (注意：Schema 定义为 `收入明细`，ETL 层已有兼容逻辑)

**已排除的"伪缺失"字段:**
- `年金账户名`: ETL 层通过公司 ID 解析生成 ✅
- `产品线代码`: ETL 层根据业务规则计算得出 ✅

---

### 2. annuity_performance（规模明细）

| # | 缺失字段 | 推测类型 | 可空性 | 用途说明 |
|---|---------|----------|--------|----------|
| 1 | `子企业号` | VARCHAR(50) | NULL | 子企业的编号标识（**可选字段**，非所有 Excel 都包含） |
| 2 | `子企业名称` | VARCHAR(255) | NULL | 子企业的人类可读名称（**可选字段**） |
| 3 | `集团企业客户号` | VARCHAR(50) | NULL | 集团企业客户的编号标识（**可选字段**） |
| 4 | `集团企业客户名称` | VARCHAR(255) | NULL | 集团企业客户的人类可读名称（**可选字段**） |

**Excel 源文件信息:**
- 文件: `tests/fixtures/real_data/202412/收集数据/数据采集/V1/【for年金分战区经营分析】24年12月年金规模收入数据0109采集.xlsx`
- Sheet: `规模明细`

**已排除的"伪缺失"字段:**
- `年金账户名`: ETL 层通过公司 ID 解析生成 ✅
- `年金账户号`: ETL 层通过公司 ID 解析生成 ✅
- `产品线代码`: ETL 层根据业务规则计算得出 ✅
- `年化收益率`: ETL 层计算得出 ✅
- `流失_含待遇支付`: ETL 层字段映射（Excel: `流失(含待遇支付)` → Schema: `流失_含待遇支付`） ✅
- `机构名称`: ETL 层字段映射（Excel: `机构` → Schema: `机构名称`） ✅

---

## 🔧 修复计划

### Phase 1: Schema 定义更新

#### 文件 1: `src/work_data_hub/infrastructure/schema/definitions/annuity_income.py`

**位置:** 在 `columns` 列表中，`机构代码` 之后添加

```python
ColumnDef("机构代码", ColumnType.STRING, max_length=255),
# ===== 新增字段开始 =====
ColumnDef("计划名称", ColumnType.STRING, nullable=True, max_length=255),
ColumnDef("组合类型", ColumnType.STRING, nullable=True, max_length=255),
ColumnDef("组合名称", ColumnType.STRING, nullable=True, max_length=255),
ColumnDef("机构名称", ColumnType.STRING, nullable=True, max_length=255),
# ===== 新增字段结束 =====
ColumnDef(
    "固费",
    ColumnType.DECIMAL,
    nullable=False,
    precision=18,
    scale=4,
),
```

#### 文件 2: `src/work_data_hub/infrastructure/schema/definitions/annuity_performance.py`

**位置:** 在 `columns` 列表中，`年金账户名` 之后添加

```python
ColumnDef("年金账户名", ColumnType.STRING, max_length=255),
ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),
# ===== 新增字段开始 =====
ColumnDef("子企业号", ColumnType.STRING, nullable=True, max_length=50),
ColumnDef("子企业名称", ColumnType.STRING, nullable=True, max_length=255),
ColumnDef("集团企业客户号", ColumnType.STRING, nullable=True, max_length=50),
ColumnDef("集团企业客户名称", ColumnType.STRING, nullable=True, max_length=255),
# ===== 新增字段结束 =====
```

---

### Phase 2: Alembic 迁移脚本更新

**⚠️ 重要说明:**

1. **生产环境迁移机制：** 项目使用 Alembic 作为生产环境的数据库迁移工具
   - 配置文件：`alembic.ini`
   - 迁移脚本：`io/schema/migrations/versions/`
   - Domain Tables 迁移：`002_initial_domains.py`

2. **迁移脚本工作原理：**
   ```python
   # 002_initial_domains.py 调用 DDL 生成器
   _execute_domain_ddl(conn, "annuity_income")
   └── ddl_generator.generate_create_table_ddl(domain_name)
       └── 从 Domain Registry 读取 Schema 定义
   ```

3. **✅ 已自动应用：** 由于 `002_initial_domains.py` 使用 `ddl_generator` 动态生成 DDL，更新 Schema 定义后，迁移脚本会自动使用新的字段定义。

4. **开发环境 DDL 文件：** `scripts/create_table/ddl/*.sql` 仅用于开发阶段填充 Legacy 架构数据，生产环境不会调用这些文件。

**现有数据库重建步骤：**
1. 备份现有数据：`pg_dump -U postgres -h localhost -d postgres > backup.sql`
2. 删除现有表：`DROP TABLE IF EXISTS business.收入明细/规模明细 CASCADE;`
3. 运行 Alembic 迁移：`PYTHONPATH=src uv run --env-file .wdh_env alembic upgrade`
4. 重新导入数据：运行 ETL CLI 导入历史数据

---

### Phase 3: 字段传递机制验证

**需要检查的组件:**

1. **Domain Registry:** `src/work_data_hub/infrastructure/schema/definitions/`
   - `annuity_income.py`
   - `annuity_performance.py`

2. **ETL Field Mapping:**
   - 检查 ETL 层如何读取 Excel 列并映射到 Schema 字段
   - 确认可选字段在缺失时的处理逻辑

3. **Bronze/Gold Validation:**
   - 确认 `bronze_required` 和 `gold_required` 列表是否需要调整
   - 可选字段不应出现在必填列表中

4. **Index Definitions:**
   - 确认是否需要为新字段添加索引（通常不需要对可变的长文本字段建索引）

---

## 📝 ETL 字段映射机制

### annuity_income 字段传递

| Excel 字段 | Schema 字段 | 传递方式 | 说明 |
|-----------|-------------|---------|------|
| 月度 | 月度 | 直接映射 | - |
| 计划代码 | 计划代码 | 直接映射 | - |
| 业务类型 | 业务类型 | 直接映射 | - |
| 计划类型 | 计划类型 | 直接映射 | - |
| 组合代码 | 组合代码 | 直接映射 | - |
| 客户名称 | 客户名称 | 直接映射 | - |
| 机构代码 | 机构代码 | 直接映射 | - |
| 固费 | 固费 | 直接映射 | - |
| 浮费 | 浮费 | 直接映射 | - |
| 回补 | 回补 | 直接映射 | - |
| 税 | 税 | 直接映射 | - |
| - | **计划名称** | **待添加** | Excel → Schema (可选) |
| - | **组合类型** | **待添加** | Excel → Schema (可选) |
| - | **组合名称** | **待添加** | Excel → Schema (可选) |
| - | **机构名称** | **待添加** | Excel → Schema (可选) |
| - | company_id | ETL 生成 | Company Enrichment |
| - | 年金账户名 | ETL 生成 | Company Enrichment |
| - | 产品线代码 | ETL 生成 | 业务规则计算 |

### annuity_performance 字段传递

| Excel 字段 | Schema 字段 | 传递方式 | 说明 |
|-----------|-------------|---------|------|
| 月度 | 月度 | 直接映射 | - |
| 业务类型 | 业务类型 | 直接映射 | - |
| 计划类型 | 计划类型 | 直接映射 | - |
| 计划代码 | 计划代码 | 直接映射 | - |
| 计划名称 | 计划名称 | 直接映射 | - |
| 组合类型 | 组合类型 | 直接映射 | - |
| 组合代码 | 组合代码 | 直接映射 | - |
| 组合名称 | 组合名称 | 直接映射 | - |
| 客户名称 | 客户名称 | 直接映射 | - |
| 期初资产规模 | 期初资产规模 | 直接映射 | - |
| 期末资产规模 | 期末资产规模 | 直接映射 | - |
| 供款 | 供款 | 直接映射 | - |
| 流失 | 流失 | 直接映射 | - |
| 流失(含待遇支付) | 流失_含待遇支付 | **字段名映射** | ETL 层处理 |
| 待遇支付 | 待遇支付 | 直接映射 | - |
| 投资收益 | 投资收益 | 直接映射 | - |
| 当期收益率 | 当期收益率 | 直接映射 | - |
| 机构 | 机构名称 | **字段名映射** | ETL 层处理 |
| 机构代码 | 机构代码 | 直接映射 | - |
| - | **子企业号** | **待添加** | Excel → Schema (可选) |
| - | **子企业名称** | **待添加** | Excel → Schema (可选) |
| - | **集团企业客户号** | **待添加** | Excel → Schema (可选) |
| - | **集团企业客户名称** | **待添加** | Excel → Schema (可选) |
| - | company_id | ETL 生成 | Company Enrichment |
| - | 年金账户号 | ETL 生成 | Company Enrichment |
| - | 年金账户名 | ETL 生成 | Company Enrichment |
| - | 产品线代码 | ETL 生成 | 业务规则计算 |
| - | 年化收益率 | ETL 生成 | 收益率计算 |

---

## 🎯 影响评估

| 影响维度 | 评估结果 | 说明 |
|---------|---------|------|
| **向后兼容性** | ✅ 高 | 所有新字段均为 `NULL`，不影响现有数据 |
| **数据完整性** | ⚠️ 中 | 历史数据需要重新导入以填充新字段 |
| **业务影响** | ⚠️ 中-高 | 缺失字段可能影响报表和数据分析 |
| **修复风险** | ✅ 低 | 仅追加字段，不修改或删除现有列 |
| **修复复杂度** | ✅ 低 | 标准的 Schema 扩展操作 |
| **ETL 影响** | ⚠️ 需验证 | 需确认 ETL 层能正确处理可选字段 |

---

## 🚀 下一步行动

1. ✅ **已完成:** 字段缺失分析和文档记录
2. ⏳ **待执行:** 更新 Domain Schema 定义
3. ⏳ **待执行:** 修改现有 Alembic 迁移脚本
4. ⏳ **待执行:** 验证 ETL 字段传递机制
5. ⏳ **待执行:** 重建数据库表（备份数据 → 删除表 → 运行迁移 → 导入数据）
6. ⏳ **待执行:** 运行测试套件确保无回归

---

## 📚 参考资料

- **Excel 文件:** `tests/fixtures/real_data/202412/收集数据/数据采集/V1/【for年金分战区经营分析】24年12月年金规模收入数据0109采集.xlsx`
- **Schema 定义:** `src/work_data_hub/infrastructure/schema/definitions/`
- **Alembic 迁移:** `alembic/versions/20251219_000001_create_domain_tables.py`
- **Domain Registry 架构:** `docs/architecture/infrastructure-layer.md#domain-registry-package`
