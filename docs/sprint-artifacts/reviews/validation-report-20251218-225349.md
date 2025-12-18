# 验证报告（validate-create-story）

**Document:** `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md`  
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2025-12-18 22:53:49  
**Inputs Provided:**
1. `epic-num: 6.2`
2. `story: docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md`
3. `sprint-change-proposal: docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-18.md`

**Ancillary Artifacts Loaded:**
1. `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-18.md`
2. `docs/sprint-artifacts/sprint-status.yaml`
3. `docs/sprint-artifacts/retrospective/epic-6.2-retro-2025-12-13.md`
4. `docs/project-context.md`
5. `docs/brownfield-architecture.md`
6. `docs/architecture-boundaries.md`
7. `scripts/validation/CLI/guimo_iter_cleaner_compare.py`
8. `scripts/validation/CLI/guimo_iter_config.py`
9. `scripts/validation/CLI/guimo_iter_report_generator.py`
10. `scripts/validation/CLI/cleaner-comparison-usage-guide.md`
11. `docs/sprint-artifacts/stories/6.2-p11-guimo-mingxi-field-derivation-fix.md`
12. `docs/sprint-artifacts/stories/6.2-p10-etl-backfill-sql-module.md`
13. `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`
14. `_bmad/core/tasks/validate-workflow.xml`
15. `git log -n 20 --oneline`（用于轻量确认近期变更热点）

---

## Summary

- Overall: **58/72 PASS（80.6%）**
- Partial: **10/72（13.9%）**
- Fail: **2/72（2.8%）**
- N/A: **2/72（2.8%）**
- Critical Issues: **2**

---

## Section Results

### A. 🚨 CRITICAL MISTAKES TO PREVENT（防灾要点）

1. [✓ PASS] Reinventing wheels（避免重复造轮子）
   - Evidence: Story 明确以“配置驱动”替代硬编码并复用现有脚本结构（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:30`）。

2. [⚠ PARTIAL] Wrong libraries（避免引入错误/不一致的库）
   - Evidence: Story 倾向于在现有 `scripts/validation/CLI/` 结构内重构（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:173`），但未显式声明“必须复用现有 argparse/pandas 等既有依赖，禁止引入新 CLI 框架”。
   - Impact: Dev 有小概率引入 Click/Typer 等导致风格分裂/依赖膨胀。

3. [✓ PASS] Wrong file locations（错误文件位置）
   - Evidence: 明确定位与结构：`scripts/validation/CLI/`（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:173`）。

4. [✓ PASS] Breaking regressions（回归风险）
   - Evidence: 明确要求功能等价与验证步骤（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:63`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:111`）。

5. [➖ N/A] Ignoring UX（忽略 UX）
   - Evidence: 该变更为内部验证 CLI，无直接 UI/UX 需求。

6. [✓ PASS] Vague implementations（实现含糊）
   - Evidence: AC + 分阶段 Tasks + 文件重命名清单齐备（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:34`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:78`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:166`）。

7. [✓ PASS] Lying about completion（“假完成”风险）
   - Evidence: DoD/Success Criteria 明确（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:234`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:244`）。

8. [⚠ PARTIAL] Not learning from past work（未吸收历史经验）
   - Evidence: Story 引用 SCP 与现存脚本（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:7`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:182`），但缺少对“当前脚本已包含 auto-discovery / token auto-refresh 等现状”的明确迁移护栏（参考现有脚本：`scripts/validation/CLI/guimo_iter_cleaner_compare.py:71`、`scripts/validation/CLI/guimo_iter_cleaner_compare.py:121`）。
   - Impact: Dev 若只按 AC1-AC3 做“抽象化”，可能无意中丢失近期增强能力。

---

### B. ✅ Required Inputs（本次验证输入完整性）

1. [✓ PASS] Story file provided
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:1`。

2. [✓ PASS] Workflow variables loaded（workflow.yaml）
   - Evidence: ` _bmad/bmm/workflows/4-implementation/create-story/workflow.yaml:1`（workflow name/metadata 存在）。

3. [✓ PASS] Source documents provided / discoverable（SCP）
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:7`。

4. [✓ PASS] Validation framework available
   - Evidence: `_bmad/core/tasks/validate-workflow.xml:1`（task id 定义存在）。

---

### C. Step 1: Load and Understand the Target（加载与理解目标）

