# 验证报告（validate-create-story）

**Document:** `docs/sprint-artifacts/stories/6.2-p7-enterprise-schema-consolidation.md`  
**Checklist:** `.bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2025-12-14 23:34:21  
**Inputs Provided:**
1. `epic-num: 6.2`
2. `story: docs/sprint-artifacts/stories/6.2-p7-enterprise-schema-consolidation.md`
3. `sprint-change-proposal: docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-api-full-coverage.md`

**Ancillary Artifacts Loaded:**
1. `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-api-full-coverage.md`
2. `docs/sprint-artifacts/sprint-status.yaml`
3. `docs/sprint-artifacts/retrospective/epic-6.2-retro-2025-12-13.md`
4. `docs/project-context.md`
5. `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py`
6. `io/schema/migrations/versions/20251214_000002_add_raw_data_to_base_info.py`
7. `io/schema/migrations/versions/20251214_000003_add_cleansing_status_to_business_info.py`
8. `tests/integration/migrations/test_enterprise_schema_migration.py`
9. `.bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`

---

## Summary

1. **对齐度（与 Sprint Change Proposal）**：✅ 高（目标、范围、依赖关系一致）
2. **可执行性（给 Dev 的“无歧义指令”）**：⚠️ 中（关键迁移策略与列映射仍有歧义）
3. **风险等级**：🚨 高（若不修正，极易导致“改了 migration 但环境不生效 / 迁移链无法在空库跑通 / 表字段命名冲突”）
4. **建议状态**：从 `ready-for-dev` 降为 `drafted`，修复“关键问题”后再恢复 `ready-for-dev`

---

## 🚨 Critical Issues（Must Fix）

1. **“重构旧 migration”与“已存在环境”之间的行为未被写清（高概率返工）**
   1. 当前故事要求“重构 `20251206_000001_create_enterprise_schema.py`”，以移除 `company_master` 并创建/扩展 `base_info` 等表。
   2. 但 Alembic 对“已应用过该 revision 的数据库”不会重跑该文件：这会导致“代码改了，但现有 dev/CI DB 完全不变”。
   3. **必须在故事中明确二选一策略：**
      a. **策略 A（推荐）**：明确要求开发者“销毁并重建 dev DB（或在 CI 使用空库）”，并把该动作写进 Validation/DoD。  
      b. **策略 B**：新增一个**新 migration**（而非改旧文件）来执行 DROP/ALTER/CREATE，让已存在环境也能演进到新 schema。

2. **当前 migration 链在“空库”场景下存在真实断裂点，故事需要把“修复链路”写成硬约束**
   1. 仓库现状：`20251214_000002_add_raw_data_to_base_info.py` 与 `20251214_000003_add_cleansing_status_to_business_info.py` 都假设 `enterprise.base_info` / `enterprise.business_info` 已存在。
   2. 但在 `io/schema/migrations/versions/` 中并没有任何 migration 创建这两张表（base_info/business_info）。
   3. 结论：**仅靠 migrations，空库 `alembic upgrade head` 可能失败**（除非外部提前导入 legacy 表）。
   4. 故事必须把目标定义为：“在空库从 0 → head 时，链路可跑通，并创建完整的 base_info/business_info/biz_label”。

3. **`archive_base_info` 列名存在明显“同义/重复”与“大小写/下划线混用”，需要明确最终落库规范**
   1. 参考列清单中同时出现：`registeredStatus` 与 `registered_status`、`companyFullName` 与 `company_full_name`、`companyId` 与 `company_id`。
   2. 这些会导致：
      a. 迁移实现时“到底要不要同时建两列”产生歧义；  
      b. SQLAlchemy/Alembic 对带大写字母列名的 quoting 规则不一致时易踩坑；  
      c. 代码侧当前已依赖 `"companyFullName"` 与 `unite_code`（见 `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` 的 INSERT）。
   3. 故事必须补充一个“**最终列名规范表**”：哪些列必须保留 camelCase（例如 `"companyFullName"`）、哪些统一 snake_case、哪些重复列被合并/保留其一，以及理由（对齐 legacy vs 对齐现有代码）。

4. **测试基线未更新：现有迁移集成测试仍把 `company_master` 作为必备（会直接失败或误导 Dev）**
   1. `tests/integration/migrations/test_enterprise_schema_migration.py` 目前明确验证 `company_master` 存在与结构（AC2）。
   2. P7 目标是移除 `company_master` 并把重心转向 `base_info/business_info/biz_label`。
   3. 故事必须在“Key Files / Tasks / DoD”中显式加入：更新该测试用例（删除 company_master 断言，新增 base_info/business_info/biz_label 的结构断言）。

---

## Alignment Check（与 Sprint Change Proposal 对齐）

1. **目标一致**：都聚焦于“补齐 EQC API 覆盖（findDepart/findLabels）所需的 schema 完整性”，并对齐 Legacy `archive_base_info`。
2. **拆分一致**：P7=Schema、P8=API、P9=Cleansing 的依赖链与提案一致。
3. **不一致/需补充说明点**：提案与故事都强调“项目未部署可重构 migration”，但未明确“已有 DB/CI 的落地执行策略”（见 Critical Issue #1）。

---

## ⚡ Enhancement Opportunities（Should Add）

1. **明确 schema 版本化策略**：给出“空库初始化（CI/新 dev）”与“已有数据库（本地/共享）”两条路径的执行步骤。
2. **列类型映射表**：对 37 列给出“推荐类型 + 允许为空 + 来源字段（search/findDepart/findLabels）”，避免开发者凭感觉定类型。
3. **索引与约束清单**：把 AC8 的“appropriate indexes”具体化（至少：`company_id` FK 索引、常用查询字段索引、必要的 unique/nullable 约束）。
4. **明确 `raw_data` 与新增 raw 字段的关系**：当前已存在 `raw_data`（P5），P7 又新增 `raw_business_info/raw_biz_label`；建议在 story 中说明三者分别存什么，避免重复存储与误用。

---

## ✨ Optimizations（Nice to Have）

1. **减少“长 SQL 片段”带来的误抄风险**：把 DDL 片段改为“最终列清单 + 关键差异点 + 参考位置（legacy/fixtures）”，让 Dev 以 migration 为单一真相来源。
2. **把关键硬约束前置**：把 “quoting/camelCase、空库可跑通、迁移策略 A/B 二选一”提升到 Hard Constraints 顶部。

---

## 🤖 LLM Optimization（Token Efficiency & Clarity）

1. 把“要改哪些文件”从段落文本变成一个短清单（migration + tests + docs），并在每个任务项后写“验收方式”。
2. 把 “37 columns” 从纯列表升级为表格（列名/类型/来源/是否必填/备注），降低歧义与 token 浪费。

---

## IMPROVEMENT OPTIONS（请选择）

1. **all**：应用全部建议（Critical + Enhancement + Optimizations）
2. **critical**：仅修复 Critical Issues（最小可用，恢复 `ready-for-dev` 的最低门槛）
3. **select**：你指定要应用的编号（例如：`1,3,4`）
4. **none**：不修改 story（仅保留本报告）
5. **details**：我先展开任一条建议的“具体改动草案”

你的选择：

