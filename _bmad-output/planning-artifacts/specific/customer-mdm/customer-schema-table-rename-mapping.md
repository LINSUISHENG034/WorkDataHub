# Customer Schema 表名统一重命名映射文档

> **目的**: 统一 `customer` schema 下的表名为中文，与 `business`、`mapping` schema 的命名策略保持一致，并修正语义不准确的表名。
>
> **日期**: 2026-02-26
>
> **决策背景**: 项目采用"双命名策略"——代码/CLI 使用英文 snake_case，数据库物理表名保留中文。当前 `customer` schema 下存在中英文混用，违反该策略。

---

## 1. 表名重命名映射

| # | 现有表名 | 新表名 | Schema | 语义说明 |
|---|---------|--------|--------|---------|
| T1 | `customer_plan_contract` | `客户年金计划` | customer | SCD Type 2 拉链表，核心合同状态追踪 |
| T2 | `fct_customer_product_line_monthly` | `客户业务月度快照` | customer | 产品线粒度月度快照事实表 |
| T3 | `fct_customer_plan_monthly` | `客户计划月度快照` | customer | 计划粒度月度快照事实表 |
| T4 | `当年中标` | `中标客户明细` | customer | 消除"当年"时间误导，实为跨期明细 |
| T5 | `当年流失` | `流失客户明细` | customer | 消除"当年"时间误导，实为跨期明细 |
| T6 | `年金关联公司` | `客户明细` | customer | 客户主数据维度表 |

### 1.1 mapping schema 兼容性视图

| 现有视图 | 处理方式 | 说明 |
|---------|---------|------|
| `mapping."年金客户"` → `customer."年金关联公司"` | 更新指向 | 改为 `mapping."年金客户"` → `customer."客户明细"` |
| `customer."年金客户"` → `customer."年金关联公司"` | 删除 | 项目未投产，无需保留兼容性视图 |

---

## 2. Seed 数据文件重命名

| 现有文件名 | 新文件名 | 路径 |
|-----------|---------|------|
| `年金关联公司.csv` | `客户明细.csv` | `config/seeds/001/` |

> 注：`当年中标` 和 `当年流失` 无 seed 文件（数据来自 Excel 加载），`客户年金计划` 和快照表无 seed 文件（数据由 ETL 生成）。

---

## 3. 触发器函数重命名映射

> **决策变更 (2026-02-26)**: 触发器/函数名保持英文不变，与索引、约束命名策略一致。仅函数体内的表名引用更新为中文新表名。理由：触发器/函数属于"代码级"标识符，应遵循英文命名约定。

### 3.1 updated_at 自动更新触发器

| # | 函数名 (不变) | 触发器名 (不变) | 所在表 (新) | 迁移脚本 |
|---|-------------|---------------|------------|---------|
| TR1 | `update_customer_plan_contract_timestamp()` | `update_customer_plan_contract_timestamp` | `客户年金计划` | 008 |
| TR2 | `update_fct_pl_monthly_timestamp()` | `update_fct_pl_monthly_timestamp` | `客户业务月度快照` | 009 |
| TR3 | `update_fct_plan_monthly_timestamp()` | `update_fct_plan_monthly_timestamp` | `客户计划月度快照` | 013 |
| TR4 | `update_annual_award_updated_at()` | `trg_annual_award_updated_at` | `中标客户明细` | 004 |
| TR5 | `update_annual_loss_updated_at()` | `trg_annual_loss_updated_at` | `流失客户明细` | 005 |

### 3.2 名称同步触发器（跨表联动）

| # | 函数名 (不变) | 触发器名 (不变) | 触发源表 | 函数体内引用表变更 | 迁移脚本 |
|---|-------------|---------------|---------|------------------|---------|
| TR6 | `sync_contract_customer_name()` | `trg_sync_contract_customer_name` | `客户明细` (ON UPDATE OF 客户名称) | `customer_plan_contract` → `"客户年金计划"` | 008 |
| TR7 | `sync_contract_plan_name()` | `trg_sync_contract_plan_name` | `mapping."年金计划"` (ON UPDATE OF 计划全称) | `customer_plan_contract` → `"客户年金计划"` | 008 |
| TR8 | `sync_fct_pl_customer_name()` | `trg_sync_fct_pl_customer_name` | `客户明细` (ON UPDATE OF 客户名称) | `fct_customer_product_line_monthly` → `"客户业务月度快照"` | 009 |
| TR9 | `sync_product_line_name()` | `trg_sync_product_line_name` | `mapping."产品线"` (ON UPDATE) | `customer_plan_contract` → `"客户年金计划"`, `fct_customer_business_monthly_status` → `"客户业务月度快照"` ⚠️ **修复既有 bug** | 011 |
| TR10 | `sync_fct_plan_customer_name()` | `trg_sync_fct_plan_customer_name` | `客户明细` (ON UPDATE OF 客户名称) | `fct_customer_plan_monthly` → `"客户计划月度快照"` | 013 |
| TR11 | `sync_fct_plan_plan_name()` | `trg_sync_fct_plan_plan_name` | `mapping."年金计划"` (ON UPDATE OF 计划全称) | `fct_customer_plan_monthly` → `"客户计划月度快照"` | 013 |