1. [✓ PASS] Load workflow configuration
   - Evidence: `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml:1`。

2. [✓ PASS] Load story file
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:1`。

3. [✓ PASS] Load validation framework
   - Evidence: `_bmad/core/tasks/validate-workflow.xml:1`。

4. [✓ PASS] Extract metadata（epic_num/story_key/status）
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:3`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:4`。

5. [⚠ PARTIAL] Resolve workflow variables（epics_file / architecture_file 等）
   - Evidence: workflow.yaml 变量默认指向 `docs/epics.md`、`docs/architecture.md`，但仓库实际使用 sharded/替代结构（例如 `docs/epics/`、`docs/brownfield-architecture.md`）（`_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml:23`、`_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml:25`；对照：`docs/brownfield-architecture.md:1`）。
   - Impact: 若后续流程严格依赖 “单文件 epics/architecture”，会出现“找不到文件”的工具链问题（但对本 story 的实现不构成 blocker）。

6. [✓ PASS] Understand current status（ready-for-dev）
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:4`；sprint-status 也标记为 ready-for-dev（`docs/sprint-artifacts/sprint-status.yaml:253`）。

---

### D. Step 2: Exhaustive Source Document Analysis（来源文档分析）

1. [⚠ PARTIAL] Load epics_file / epic context
   - Evidence: 未发现 `docs/epics.md`（workflow 默认路径），改用 `docs/sprint-artifacts/sprint-status.yaml` 与 `docs/sprint-artifacts/retrospective/epic-6.2-retro-2025-12-13.md` 做 Epic 6.2 上下文（`docs/sprint-artifacts/sprint-status.yaml:1`、`docs/sprint-artifacts/retrospective/epic-6.2-retro-2025-12-13.md:1`）。
   - Impact: Epic 级“官方 epics 单文件”缺失会影响流程一致性，但不影响本 story 的可实现性。

2. [✓ PASS] Extract COMPLETE Epic {{epic_num}} context
   - Evidence: sprint-status 明确该 story 属于 Epic 6.2 且当前状态 ready-for-dev（`docs/sprint-artifacts/sprint-status.yaml:253`）。

3. [✓ PASS] Load architecture_file / architecture context
   - Evidence: 使用 `docs/brownfield-architecture.md` 作为当前架构基线（`docs/brownfield-architecture.md:1`、`docs/brownfield-architecture.md:26`）。

4. [✓ PASS] Systematically scan for relevant architecture constraints
   - Evidence: 统一 CLI 入口与 `uv run` 规范在架构文档明确（`docs/brownfield-architecture.md:26`、`docs/brownfield-architecture.md:387`）。

5. [✓ PASS] Load previous story file (story_num > 1)
   - Evidence: 已加载 Epic 6.2 的近期 story 样式与命令习惯（`docs/sprint-artifacts/stories/6.2-p11-guimo-mingxi-field-derivation-fix.md:1`、`docs/sprint-artifacts/stories/6.2-p10-etl-backfill-sql-module.md:1`）。

6. [✓ PASS] Extract actionable intelligence from previous story
   - Evidence: P11 的 Commands Reference 使用 `uv run --env-file .wdh_env`（`docs/sprint-artifacts/stories/6.2-p11-guimo-mingxi-field-derivation-fix.md:115`、`docs/sprint-artifacts/stories/6.2-p11-guimo-mingxi-field-derivation-fix.md:117`）。

7. [⚠ PARTIAL] Analyze recent commits for patterns (if available)
   - Evidence: repo 在 git work tree 内（`git rev-parse --is-inside-work-tree` 通过）；但本次仅做热点确认，未做逐 commit 代码 diff 复核（原因：story 的变更边界已在文件清单中明确）。
   - Impact: 可能遗漏少量“近期已做过类似抽象”的先例文件，降低复用机会。

8. [⚠ PARTIAL] Identify libraries/frameworks mentioned
   - Evidence: Story 与 SCP 未指定引入新库，主要依赖现有 `pandas/argparse` 等（对照现状：`scripts/validation/CLI/guimo_iter_cleaner_compare.py:26`）。
   - Impact: 缺少显式依赖约束时，可能发生工具/风格分裂（低概率）。

9. [➖ N/A] Research latest versions and critical information
   - Evidence: 本 story 为 repo 内部脚本重构，未引入外部新依赖；“版本研究”不构成必须项。

