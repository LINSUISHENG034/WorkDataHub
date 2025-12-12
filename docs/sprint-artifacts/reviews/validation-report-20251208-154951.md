# Validation Report

**Document:** docs/sprint-artifacts/stories/6.1-4-legacy-data-migration.md  
**Checklist:** .bmad/bmm/workflows/4-implementation/create-story/checklist.md  
**Date:** 2025-12-08 15:49:51

## Summary
- Overall: 16/19 passed (84%)
- Critical Issues: 1

## Section Results

### Critical Mistakes to Prevent
Pass Rate: 6/7 (86%)

✓ 避免重复造轮子：重用 `insert_enrichment_index_batch()` 与 `normalize_for_temp_id()`，明确依赖既有仓储与归一化逻辑 (128-133, 265-313)。  
✓ 避免错误库/依赖：未引入新库，强调复用现有模块与 structlog 日志 (37-48, 128-133)。  
✓ 正确文件位置：脚本与测试路径明确列出，符合项目结构 (37-41, 128-133, 255-260, 449-453)。  
⚠ 回归风险防范：有回滚与幂等说明，但缺少对表存在性/依赖版本的前置检查或影子演练指引 (49-57, 104-108, 124-133)。  
➖ 忽视 UX：故事无 UI/UX 触点，非适用。  
✓ 避免模糊实现：AC 与任务分解具体，涵盖迁移、去重、报告与测试 (13-70, 71-120)。  
✓ 避免虚假完成：状态为 ready-for-dev，任务全部未勾选，未假称已完成 (3, 71-120)。  
✓ 学习以往工作：总结 6.1.1-6.1.3 经验并注明依赖 (420-434, 510-514)。

### Systematic Re-Analysis Approach
Pass Rate: 4/6 (67%)

✓ 工作流上下文：Story 元数据、依赖与目标清晰，匹配 create-story 模板 (1-4, 7-9, 510-514)。  
✓ Epic 语境：说明为 Epic 6.1 第四个故事，业务价值与动机明确 (7-9, 510-514)。  
✓ 架构深潜：强调使用现有归一化/仓储、无 schema 变更、ON CONFLICT 语义 (124-133, 204-230)。  
✓ 既有故事情报：提炼前序故事的仓储、优先级与日志经验 (420-434)。  
⚠ Git 历史模式：仅提供提交命名模式，未总结近期变更影响或回归点 (436-446)。  
✗ 最新技术研究：未提供库/运行时版本、批处理性能基线或潜在破坏性变更扫描（需补充）。

### Disaster Prevention Gap Analysis
Pass Rate: 5/5 (100%)

✓ 防止重复实现：指向现有仓储与归一化函数，避免新实现 (128-133, 265-313)。  
✓ 技术规格防灾：AC1-AC4 明确字段映射、置信度、去重与归一化规则；AC5-AC7 覆盖幂等与回滚 (13-57, 214-230, 104-108)。  
✓ 文件结构防灾：脚本/测试路径与参考文件列表齐备 (37-48, 255-261, 449-453, 521-527)。  
✓ 回归防灾：单测与集成测试覆盖、性能指标、日志/报告要求写明 (59-70, 98-120, 233-249, 455-482)。  
✓ 实施防灾：任务分解到方法级，包含过滤空值、分页、批量插入、冲突策略与报告输出 (79-120, 171-207, 355-408)。

### LLM Optimization
Pass Rate: 1/1 (100%)

✓ 结构与可扫描性：标题/AC/任务/参考分区清晰，强调必用组件与代码片段，便于代理消费 (5-120, 232-408, 455-495)。

## Failed Items
✗ 最新技术研究（Systematic Re-Analysis 6/6）：缺少运行时/依赖版本、批量插入性能基线、潜在 breaking change 摘要；易导致脚本在未来升级或不同环境下踩坑。

## Partial Items
⚠ 回归风险防范：未要求在运行前检测 `enrichment_index` 及仓储方法版本、未建议影子环境或小样本演练。  
⚠ Git 历史模式：未总结近期相关提交的行为变化或潜在冲突点。

## Recommendations
1. Must Fix: 添加运行时/依赖版本与批处理性能基线，附带“兼容性检查表”（表存在性、索引、仓储 API 版本）。  
2. Should Improve: 在脚本开头加入前置验证步骤与 `--dry-run --limit` 示例，用于影子演练；补充近期提交/差异的快速回归关注点。  
3. Consider: 记录一次示例性能（31k 行/批 1000 的耗时与日志格式），供后续比对。

## Baseline Guidance (Shadow/Perf Testing)
- 命令（影子/预发，小样本或全量）：`PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --dry-run --batch-size 500 --verbose`
- 采集字段：DB 版本/实例；数据规模（company_id_mapping 读取行数 / eqc_search_result 读取行数）；batch；总耗时；吞吐（行/秒）；每 5000 行日志打点；inserted/updated/skipped（分源）；ON CONFLICT 触发情况；异常；可选 CPU/内存峰值
- 建议规模：
  - 单元级：20–50 行（空值/空串/前后空格/重复键/current+former/Success+非 Success/空 company_id 跳过/长字符串）
  - 集成级：500–1,000 行（10–15% 重复、5–10% 空 company_id/空名称、current:former≈7:3、Success/非 Success 混合）
  - 预发性能：10,000 行，batch=500/1000 各跑一次，记录耗时/吞吐与日志节奏
  - 生产近似：30k–35k 行（贴合月度 33,615 行），batch=1000 目标 <5 分钟；如超时再测 batch=500
- 组成建议：company_id_mapping 70% current / 30% former，含名称空格/大小写/符号差异；eqc_search_result 仅 Success+非空 company_id，混入 5–10% 非 Success 验证过滤；跨源/跨 current-former 重复以验证 ON CONFLICT（hit_count+1、GREATEST(confidence)）
- 基线记录模板（填实后追加至报告或故事）：
  - Env: Postgres 14.x, DB=<shadow_db>, host=<shadow_host>
  - Rows read: company_id_mapping=<n1>, eqc_search_result=<n2>, total=<n_total>
  - Batch: <size>
  - Runtime: <seconds> s; Throughput: <rows_per_sec> rows/s
- Logs: every 5000 rows timestamped
- Results: inserted=<0>, updated=<0> (dry-run), skipped=<n_skipped>; Conflicts observed=<yes/no>; Errors=<none/desc>
- Notes: <anomalies/config tweaks>

## Baseline Record (Pending Data Entry)
- 使用模板：`docs/templates/migration-baseline-template.md` 复制后填入实测值。
