# 验证报告（validate-create-story）

**Document:** `docs/sprint-artifacts/stories/6.2-p5-eqc-data-persistence-legacy-integration.md`  
**Checklist:** `.bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2025-12-14 11:46:12  
**Ancillary Artifacts Loaded:**
- `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-14-eqc-data-persistence.md`
- `docs/sprint-artifacts/reviews/pm-review-eqc-data-persistence-2025-12-14.md`
- `docs/sprint-artifacts/sprint-status.yaml`
- `docs/sprint-artifacts/retrospective/epic-6.2-retro-2025-12-13.md`
- `docs/project-context.md`
- `.bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`

---

## Summary

- Overall: 59/152 passed (38.8%)
- Partial: 65
- Failed: 0
- N/A: 28
- Critical Issues: 5

---

## 🚨 Critical Issues（Must Fix）

1. **`raw_response/raw_data` 在调用链中的“数据来源与传递方式”未被写清，且示例代码自相矛盾**
   - Story 示例在 `_cache_result()` 中使用 `raw_response`，但函数签名未体现该参数（Story L224-L236）。
   - 现有代码：`EqcProvider._cache_result(self, company_name, result)`（`src/work_data_hub/infrastructure/enrichment/eqc_provider.py` L341）当前无法获取 raw JSON。
   - 影响：开发者可能走错实现路径（把 raw JSON 塞进 `CompanyInfo` vs 改 `EQCClient` 返回类型 vs 改 `_call_api` 返回 tuple），导致返工与测试不稳定。

2. **CLI 执行标准与项目“uv 运行规范”不一致（容易造成环境/依赖/导入偏差）**
   - Story 命令使用 `uv run python -m ...`（Story L276-L299）。
   - 项目规范要求：`PYTHONPATH=src uv run` 且优先 `--env-file .wdh_env`，并“避免直接 python 调用”（`docs/project-context.md` L59-L72）。
   - 影响：不同机器/CI 上可能出现导入路径差异、配置未加载、脚本行为不一致。

3. **`company_master` “deprecate” 的含义与边界不清晰（易引入回归或误删表风险）**
   - Story 将其列为 In Scope（Story L44）并在 AC6 要求“Deprecate or reposition”（Story L60）。
   - 但仓库中仍存在大量 `company_master` 概念与文档/类型耦合（例如 `src/work_data_hub/infrastructure/enrichment/types.py` 对齐说明、多个 tech spec/epic 文档）。
   - 影响：开发者可能误解为“drop table / remove code paths”，导致历史故事/运行路径回归。

4. **“清洗框架”可能与现有 cleansing 基础设施产生重复/割裂，需要明确复用策略**
   - Story 计划新增 `src/work_data_hub/infrastructure/cleansing/rule_engine.py` 与 `config/cleansing_rules/business_info.yaml`（Story L207-L209、L67-L76、L295-L299）。
   - 现有项目已存在 `src/work_data_hub/infrastructure/cleansing/registry.py` + `.../settings/cleansing_rules.yml` 的配置驱动体系（见代码与历史 story/tech spec）。
   - 影响：同一“清洗”概念出现两套入口/配置格式，长期维护成本与使用混乱。

5. **Patch Story 的 Required AC 数量与 Phase 范围过大，存在“故事不可交付”的风险**
   - AC1-AC22 大量 Required（Story L55-L76），并且 Tasks 覆盖 Phase1-Phase5（Story L80+）。
   - 影响：开发时容易出现“只做 Phase1/2 但故事仍未达成 DoD”，导致状态管理与验收混乱。

---

## Alignment Check（与 Sprint Change Proposal 对齐）

### Identity & Scope
- Story 标题与目标与提案一致：均为“EQC Data Persistence & Legacy Table Integration”（Story L1-L12；Proposal L1-L7、L89-L95）。
- “Consolidate to base_info instead of company_master”的架构决策一致（Story L28-L34；Proposal L51-L58、L65-L82）。

### Acceptance Criteria 一致性
- AC1-AC22 与提案表格逐项对齐（Story L55-L76；Proposal L98-L121）。

---

## Checklist Results（152项，逐条）

> 说明：以下标记用于衡量“该 story 是否为 dev agent 提供了足够上下文与防灾护栏”。  
> `[✓]` PASS / `[⚠]` PARTIAL / `[✗]` FAIL / `[➖]` N/A

### A. 关键错误预防（Checklist L11-L18）

[✓] (Checklist L11) **Reinventing wheels** - Creating duplicate functionality instead of reusing existing  
Evidence: 提供“Existing Code Patterns to Follow”“Key Files to Modify”与复用约束（Story L196-L210、L211-L219、L220-L240）。

[⚠] (Checklist L12) **Wrong libraries** - Using incorrect frameworks, versions, or dependencies  
Evidence: 复用 SQLAlchemy/Dagster/uv 的大方向正确，但缺少版本/运行规范对齐（Story L258-L265、L276-L299；`docs/project-context.md` L59-L72）。

[✓] (Checklist L13) **Wrong file locations** - Violating project structure and organization  
Evidence: 明确列出目标文件路径与分层边界（Story L196-L210、L301-L308）。

[⚠] (Checklist L14) **Breaking regressions** - Implementing changes that break existing functionality  
Evidence: 有“Non-blocking cache”“Graceful degradation”约束（Story L211-L219、L237-L240），但 `company_master` deprecate 边界不清（Story L44、L60）。

[➖] (Checklist L15) **Ignoring UX** - Not following user experience design requirements  
Evidence: 本 story 为数据持久化/CLI/服务端能力，无 UX 范畴。

[⚠] (Checklist L16) **Vague implementations** - Creating unclear, ambiguous implementations  
Evidence: Phase1 任务清晰（Story L80-L99），但 raw_response 传递方式不清（Story L224-L236），deprecate 策略不清（Story L44、L60）。

[⚠] (Checklist L17) **Lying about completion** - Implementing incorrectly or incompletely  
Evidence: AC 很多且多 Phase（Story L55-L76、L80+），若不拆分/不明确“本 story 是否必须执行 full refresh”，存在“做了部分但 story 仍未完成”的风险。

[✓] (Checklist L18) **Not learning from past work** - Ignoring previous story learnings and patterns  
Evidence: 明确列出 6.2-P3 的 learnings（Story L309-L314）。

### B. 验证运行/输入与变量上下文（Checklist L36-L69）

[➖] (Checklist L36) The `{project_root}/.bmad/core/tasks/validate-workflow.xml` framework will automatically:  
Evidence: 验证框架说明项；不要求 story 覆盖。

[➖] (Checklist L37) Load this checklist file  
Evidence: 同上（验证框架说明项）。

[➖] (Checklist L38) Load the newly created story file (`{story_file_path}`)  
Evidence: 同上（验证框架说明项）。

[➖] (Checklist L39) Load workflow variables from `{installed_path}/workflow.yaml`  
Evidence: 同上（验证框架说明项）。

[➖] (Checklist L40) Execute the validation process  
Evidence: 同上（验证框架说明项）。

[✓] (Checklist L44) User should provide the story file path being reviewed  
Evidence: 本次验证输入已提供（见本报告 Document 字段）。

[✓] (Checklist L45) Load the story file directly  
Evidence: 已加载 `docs/sprint-artifacts/stories/6.2-p5-eqc-data-persistence-legacy-integration.md`（见本报告 Document 字段）。

[✓] (Checklist L46) Load the corresponding workflow.yaml for variable context  
Evidence: 已加载 `.bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`（见本报告 Ancillary Artifacts Loaded）。

[✓] (Checklist L47) Proceed with systematic analysis  
Evidence: 本报告包含 Critical Issues、Alignment、Checklist 逐项结果与建议。

[✓] (Checklist L51) **Story file**: The story file to review and improve  
Evidence: 已提供并验证（Story L1-L390）。

[✓] (Checklist L52) **Workflow variables**: From workflow.yaml (story_dir, output_folder, epics_file, architecture_file, etc.)  
Evidence: 已加载 workflow.yaml；但 `epics_file/architecture_file` 在项目中并非单一入口（见 Checklist L68/L80/L90 的标记与说明）。

[✓] (Checklist L53) **Source documents**: Epics, architecture, etc. (discovered or provided)  
Evidence: Story References 列出提案/PM review/retro/架构边界（Story L364-L373）。

[✓] (Checklist L54) **Validation framework**: `validate-workflow.xml` (handles checklist execution)  
Evidence: 已加载并按 checklist 思路执行（见本报告结构）。

[✓] (Checklist L64) 1. **Load the workflow configuration**: `{installed_path}/workflow.yaml` for variable inclusion  
Evidence: 已加载 `.bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`。

[✓] (Checklist L65) 2. **Load the story file**: `{story_file_path}` (provided by user or discovered)  
Evidence: 已加载 story（Story L1-L390）。

[✓] (Checklist L66) 3. **Load validation framework**: `{project_root}/.bmad/core/tasks/validate-workflow.xml`  
Evidence: 已加载 `.bmad/core/tasks/validate-workflow.xml`。

[✓] (Checklist L67) 4. **Extract metadata**: epic_num, story_num, story_key, story_title from story file  
Evidence: Epic=6.2（Story L3）；Story Key/Title=6.2-P5 / “EQC Data Persistence & Legacy Table Integration”（Story L1）。

[⚠] (Checklist L68) 5. **Resolve all workflow variables**: story_dir, output_folder, epics_file, architecture_file, etc.  
Evidence: workflow.yaml 默认变量（如 `docs/epics.md` / `docs/architecture.md`）在本仓库未必存在；当前 story 通过 References 指向替代上下文（Story L364-L373）但未显式说明“以 sprint-status/retro 为 epic 事实来源”。

[✓] (Checklist L69) 6. **Understand current status**: What story implementation guidance is currently provided?  
Evidence: Status=ready-for-dev（Story L6）；包含 Tasks、Testing/DoD、关键约束与参考链接（Story L78+、L326+、L355+）。

### C. Epic 与架构深挖（Checklist L80-L100）

[⚠] (Checklist L80) Load `{epics_file}` (or sharded equivalents)  
Evidence: workflow.yaml 的 `epics_file` 默认指向 `docs/epics.md`；本项目 Epic6.2 的事实入口更接近 `docs/sprint-artifacts/sprint-status.yaml` 与 retro（见 `docs/sprint-artifacts/sprint-status.yaml` L165-L209）。

[⚠] (Checklist L81) Extract **COMPLETE Epic {{epic_num}} context**:  
Evidence: story 本身未复述 Epic6.2 全量目标/故事列表；仅给出本 story 背景与范围（Story L14-L50）并提供引用（Story L364-L373）。

[⚠] (Checklist L82) Epic objectives and business value  
Evidence: 提案中有业务影响与目标（Proposal L42-L45、L89-L95）；story 有背景与业务动机，但未摘要 Epic6.2 的整体目标（Story L14-L34）。

[⚠] (Checklist L83) ALL stories in this epic (for cross-story context)  
Evidence: story 未列出 Epic6.2 的 story 列表；可从 `docs/sprint-artifacts/sprint-status.yaml` L174-L209 获取（建议在 story 内摘取与本变更强相关的前置/后置：如 6.6、6.1）。

[✓] (Checklist L84) Our specific story's requirements, acceptance criteria  
Evidence: AC1-AC22 明确（Story L51-L76）。

[⚠] (Checklist L85) Technical requirements and constraints  
Evidence: 有“Critical Implementation Notes”“Project Structure Notes”等约束（Story L211-L219、L301-L308），但对“raw_data 的字段/大小/敏感字段处理策略”“迁移 IF NOT EXISTS 约束”等仍缺明确化。

[⚠] (Checklist L86) Cross-story dependencies and prerequisites  
Evidence: 依赖 `EqcProvider`（Story 6.6）被提及（Story L23），但未明确“改动点与调用链契约”以及“是否影响 6.1 Layer2 enrichment_index 语义”的边界。

[⚠] (Checklist L90) Load `{architecture_file}` (single or sharded)  
Evidence: story 引用 `docs/architecture-boundaries.md`（Story L370），但未摘要关键约束（尤其是运行命令/环境标准来自 `docs/project-context.md` L59-L72）。

[✓] (Checklist L91) **Systematically scan for ANYTHING relevant to this story:**  
Evidence: story 覆盖 DB/服务/CLI/测试/性能估算/护栏（Story L35-L325、L326-L354）。

[⚠] (Checklist L92) Technical stack with versions (languages, frameworks, libraries)  
Evidence: 提到 SQLAlchemy/uv/CLI，但未给版本或“不得新增依赖”的约束（Story L258-L265、L276-L299）。

[✓] (Checklist L93) Code structure and organization patterns  
Evidence: 明确 Clean Architecture 边界与目录约束（Story L301-L308）。

[⚠] (Checklist L94) API design patterns and contracts  
Evidence: CLI 参数与服务职责描述存在，但 EQC raw response 的返回/传递契约未落到类型层（Story L84-L99、L224-L236）。

[✓] (Checklist L95) Database schemas and relationships  
Evidence: 明确目标表与字段、UPSERT 示例（Story L37-L45、L244-L253）。

[⚠] (Checklist L96) Security requirements and patterns  
Evidence: 有“NEVER log API token”护栏（Story L213），但 raw_data 的脱敏/敏感字段策略未说明（raw_data 将保存完整响应，需明确不可包含 token/PII）。

[✓] (Checklist L97) Performance requirements and optimization strategies  
Evidence: 给出全量 refresh 估算与 rate-limit 配置（Story L316-L324、L262-L265）。

[✓] (Checklist L98) Testing standards and frameworks  
Evidence: Unit/Integration 测试清单与命令示例（Story L326-L353）。

[➖] (Checklist L99) Deployment and environment patterns  
Evidence: 本 story 不涉及部署流程；仅涉及 CLI/服务与 DB 迁移（但仍应遵循 uv 运行规范，见 Critical Issue #2）。

[✓] (Checklist L100) Integration patterns and external services  
Evidence: 描述 EQC API → 持久化 → refresh → report 的整体流（Story L170-L194）。

### D. 既有工作/历史情报（Checklist L104-L128）

[✓] (Checklist L104) If `story_num > 1`, load the previous story file  
Evidence: story 直接给出“Previous Story Learnings (from 6.2-P3)”（Story L309-L314）。

[✓] (Checklist L105) Extract **actionable intelligence**:  
Evidence: 以 learnings 列表形式给出可执行要点（Story L309-L314）。

[✓] (Checklist L106) Dev notes and learnings  
Evidence: learnings + Critical Implementation Notes（Story L211-L219、L309-L314）。

[⚠] (Checklist L107) Review feedback and corrections needed  
Evidence: story 引用 PM review 路径（Story L367、L379-L380），但未在正文提炼“PM 强制修订点/风险点摘要”（建议加 5-10 行“PM Review Key Decisions”）。

[✓] (Checklist L108) Files created/modified and their patterns  
Evidence: “Key Files to Modify”表清晰列出新增/修改文件（Story L196-L210）。

[✓] (Checklist L109) Testing approaches that worked/didn't work  
Evidence: Testing/Validation 列出 unit 测试关注点与 CLI 验证命令（Story L326-L353）。

[⚠] (Checklist L110) Problems encountered and solutions found  
Evidence: story 有“Gap Identified/Decision”叙述（Story L22-L34），但缺少“为何 raw_data 放 base_info 而非 company_master”的明确问题-方案对照（提案有，story 可再提炼）。

[✓] (Checklist L111) Code patterns and conventions established  
Evidence: 参数化 SQL、caller owns transaction、non-blocking cache、schema qualification 等明确（Story L211-L219、L242-L253）。

[✓] (Checklist L115) Analyze recent commits for patterns:  
Evidence: 仓库近期提交集中在 Epic6.2 patch 与 enrichment（例如 `feat(story-6.2-p4)`、`feat(story-6.2-p3)`、`fix(epic-6.1): fix EQC query result caching...`），说明“延续既有 enrichment/patch 迭代方式”是正确方向（本次验证已参考 `git log -n 20 --oneline`）。

[✓] (Checklist L116) Files created/modified in previous work  
Evidence: 近期故事集中在 `src/work_data_hub/orchestration/`、`infrastructure/enrichment/`、`io/schema/migrations/` 等范围；与本 story 的“Key Files to Modify”一致（Story L196-L210）。

[✓] (Checklist L117) Code patterns and conventions used  
Evidence: 近期持续使用 repo pattern + structured logging；本 story 亦明确“parameterized queries / no f-strings / non-blocking”（Story L211-L219）。

[⚠] (Checklist L118) Library dependencies added/changed  
Evidence: story 未声明“是否新增依赖”；而清洗引擎示例依赖 `yaml`（PyYAML）与 `re`（标准库）（见 PM review 实现草案）。建议显式声明“若 PyYAML 已存在则复用，否则走既有依赖策略”。

[✓] (Checklist L119) Architecture decisions implemented  
Evidence: 决策“Consolidate to base_info”与“refresh + checkpoint + report”链路清晰（Story L28-L34、L170-L194）。

[✓] (Checklist L120) Testing approaches used  
Evidence: unit 测试 + CLI dry-run 验证（Story L328-L353）。

[✓] (Checklist L124) Identify any libraries/frameworks mentioned  
Evidence: SQLAlchemy（Story L244-L253）、uv（Story L276-L299）、CLI 模块（Story L41-L42、L274-L299）、EQCClient/EqcProvider（Story L23-L25、L39-L40）。

[➖] (Checklist L125) Research latest versions and critical information:  
Evidence: 本 story 不要求引入新框架/升级版本；以“复用现有依赖”为前提更合适。

[➖] (Checklist L126) Breaking changes or security updates  
Evidence: 同上（不在本 story 范围；如需升级，应单独故事化并给出版本策略）。

[➖] (Checklist L127) Performance improvements or deprecations  
Evidence: 同上。

[➖] (Checklist L128) Best practices for current versions  
Evidence: 同上。

### E. 灾难预防差距分析（Checklist L136-L167）

[✓] (Checklist L136) **Wheel reinvention:** Areas where developer might create duplicate functionality  
Evidence: 明确要求复用 `enterprise.base_info` 而非新建 `company_master` 流（Story L28-L34、L44）。

[⚠] (Checklist L137) **Code reuse opportunities** not identified that could prevent redundant work  
Evidence: 清洗框架可能复用既有 cleansing registry/config 体系，但 story 未给出复用/分岔决策（Story L42-L43、L207-L209）。

[⚠] (Checklist L138) **Existing solutions** not mentioned that developer should extend instead of replace  
Evidence: 未提及 `src/work_data_hub/infrastructure/cleansing/registry.py` 等既有清洗入口（建议补充“复用 vs 新增 rule_engine 的边界”）。

[⚠] (Checklist L142) **Wrong libraries/frameworks:** Missing version requirements that could cause compatibility issues  
Evidence: 未声明依赖/版本边界；且 CLI 命令未遵循 uv 标准（Story L276-L299；`docs/project-context.md` L59-L72）。

[⚠] (Checklist L143) **API contract violations:** Missing endpoint specifications that could break integrations  
Evidence: EQC raw response 的传递与类型契约不清（Story L84-L99、L224-L236）。

[⚠] (Checklist L144) **Database schema conflicts:** Missing requirements that could corrupt data  
Evidence: migration 未声明 `IF NOT EXISTS` / 现有列冲突处理（Story L81-L83）；同时 `base_info` 既有字段与 upsert 列名需核对（Story L244-L253）。

[⚠] (Checklist L145) **Security vulnerabilities:** Missing security requirements that could expose the system  
Evidence: 有“不记录 token”护栏（Story L213），但“raw_data 存储敏感字段/脱敏策略/字段白名单”未说明（Story L38、L55）。

[✓] (Checklist L146) **Performance disasters:** Missing requirements that could cause system failures  
Evidence: rate limit/batch size 配置 + 全量 refresh 估算与 checkpoint 机制（Story L262-L265、L316-L324、L43-L44）。

[✓] (Checklist L150) **Wrong file locations:** Missing organization requirements that could break build processes  
Evidence: 明确 migrations/cli/config/service 的落点（Story L196-L210、L301-L308）。

[✓] (Checklist L151) **Coding standard violations:** Missing conventions that could create inconsistent codebase  
Evidence: 参数化 SQL、caller owns transaction、structured logging、non-blocking cache（Story L211-L219、L242-L253、L237-L240）。

[⚠] (Checklist L152) **Integration pattern breaks:** Missing data flow requirements that could cause system failures  
Evidence: `_call_api`→`_cache_result` 当前返回 `CompanyInfo`；引入 raw_response 后需要明确“API 返回/缓存写入”的契约（Story L84-L99、L224-L236；`eqc_provider.py` L262-L272）。

[➖] (Checklist L153) **Deployment failures:** Missing environment requirements that could prevent deployment  
Evidence: 本 story 不涉及部署；但 CLI 运行规范应与 `docs/project-context.md` 对齐（见 Critical Issue #2）。

[⚠] (Checklist L157) **Breaking changes:** Missing requirements that could break existing functionality  
Evidence: `company_master` deprecate 边界不清（Story L44、L60）；需要声明“不 drop，仅标注 deprecated + 不再作为新写入目标”。

[⚠] (Checklist L158) **Test failures:** Missing test requirements that could allow bugs to reach production  
Evidence: 有测试清单（Story L328-L353），但缺少“integration test 的 DB fixture/迁移执行方式/是否需要 docker”说明；建议补一段“Integration Test Harness”。

[➖] (Checklist L159) **UX violations:** Missing user experience requirements that could ruin the product  
Evidence: 非 UX story。

[✓] (Checklist L160) **Learning failures:** Missing previous story context that could repeat same mistakes  
Evidence: 明确列出 6.2-P3 learnings（Story L309-L314）。

[⚠] (Checklist L164) **Vague implementations:** Missing details that could lead to incorrect or incomplete work  
Evidence: raw_response 契约与 `company_master` deprecate 策略细节不足（Story L224-L236、L44、L60）。

[⚠] (Checklist L165) **Completion lies:** Missing acceptance criteria that could allow fake implementations  
Evidence: AC 很全，但缺少“如何证明 raw_data 真为完整响应 / refresh 报告包含哪些字段 / checkpoint 持久化位置”这类可验证细则。

[⚠] (Checklist L166) **Scope creep:** Missing boundaries that could cause unnecessary work  
Evidence: 有 Phase2 Out of Scope（Story L46-L49），但 Phase1-5 中仍大量 Required；建议明确“本 story 是否必须执行全量 refresh（执行 vs 能力提供）”。

[✓] (Checklist L167) **Quality failures:** Missing quality requirements that could deliver broken features  
Evidence: DoD + unit/integration 要求明确（Story L355-L362、L328-L353）。

### F. LLM-Dev-Agent 优化分析（Checklist L175-L187）

[⚠] (Checklist L175) **Verbosity problems:** Excessive detail that wastes tokens without adding value  
Evidence: 大段代码块/命令块较多（Story L145-L194、L222-L299）；可改为“引用 + 必要差异点”。

[⚠] (Checklist L176) **Ambiguity issues:** Vague instructions that could lead to multiple interpretations  
Evidence: raw_response 传递/类型边界不清（Story L224-L236）；`company_master` deprecate 边界不清（Story L44、L60）。

[⚠] (Checklist L177) **Context overload:** Too much information not directly relevant to implementation  
Evidence: “资源估算/全量 refresh”对实现有帮助，但可更聚焦于“能力实现”与“是否执行”的边界（Story L316-L324）。

[✓] (Checklist L178) **Missing critical signals:** Key requirements buried in verbose text  
Evidence: “Critical Implementation Notes (Disaster Prevention)”集中呈现关键护栏（Story L211-L219）。

[✓] (Checklist L179) **Poor structure:** Information not organized for efficient LLM processing  
Evidence: 结构清晰（Story 具备 Scope/AC/Tasks/Context/Testing/DoD/Refs）。

[⚠] (Checklist L183) **Clarity over verbosity:** Be precise and direct, eliminate fluff  
Evidence: 需进一步“把关键决策变成硬约束”（raw_response、company_master deprecate、uv 命令标准）。

[✓] (Checklist L184) **Actionable instructions:** Every sentence should guide implementation  
Evidence: Tasks/Key Files/SQL 示例/测试清单具备可执行性（Story L80-L210、L242-L253、L328-L353）。

[✓] (Checklist L185) **Scannable structure:** Use clear headings, bullet points, and emphasis  
Evidence: 标题与表格使用良好（Story L35-L76、L196-L210、L318-L324）。

[⚠] (Checklist L186) **Token efficiency:** Pack maximum information into minimum text  
Evidence: 可删减重复描述（提案/PM review 已覆盖的内容），转为引用 + 关键差异点。

[⚠] (Checklist L187) **Unambiguous language:** Clear requirements with no room for interpretation  
Evidence: raw_response/类型契约与 deprecate 定义仍留解释空间（Story L224-L236、L44、L60）。

### G. 改进建议分组（Checklist L195-L218）

[⚠] (Checklist L195) Missing essential technical requirements  
Evidence: migration 安全性（IF NOT EXISTS/rollback 验证）、raw_response 契约、raw_data 脱敏策略缺少硬性描述。

[✓] (Checklist L196) Missing previous story context that could cause errors  
Evidence: 已包含 learnings（Story L309-L314）。

[⚠] (Checklist L197) Missing anti-pattern prevention that could lead to duplicate code  
Evidence: 清洗框架与既有 cleansing 体系可能重复，需明确复用策略（Story L42-L43、L207-L209）。

[⚠] (Checklist L198) Missing security or performance requirements that must be followed  
Evidence: 性能已覆盖（Story L262-L265、L316-L324），但安全（raw_data 内容边界）仍需补（Story L38、L55）。

[⚠] (Checklist L202) Additional architectural guidance that would help developer  
Evidence: 建议补“raw_data 存储策略（字段/大小/脱敏）”与“company_master deprecate definition”小节。

[⚠] (Checklist L203) More detailed technical specifications  
Evidence: raw_response 的类型/传递/落库字段映射需写成可实现的契约（Story L84-L99、L224-L236）。

[⚠] (Checklist L204) Better code reuse opportunities  
Evidence: 需明确是否复用既有 cleansing registry/config（Story L207-L209）。

[⚠] (Checklist L205) Enhanced testing guidance  
Evidence: 需要补 integration test 的环境准备与断言（数据库迁移、seed 数据、mock EQC）。

[✓] (Checklist L209) Performance optimization hints  
Evidence: refresh 估算 + 并发建议 + rate limit 配置（Story L316-L324、L262-L265）。

[⚠] (Checklist L210) Additional context for complex scenarios  
Evidence: checkpoint/resume 只在 AC/Task 层提到，缺少“checkpoint 存储介质/格式/幂等策略”的详细约束。

[⚠] (Checklist L211) Enhanced debugging or development tips  
Evidence: 有“Report results”示例（Story L192-L194），但缺少失败重试/错误分类/可观测性字段（可从 PM review 摘要）。

[⚠] (Checklist L215) Token-efficient phrasing of existing content  
Evidence: 可把大段代码示例替换为“引用 + 关键差异点”（当前 Story L145-L194、L222-L254）。

[✓] (Checklist L216) Clearer structure for LLM processing  
Evidence: 已有良好结构（Scope/AC/Tasks/Notes/Testing/DoD/Refs）。

[⚠] (Checklist L217) More actionable and direct instructions  
Evidence: 关键决策点需“二选一”写死（raw_response 方案：tuple 返回 vs 扩展 CompanyInfo；company_master：仅 deprecated 文档 vs 引入 view）。

[⚠] (Checklist L218) Reduced verbosity while maintaining completeness  
Evidence: 同 L175/L186。

### H. 竞争成功度量（Checklist L228-L244）

[⚠] (Checklist L228) Essential technical requirements the developer needs but aren't provided  
Evidence: raw_data 脱敏策略、迁移健壮性、integration harness 缺少硬约束。

[✓] (Checklist L229) Previous story learnings that would prevent errors if ignored  
Evidence: learnings 清单（Story L309-L314）。

[⚠] (Checklist L230) Anti-pattern prevention that would prevent code duplication  
Evidence: cleansing 复用策略未定义（Story L207-L209）。

[⚠] (Checklist L231) Security or performance requirements that must be followed  
Evidence: 性能已覆盖（Story L316-L324），安全仍需补（raw_data 的敏感字段处理）。

[✓] (Checklist L235) Architecture guidance that would significantly help implementation  
Evidence: 数据存储架构图 + refresh flow（Story L145-L194）。

[⚠] (Checklist L236) Technical specifications that would prevent wrong approaches  
Evidence: raw_response 传递与类型契约仍不清（Story L224-L236）。

[⚠] (Checklist L237) Code reuse opportunities the developer should know about  
Evidence: cleansing 既有体系未被引用（Story L207-L209）。

[⚠] (Checklist L238) Testing guidance that would improve quality  
Evidence: 测试清单存在但缺“环境/断言/fixture”（Story L328-L353）。

[✓] (Checklist L242) Performance or efficiency improvements  
Evidence: rate limit + batch + checkpoint/resume（Story L262-L265、L43-L44）。

[⚠] (Checklist L243) Development workflow optimizations  
Evidence: 需要将 CLI 命令与 uv 标准对齐（Critical Issue #2），并建议为 full refresh 增加 dry-run/确认流程的明确约束。

[⚠] (Checklist L244) Additional context for complex scenarios  
Evidence: checkpoint/恢复/失败处理仍需细化（同 L210/L211）。

### I. 交互式改进流程项（Checklist L276-L323, L305-L308）

[➖] (Checklist L276) Reduce verbosity while maintaining completeness  
Evidence: checklist 代码块内的示例项；不作为 story 约束本身。

[➖] (Checklist L277) Improve structure for better LLM processing  
Evidence: 同上。

[➖] (Checklist L278) Make instructions more actionable and direct  
Evidence: 同上。

[➖] (Checklist L279) Enhance clarity and reduce ambiguity}}  
Evidence: 同上。

[➖] (Checklist L292) **all** - Apply all suggested improvements  
Evidence: checklist 代码块内交互选项；不作为 story 约束本身。

[➖] (Checklist L293) **critical** - Apply only critical issues  
Evidence: 同上。

[➖] (Checklist L294) **select** - I'll choose specific numbers  
Evidence: 同上。

[➖] (Checklist L295) **none** - Keep story as-is  
Evidence: 同上。

[➖] (Checklist L296) **details** - Show me more details about any suggestion  
Evidence: 同上。

[➖] (Checklist L305) **Load the story file**  
Evidence: 这是“如何应用改动”的流程项；本次验证未直接改 story（仅给出建议）。

[➖] (Checklist L306) **Apply accepted changes** (make them look natural, as if they were always there)  
Evidence: 同上。

[➖] (Checklist L307) **DO NOT reference** the review process, original LLM, or that changes were "added" or "enhanced"  
Evidence: 同上。

[➖] (Checklist L308) **Ensure clean, coherent final story** that reads as if it was created perfectly the first time  
Evidence: 同上。

[➖] (Checklist L322) 1. Review the updated story  
Evidence: checklist 代码块内“应用改动后”的下一步；本次未修改 story。

[➖] (Checklist L323) 2. Run `dev-story` for implementation  
Evidence: 同上。

### J. 成功标准自检（Checklist L334-L356）

[✓] (Checklist L334) ✅ Clear technical requirements they must follow  
Evidence: AC/Tasks/Key Files/护栏明确（Story L51-L76、L80-L210、L211-L219）。

[✓] (Checklist L335) ✅ Previous work context they can build upon  
Evidence: Background/Decision/Learnings/Refs（Story L14-L34、L309-L314、L364-L373）。

[⚠] (Checklist L336) ✅ Anti-pattern prevention to avoid common mistakes  
Evidence: 有护栏（Story L211-L219），但 cleansing 复用策略与 raw_response 契约需明确以避免“走错路/造轮子”。

[✓] (Checklist L337) ✅ Comprehensive guidance for efficient implementation  
Evidence: 文件清单、SQL 示例、配置项、测试清单（Story L196-L210、L242-L265、L328-L353）。

[✓] (Checklist L338) ✅ **Optimized content structure** for maximum clarity and minimum token waste  
Evidence: 结构合理（Scope/AC/Tasks/Notes/Testing/DoD/Refs）。

[✓] (Checklist L339) ✅ **Actionable instructions** with no ambiguity or verbosity  
Evidence: 大部分任务可执行（Story L80-L210）；但仍需修正 raw_response/uv 标准/`company_master` 定义（见 Critical Issues）。

[⚠] (Checklist L340) ✅ **Efficient information density** - maximum guidance in minimum text  
Evidence: 信息密度高但偏长；可用引用替代部分代码块以节省 token（Story L145-L194、L222-L299）。

[✓] (Checklist L344) Reinvent existing solutions  
Evidence: 明确“用 base_info 统一”“复用既有模式”（Story L28-L34、L211-L219）。

[⚠] (Checklist L345) Use wrong approaches or libraries  
Evidence: uv 命令标准未对齐（Story L276-L299；`docs/project-context.md` L59-L72）。

[⚠] (Checklist L346) Create duplicate functionality  
Evidence: cleansing 可能出现双体系（Story L207-L209）。

[⚠] (Checklist L347) Miss critical requirements  
Evidence: raw_data 安全边界/迁移健壮性/类型契约仍需补齐。

[⚠] (Checklist L348) Make implementation errors  
Evidence: 同上（raw_response 与 deprecate 策略不清会诱发错误实现）。

[⚠] (Checklist L352) Misinterpret requirements due to ambiguity  
Evidence: raw_response/`company_master` 定义仍可能被不同 dev 解读（Story L224-L236、L44、L60）。

[⚠] (Checklist L353) Waste tokens on verbose, non-actionable content  
Evidence: 可压缩大段代码/命令块（Story L145-L194、L222-L299）。

[✓] (Checklist L354) Struggle to find critical information buried in text  
Evidence: 关键护栏集中在“Critical Implementation Notes”（Story L211-L219）。

[✓] (Checklist L355) Get confused by poor structure or organization  
Evidence: 结构清晰，信息可扫描。

[⚠] (Checklist L356) Miss key implementation signals due to inefficient communication  
Evidence: 仍需将“三个硬约束”前置高亮：raw_response 契约、uv 命令标准、company_master deprecate definition。

---

## Recommendations（按优先级）

1. Must Fix
   - **把 raw_response 契约写死**：明确采用哪一种方案（例如：`EQCClient.search_company()` 返回 `(parsed, raw_json)`；或 `CompanySearchResult.raw`；或 provider 改为返回 `CompanyInfoWithRaw`）。
   - **把 CLI 命令改为符合项目标准**：至少示例统一为 `PYTHONPATH=src uv run --env-file .wdh_env python -m ...`（或项目已有惯例的等价写法）。
   - **定义 `company_master` deprecate 的“非破坏性”边界**：不 drop 表；仅文档/注释标注 deprecated；新写入目标为 base_info；现存读取路径如何处理写清。
   - **明确 cleansing 复用策略**：是复用现有 registry 体系并新增一套 rule 类型，还是引入独立 `rule_engine.py`（并说明为何不复用）。
2. Should Improve
   - **拆分 story 或明确 Phase 边界**：若 full refresh 的“执行”不在本 story 内，则 AC/DoD 应改为“提供能力+dry-run+checkpoint”，把“执行全量 28,576 refresh”放到单独 milestone story。
   - **补齐 Integration Test Harness**：DB 迁移执行方式、seed 数据、mock EQC、断言/报告字段。
3. Consider
   - 精简大段代码块：改为“引用现有函数/行号 + 仅列 diff 要点”，提升 token 效率并降低误抄风险。