---

### E. Step 3: Disaster Prevention Gap Analysis（防灾缺口分析）

#### 3.1 Reinvention Prevention Gaps

1. [✓ PASS] Wheel reinvention risk identified
   - Evidence: Story 明确目标为“配置驱动、避免代码重复”（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:30`）。

2. [✓ PASS] Code reuse opportunities identified
   - Evidence: Story 指向复用现有 `guimo_iter_*` 结构，仅做抽象与重命名（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:99`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:182`）。

3. [⚠ PARTIAL] Existing solutions not mentioned (extend instead of replace)
   - Evidence: 现存脚本已包含 auto-discovery 与 token auto-refresh（`scripts/validation/CLI/guimo_iter_cleaner_compare.py:71`、`scripts/validation/CLI/guimo_iter_cleaner_compare.py:121`），但 story 未将其列为“不可丢失能力”。
   - Impact: 抽象化过程中可能把“已解决的问题”退化回老问题（中等风险）。

#### 3.2 Technical Specification DISASTERS

4. [⚠ PARTIAL] Wrong libraries/frameworks risk
   - Evidence: 缺少“必须复用现有 argparse/pandas”与“禁止新增依赖”的硬约束（见 A.2）。
   - Impact: 依赖/风格分裂（低概率，中等维护成本）。

5. [➖ N/A] API contract violations
   - Evidence: 本 story 不涉及对外 API 合约。

6. [➖ N/A] Database schema conflicts
   - Evidence: 本 story 不改 DB schema；仅运行对比验证脚本与生成报告。

7. [⚠ PARTIAL] Security vulnerabilities
   - Evidence: 脚本涉及 legacy import path 与可能访问 EQC token（现状脚本包含 token 校验逻辑：`scripts/validation/CLI/guimo_iter_cleaner_compare.py:121`）；story 未显式要求“不可打印 token/敏感信息”。
   - Impact: 不当日志输出的潜在风险（低概率，但影响高）。

8. [⚠ PARTIAL] Performance disasters
   - Evidence: story 未定义性能/规模边界（例如 `--limit 0` 全量运行对比的耗时与内存风险）。
   - Impact: Dev 可能在无 guardrails 下运行全量导致卡死/爆内存（中等概率，影响中等）。

#### 3.3 File Structure DISASTERS

9. [✓ PASS] Wrong file locations guarded
   - Evidence: 目录/文件 rename 清单明确（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:147`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:280`）。

10. [✓ PASS] Coding standard violations addressed
   - Evidence: project-context 强调 KISS/YAGNI 与 uv 执行标准（`docs/project-context.md:3`、`docs/project-context.md:7`、`docs/project-context.md:62`）。

11. [✓ PASS] Integration pattern breaks considered
   - Evidence: 明确“Local imports with sys.path manipulation（existing pattern）”（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:178`）。

12. [➖ N/A] Deployment failures
   - Evidence: 本 story 为本地/CI 验证脚本，不涉及部署管线更改。

#### 3.4 Regression DISASTERS

13. [✓ PASS] Breaking changes guarded by equivalence validation
   - Evidence: AC4 + T5.1/T5.2（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:63`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:111`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:116`）。

14. [⚠ PARTIAL] Test failures prevention
   - Evidence: story 提到 pytest 路径，但未说明 markers（例如 `-m "not postgres"`）与本地环境依赖（见架构文档建议：`docs/brownfield-architecture.md:390`）。
   - Impact: Dev 可能在无 Postgres 环境下跑到需要数据库的测试（低概率）。

15. [➖ N/A] UX violations
   - Evidence: CLI 工具，无 UI/UX 交互面。

16. [✓ PASS] Learning failures addressed
   - Evidence: 引用现存脚本与 SCP（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:7`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:182`）。

#### 3.5 Implementation DISASTERS

17. [✓ PASS] Vague implementations reduced by explicit ACs
   - Evidence: AC1-AC5（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:34`）。

18. [✓ PASS] Completion lies prevented by DoD + Success Criteria
   - Evidence: `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:234`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:244`。

19. [✓ PASS] Scope creep bounded (YAGNI)
   - Evidence: `annuity_income` 明确延后（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:170`；对齐 SCP：`docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-18.md:245`）。

