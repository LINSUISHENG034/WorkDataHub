# Slice Tests Traceability Matrix

来源文档：`docs/domain_processing_flows.md`

| 流程阶段 | 核心行为 | 主要测试覆盖 |
|---|---|---|
| 1. discover_files_op | 按 domain+period 发现文件；版本优先策略 | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| 2. read_data_op | 单 Sheet / 多 Sheet 读取与拼接 | `tests/slice_tests/test_h_end_to_end_flows.py` |
| 3. process_domain_op_v2 | annuity/award/loss Bronze→Silver 全链路转换 | `tests/slice_tests/test_b_annuity_performance_pipeline.py`, `tests/slice_tests/test_c_annual_award_pipeline.py`, `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| 3a. Company ID 解析优先级 | YAML -> DB 缓存 -> existing -> EQC -> temp ID | `tests/slice_tests/test_j_real_effect_guards.py` |
| 3b. 年金计划号补齐 | PlanCodeEnrichment 按 计划类型优先 P/S 前缀 | `tests/slice_tests/test_j_real_effect_guards.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| 4. generic_backfill_refs_op | foreign_keys 聚合回填（max_by/concat/count/lambda/jsonb） | `tests/slice_tests/test_e_backfill_engine.py`, `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| 5. gate_after_backfill | 回填完成后才允许 load | `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| 6. load_op | delete_insert + PK 幂等计划 | `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| Snapshot 刷新 | ProductLine / Plan 双粒度 SQL + ON CONFLICT | `tests/slice_tests/test_g_snapshot_status.py`, `tests/slice_tests/test_i_snapshot_refresh_contract.py` |
| 状态规则 | config/customer_status_rules.yml 驱动 status 计算 | `tests/slice_tests/test_g_snapshot_status.py`, `tests/slice_tests/test_i_snapshot_refresh_contract.py` |

## 仍需关注（非 slice 范围）
- `load_op` 与 `generic_backfill_refs_op` 的真实 PostgreSQL 写入效果（当前 slice 以 plan_only 合同为主；真实落库建议由 integration 套件兜底）。
