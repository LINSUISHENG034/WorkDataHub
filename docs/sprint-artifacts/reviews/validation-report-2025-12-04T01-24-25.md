# Validation Report

**Document:** docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md
**Checklist:** .bmad/bmm/workflows/4-implementation/create-story/checklist.md
**Date:** ' + $ts + '

## Summary
- Overall: 3/15 passed (20%), 5 partial, 7 failed
- Critical Issues: 7 (fails)

## Section Results

### Step 1: Target & Metadata
- ✓ Story metadata完整（编号/史诗/优先级/依赖/工期）并可追溯：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:1-7
- ✓ 目标文件结构列出清晰（7个文件名），便于实现者定位：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:33-62
- ✓ 行数表/优先级/依赖明确，便于排期：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:63-117

### Step 2: Source Context & Inputs
- ✗ 未带出史诗业务目标/价值/成功指标（Epic 5 Goal/Business Value/Success Metrics 未引用）：docs/epics/epic-5-infrastructure-layer.md:1-9,420-439
- ✗ 未总结 5.1-5.8 成果/可复用模式/阻碍（仅写“依赖 5.1-5.8”）：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:5-7 与 docs/epics/epic-5-infrastructure-layer.md:13-369
- ✗ 缺少架构护栏与 AD-010 约束（Clean Architecture 分层、DI、标准步骤/infra 复用等）：docs/epics/epic-5-infrastructure-layer.md:3-10
- ✗ 未携带前置故事的测试/性能/覆盖率基线与经验教训（Epic 5.8 E2E/性能/覆盖率要求未体现）：docs/epics/epic-5-infrastructure-layer.md:325-356,338-344
- ✗ 未提及技术研究/依赖版本或库注意事项（无版本/兼容性提示）

### Step 3: Disaster-Prevention Coverage
- ⚠ Gap 分析发现的缺口仅放在引用，未转化为约束/任务顺序（应使用收尾计划 1-6 步）：docs/sprint-artifacts/auxiliary/epic-5-migration-gap-analysis.md:40-306
- ⚠ 重用/防重复指令不足：虽要求删除 helpers/pipeline_steps，但未强制“必须复用 infra/components，禁止 domain 自建标准步骤”
- ✗ 关键技术规格缺失：未给出 CompanyIdResolver 契约/标准 TransformStep 接口/验证类迁移位置/依赖路径更新要求，导致实现自由度过大
- ⚠ 行数/文件计数有目标但无验收方法（如何统计、何时验证、失败处理未写）
- ⚠ 测试与回归仅泛述“全部测试通过”，无 E2E/性能/覆盖率阈值或具体脚本入口：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:119-127 vs epic要求 docs/epics/epic-5-infrastructure-layer.md:325-356,338-344
- ⚠ 文档更新只列文件名，未说明新增哪些章节/图/指标：docs/sprint-artifacts/stories/5-9-epic5-migration-cleanup.md:129-136
- ✗ 回归/兼容性/性能指标未写（Epic 5 目标：<3s/1K rows，内存<200MB，覆盖率>85/90，Mypy/Ruff 等）：docs/epics/epic-5-infrastructure-layer.md:325-356,338-344

### Step 4: LLM-Dev-Agent Optimization
- ⚠ 结构清晰但缺乏“必须/禁止”红线、性能阈值、测试脚本入口；易产生实现歧义
- ⚠ 无 token/上下文压缩策略（哪些细节可略、哪些必须保留）

### Step 5: Improvement Recommendations
- ✗ 建议尚未写入故事；需将上列缺口转成约束/任务/测试/文档要求
- ⚠ 需要加入测量与验收步骤（行数、文件数、测试、性能、覆盖率、文档更新确认）

## Failed Items
1) 史诗业务目标/价值/成功指标未收敛到故事
2) 跨故事成果/复用/教训缺失
3) 架构护栏与 AD-010 约束缺失
4) 前置故事的测试/性能/覆盖率基线缺失
5) 技术研究/依赖版本缺失
6) 关键技术规格与接口约束缺失
7) 回归/兼容性/性能指标未写

## Partial Items
1) Gap 分析缺口未转成执行顺序/约束
2) 重用/防重复指令不足（需强制复用 infra 禁止自建）
3) 行数/文件计数缺少验收方法
4) 测试与回归缺少阈值与脚本入口
5) 文档更新缺少具体内容/章节/指标
6) LLM 优化缺少硬性“必须/禁止”与压缩策略
7) 建议未落地到故事

## Recommendations
1. 补齐史诗上下文：Goal/Business Value/Success Metrics/AD-010 护栏、Epic 5.8 性能/覆盖率/兼容性目标。
2. 引入 5.1-5.8 成果/可复用组件与教训，明确“必须复用”与“禁止自建”列表（enrichment/validation/transforms/cleansing/registry 等）。
3. 将 gap 分析收尾计划 1-6 步转成任务顺序与验收信号；给出行数/文件数统计指令与失败处理。
4. 补充技术规格：CompanyIdResolver 契约、标准 Pipeline/TransformStep 使用、验证/投影迁移路径、导入路径更新 checklist。
5. 补充测试/性能/覆盖率阈值与命令（unit/integration/E2E/perf/parity、Mypy/Ruff）；记录数据集/基准。
6. 明确文档更新范围（哪些章节/图/指标/表），并记录完成检查方法。
7. 增加 LLM 执行护栏：必须/禁止、token 节省策略、引用脚本入口、验收流程。'