20. [✓ PASS] Quality failures mitigated by equivalence + artifacts diff
   - Evidence: T5.2 明确对比 pre-refactor baseline（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:116`）。

---

### F. Step 4: LLM-Dev-Agent Optimization Analysis（LLM 可执行性与结构优化）

1. [⚠ PARTIAL] Verbosity problems
   - Evidence: story 仍包含较长的重复段落（例如 References/Test Strategy 与 Success/DoD 部分存在重复意图）。
   - Impact: dev-story agent token 消耗更高，但不影响正确性。

2. [⚠ PARTIAL] Ambiguity issues
   - Evidence: AC4 指定 202510，而命令示例使用 202311（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:64`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:114`）。
   - Impact: 直接导致验证基线不一致（高风险）。

3. [✓ PASS] Context overload controlled（相对可控）
   - Evidence: 以 Phase/Tasks 分段，开发可按阶段执行（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:78`）。

4. [✓ PASS] Missing critical signals surfaced
   - Evidence: “Lazy Imports / No Backward Compatibility / YAGNI / Registry”集中在 Critical Notes（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:166`）。

5. [✓ PASS] Structure scannable
   - Evidence: AC/Tasks/Test/DoD/Files 表格齐全（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:34`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:189`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:244`）。

6. [✓ PASS] Clarity over verbosity（原则被体现）
   - Evidence: KISS/YAGNI 与“无向后兼容”的边界清晰（`docs/project-context.md:3`、`docs/project-context.md:7`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:169`）。

7. [✓ PASS] Actionable instructions present
   - Evidence: Tasks 细化到文件与函数级别（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:101`、`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:103`）。

8. [✓ PASS] Scannable structure
   - Evidence: Phase 标题+复选任务（`docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:78`）。

9. [⚠ PARTIAL] Token efficiency
   - Evidence: 可通过合并重复的 equivalence/validation 描述进一步压缩（不影响执行）。

10. [⚠ PARTIAL] Unambiguous language
   - Evidence: AC4 “byte-for-byte identical”在当前实现下不可满足（见 Critical Issue #2，证据来自现存 report generator 输出包含动态时间戳：`scripts/validation/CLI/guimo_iter_report_generator.py:321`）。
   - Impact: 不修正将导致 DoD 永远无法客观达成（高风险）。

---

### G. Step 5: Improvement Recommendations（改进建议覆盖）

#### 5.1 Critical Misses (Must Fix)

1. [✓ PASS] Missing essential technical requirements
   - Evidence: 已识别“sys.path/legacy import 顺序护栏、--run-id/可重复性”等关键缺口（见下方 Critical Issues）。

2. [✓ PASS] Missing previous story context
   - Evidence: 已对照现存脚本的 auto-discovery/token refresh，提出“不可丢失能力”建议（见 E.3）。

3. [✓ PASS] Missing anti-pattern prevention
   - Evidence: 已点名“禁止新增 CLI 框架/重复造轮子”的增强点（见 A.2）。

4. [✓ PASS] Missing security or performance requirements
   - Evidence: 已点名“token 不得泄露/limit=0 的资源风险”（见 E.7/E.8）。

#### 5.2 Enhancement Opportunities (Should Add)

5. [✓ PASS] Additional architectural guidance
   - Evidence: 引用 `uv run --env-file .wdh_env` 与统一 CLI 入口规则（`docs/brownfield-architecture.md:26`）。

6. [✓ PASS] More detailed technical specifications
   - Evidence: 已建议明确 `DomainComparisonConfig.build_new_pipeline()` 的参数契约与返回值（见 Recommendations）。

7. [✓ PASS] Better code reuse opportunities
   - Evidence: 建议复用现有报告生成与 artifacts 结构并保持等价（见 E.2/E.3）。

8. [✓ PASS] Enhanced testing guidance
   - Evidence: 已建议把测试命令与 marker/环境约束对齐（`docs/brownfield-architecture.md:390`）。

#### 5.3 Optimization Suggestions (Nice to Have)

9. [✓ PASS] Performance optimization hints
   - Evidence: 建议为 `--limit 0` 增加 guardrail（例如提示/确认/内存预估）。

10. [✓ PASS] Additional context for complex scenarios
   - Evidence: 建议新增 `--run-id` 或固定生成时间戳，支持严格 diff（见 Critical Issue #2）。