> ⚠️ **TR9 既有 bug 修复**: migration 011 中 `sync_product_line_name()` 函数体引用了不存在的旧表名 `fct_customer_business_monthly_status`，应为 `fct_customer_product_line_monthly`。本次重命名时一并修正为 `"客户业务月度快照"`。

---

## 4. 索引与约束命名映射

> 索引和约束名称使用英文短前缀，不包含完整表名，因此**无需重命名**。仅需确保 Alembic 脚本中 `sa.ForeignKeyConstraint` 的 `referred_table` 参数指向新表名。

### 4.1 外键约束（引用目标表变更）

| 约束名 | 所在表 (新) | 引用目标变更 | 迁移脚本 |
|-------|------------|------------|---------|
| `fk_contract_company` | `客户年金计划` | `"年金客户"(company_id)` → `"客户明细"(company_id)` | 008 |
| `fk_contract_product_line` | `客户年金计划` | 不变 (`mapping."产品线"`) | 008 |
| `fk_fct_pl_company` | `客户业务月度快照` | `"年金客户"(company_id)` → `"客户明细"(company_id)` | 009 |
| `fk_fct_pl_product_line` | `客户业务月度快照` | 不变 (`mapping."产品线"`) | 009 |
| `fk_fct_plan_company` | `客户计划月度快照` | `"年金客户"(company_id)` → `"客户明细"(company_id)` | 013 |
| `fk_fct_plan_product_line` | `客户计划月度快照` | 不变 (`mapping."产品线"`) | 013 |

### 4.2 唯一约束

| 约束名 | 所在表 (新) | 列 | 说明 |
|-------|------------|---|------|
| `uq_contract_version` | `客户年金计划` | `company_id, plan_code, product_line_code, valid_from` | 名称不变 (migration 012) |

---

## 5. 受影响的代码文件清单（必须修改）

### 5.1 Alembic 迁移脚本（直接修改，面向全新建库场景）

| 文件 | 涉及表 | 修改内容 |
|-----|-------|---------|
| `001_initial_infrastructure.py` | T6 | 表名 `年金客户` → `客户明细`，PK 约束名，兼容性视图 |
| `003_seed_static_data.py` | T6 | seed 文件名引用 `年金关联公司` → `客户明细` |
| `004_create_annual_award.py` | T4 | 表名 `当年中标` → `中标客户明细`，触发器 TR4 |
| `005_create_annual_loss.py` | T5 | 表名 `当年流失` → `流失客户明细`，触发器 TR5 |
| `006_create_business_type_view.py` | T4, T5 | 视图中引用的表名 |
| `007_add_customer_tags_jsonb.py` | T6 | 表名引用 |
| `008_create_customer_plan_contract.py` | T1, T6 | 表名、触发器 TR1/TR6/TR7、FK 引用 |
| `009_create_fct_customer_monthly_status.py` | T2, T6 | 表名、触发器 TR2/TR8、FK 引用 |
| `010_create_bi_star_schema.py` | T6 | dim_customer 视图中的表名引用 |
| `011_create_sync_product_line_trigger.py` | T1, T2 | 触发器 TR9 函数体 + 修复既有 bug |
| `012_fix_contract_unique_constraint.py` | T1 | 表名引用 |
| `013_create_fct_customer_plan_monthly.py` | T3, T6 | 表名、触发器 TR3/TR10/TR11、FK 引用 |

### 5.2 源代码（`src/work_data_hub/`）

