# 学习笔记

- 测试脚本
```bash
uv run python -m src.work_data_hub.orchestration.jobs --execute --max-files 2
```

## 新架构起始点

- Dagster Job: 通过 src/work_data_hub/orchestration/jobs.py 中的 trustee_performance_job 或
trustee_performance_multi_file_job 启动。
- 首个 Op: discover_files_op（src/work_data_hub/orchestration/ops.py），内部调用
DataSourceConnector.discover，依据 data_sources.yml 与 settings.data_base_dir 做配置驱动的文
件发现。
- 事件触发: trustee_new_files_sensor（src/work_data_hub/orchestration/sensors.py）监听新文件
出现并触发 trustee_performance_multi_file_job。
- 定时触发: trustee_daily_schedule（src/work_data_hub/orchestration/schedules.py）按日程触发
多文件作业。
- Dagster 发现入口: src/work_data_hub/orchestration/repository.py 中的 defs 被 dagster dev 自动发现。

### 快速运行示例

- CLI（计划模式）: uv run python -m src.work_data_hub.orchestration.jobs --domain
trustee_performance --plan-only
- CLI（执行模式）: uv run python -m src.work_data_hub.orchestration.jobs --domain
trustee_performance --execute
- Dagster 本地: dagster dev（加载 repository.py 的 jobs/schedules/sensors）