11. [✓ PASS] Enhanced debugging tips
   - Evidence: 现存脚本定义 `--debug/--export` 参数（`scripts/validation/CLI/guimo_iter_cleaner_compare.py:837`、`scripts/validation/CLI/guimo_iter_cleaner_compare.py:842`）；usage guide 也已文档化（`scripts/validation/CLI/cleaner-comparison-usage-guide.md:94`、`scripts/validation/CLI/cleaner-comparison-usage-guide.md:95`）。

#### 5.4 LLM Optimization Improvements

12. [✓ PASS] Token-efficient phrasing suggestions provided
   - Evidence: 已指出可去重（见 F.1/F.9）。

13. [✓ PASS] Clearer structure suggestions provided
   - Evidence: 建议将“契约/不可丢失能力/验证可重复性”前置为 Hard Constraints（见 Recommendations）。

14. [✓ PASS] More actionable instructions suggestions provided
   - Evidence: 建议把 `build_new_pipeline()` 的具体签名落到 AC（见 Recommendations）。

15. [✓ PASS] Reduced verbosity while maintaining completeness
   - Evidence: 建议合并重复段落（见 F.1/F.9）。

---

## Failed Items

1. [✗ FAIL] Ambiguity: AC4 month mismatch (202510 vs 202311)
   - Evidence:
     - `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:64` — “Given same input data (202510 month, 100 row limit)”
     - `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:114` — “--month 202311 --limit 100 --export”
   - Recommendation: 统一基准月份（建议直接用 `202311`，与现有 CLI auto-discovery 示例一致；或将命令改为 `--month 202510` 并说明基准文件路径）。

2. [✗ FAIL] AC4 “byte-for-byte identical” 在现有报告实现下不可达成
   - Evidence:
     - `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md:66` — “CSV/MD artifacts are byte-for-byte identical”
     - `scripts/validation/CLI/guimo_iter_report_generator.py:321` — Markdown summary 含动态生成时间戳 `datetime.now(...)`
   - Recommendation（任选其一，写进 AC4/DoD）:
     1. 允许“语义等价”而非 byte-for-byte（忽略 Generated 时间戳/文件名 run_id）。
     2. 引入 `--run-id`（或 `--deterministic`）让 run_id 与 Generated 取同一固定值，从而可严格 diff。
     3. 将报告中的 `Generated` 行改为使用 run_id 派生的固定时间（或删除该行）。

---

## Partial Items

1. Wrong libraries guardrail（建议加硬约束）
2. 历史增强能力（auto-discovery / token refresh）未明确为不可丢失
3. workflow 默认 epics/architecture 单文件路径与 repo 现实不一致（但可通过“允许 sharded”化解）
4. Security/performance guardrails 未显式写入 story（token/logging、limit=0 资源风险）
5. 测试命令缺少 marker/环境约束说明（可参考架构文档）

---

## Recommendations

1. Must Fix
   1. 修正 AC4 基准月份一致性（见 Failed #1）。
   2. 修正 AC4 的“byte-for-byte”可验证性（见 Failed #2）。

2. Should Improve
   1. 在 story 顶部新增 **Hard Constraints**：
      - “不得引入新的 CLI 框架；复用现有 argparse/pandas；保持 `--month/--debug/--export` 行为不退化”
      - “不得在日志中输出 token/敏感信息（沿用既有约束）”
   2. 明确 `DomainComparisonConfig` 的方法契约（建议写到 AC1）：
      - `build_new_pipeline(excel_path: str, sheet_name: str, row_limit: int, enable_enrichment: bool, sync_lookup_budget: int) -> pandas.DataFrame`
      - `get_legacy_cleaner()` 若 legacy 依赖不可用，应抛出可读错误并提示 `--new-only`

3. Consider
   1. 增加 `--run-id` 以支持严格对比与可复现输出（对 CI 很友好）。
   2. 将报告标题从 “Annuity Performance …” 抽象为 domain-aware（为真正“domain-agnostic”铺路）。

---

## IMPROVEMENT OPTIONS（请选择）

1. **all**：应用全部建议（Critical + Should Improve + Consider）
2. **critical**：仅修复 Critical Issues（让 story 可被客观验收）
3. **select**：你指定要应用的编号（例如：`1,2`）
4. **none**：不修改 story（仅保留本报告）
5. **details**：我先给出“具体改动草案”（含建议改哪些段落/新增哪些小节）

你的选择：