| 文件 | 涉及表 |
|-----|-------|
| `customer_mdm/contract_sync.py` | T1 |
| `customer_mdm/snapshot_refresh.py` | T1, T2, T3, T4, T5 |
| `customer_mdm/year_init.py` | T1 |
| `customer_mdm/validation.py` | T1 |
| `customer_mdm/sql/close_old_records.sql` | T1 |
| `customer_mdm/sql/sync_insert.sql` | T1, T6 |
| `customer_mdm/sql/annual_cutover_close.sql` | T1 |
| `customer_mdm/sql/annual_cutover_insert.sql` | T1, T6 |
| `domain/annual_award/__init__.py` | T4 |
| `domain/annual_award/service.py` | T4 |
| `domain/annual_award/schemas.py` | T4 |
| `domain/annual_award/pipeline_builder.py` | T1, T4 |
| `domain/annual_award/models.py` | T4 |
| `domain/annual_award/helpers.py` | T1, T4 |
| `domain/annual_award/constants.py` | T4 |
| `domain/annual_loss/__init__.py` | T1, T5 |
| `domain/annual_loss/service.py` | T5 |
| `domain/annual_loss/schemas.py` | T5 |
| `domain/annual_loss/pipeline_builder.py` | T1, T5 |
| `domain/annual_loss/models.py` | T5 |
| `domain/annual_loss/helpers.py` | T5 |
| `domain/annual_loss/constants.py` | T5 |

### 5.3 配置文件（`config/`）

| 文件 | 涉及表 | 修改内容 |
|-----|-------|---------|
| `customer_status_rules.yml` | T4, T5 | source 表名引用 |
| `data_sources.yml` | T4, T5 | output_table 引用 |
| `domain_sources.yaml` | T4, T5 | 表名引用 |
| `foreign_keys.yml` | T4, T5, T6 | target_table `年金关联公司` → `客户明细` |

### 5.4 测试文件（`tests/`）

| 文件 | 涉及表 |
|-----|-------|
| `unit/customer_mdm/test_status_evaluator.py` | T4 |
| `unit/customer_mdm/test_customer_status_schema.py` | T4 |
| `unit/customer_mdm/test_annual_cutover.py` | T1 |
| `integration/customer_mdm/test_trigger_sync.py` | T1, T2, T3 |
| `integration/customer_mdm/test_status_fields.py` | T1 |
| `integration/customer_mdm/test_status_evaluation.py` | T4 |
| `integration/customer_mdm/test_hook_chain.py` | T2 |
| `integration/customer_mdm/test_e2e_pipeline.py` | T2, T3 |
| `integration/customer_mdm/conftest.py` | T4 |

### 5.5 辅助脚本（`scripts/`）

| 文件 | 涉及表 |
|-----|-------|
| `seed_data/seed_customer_plan_contract.py` | T1, T6 |
| `seed_data/export_seed_data.py` | T6 |
| `verify_contract_sync.py` | T1 |
| `check_customer_coverage.py` | T1, T6 |
| `analyze_sync_issues.py` | T1, T6 |
| `analyze_missing_records.py` | T1 |

### 5.6 历史迁移 SQL 脚本（`scripts/migrations/`）

| 文件 | 处理方式 |
|-----|---------|
| `add_contract_name_fields.sql` | 更新表名引用 |
| `rollback_annuity_customer_migration.sql` | 更新表名引用 |
| `rename_annuity_customer_table.sql` | 删除（已无意义，重命名逻辑已内化到 Alembic） |
| `migrate_fct_tables_2026-02-09.sql` | 更新表名引用 |

---

## 6. 不修改范围（明确排除）

| 范围 | 原因 |
|-----|------|
| `_bmad-output/` 下的规划文档、Story、Review 报告 | 历史规划产物，不影响运行 |
| `docs/` 下的文档 | 参考文档，可后续按需更新 |
| `_archived/` 下的归档迁移脚本 | 已归档，不在活跃迁移链中 |

---

## 7. 实施策略

### 7.1 核心原则

1. **直接修改现有 Alembic 脚本**：面向全新建库场景，不使用 `ALTER TABLE RENAME`
2. **现有数据库重建**：使用调整后的 Alembic 脚本直接创建，无需独立 SQL 迁移脚本
3. **无兼容性视图**：项目未投产，不保留旧名视图过渡

### 7.2 实施步骤（建议顺序）

| 步骤 | 内容 | 验证方式 |
|-----|------|---------|
| Step 1 | 修改 Alembic 迁移脚本 (001-013) 中的表名、触发器、FK | `alembic upgrade head` 在空库上成功 |
| Step 2 | 重命名 seed CSV 文件 + 更新 seed 脚本引用 | seed 数据正确加载 |
| Step 3 | 更新 `config/` 下所有 YAML 配置文件 | 配置校验通过 |
| Step 4 | 更新 `src/` 下所有 Python 和 SQL 源代码 | `uv run ruff check` + `uv run mypy` 通过 |
| Step 5 | 更新 `tests/` 下所有测试文件 | `uv run pytest tests/unit` 通过 |
| Step 6 | 更新 `scripts/` 下辅助脚本 | 脚本可正常执行 |
| Step 7 | 现有数据库重建验证 | drop schema + `alembic upgrade head` + seed + ETL 全流程 |
