# INITIAL.md — C-019..C-022 小补丁（减少关键用例失败）

目标：以最小改动修复当前最主要的失败簇，提升端到端稳定性；不改变架构、不扩大范围。后续C-023将单独处理连接语义对齐。

## 任务
- ROADMAP：
  - C-019（DB设置兼容层与DSN获取统一）
  - C-020（ExcelReader健壮化）
  - C-021（文件发现月份提取稳健化）
  - C-022（受托业绩小数/百分比处理与量化稳健性）
- 范围：仅限小补丁，不改测试，不动无关模块。

## 现状与主要症状（摘自VALIDATION.md）
- 配置/API不匹配：测试期望存在`DatabaseSettings`与`settings.database.get_connection_string()`；当前仅有`Settings.get_database_connection_string()`。
- 月份提取错误：正则`(?P<month>0?[1-9]|1[0-2])`在“12”时匹配到“1”（左侧优先），致断言期望12变为1。
- ExcelReader不一致：
  - “年/月”断言为字符串（"2024"），但读成了整数；
  - “Unnamed: n”列名未清洗为空字符串""；
  - 损坏文件未统一抛出“Failed to parse Excel file”类错误。
- 领域小数/百分比：`return_rate=5.5`应按百分比解释为0.055；量化器构造需更稳健。

## 交付物（最小变更集）
1) DB设置兼容层（C-019）
   - 文件：`src/work_data_hub/config/settings.py`
   - 新增轻量`DatabaseSettings`（host/port/user/password/db/uri + `get_connection_string()`）。
   - `Settings`新增属性`database: DatabaseSettings`（从现有环境变量组装），并让`get_database_connection_string()`委托给`self.database.get_connection_string()`；保留现有`database_uri`直连优先逻辑。
   - `ops.load_op`取DSN时：优先`settings.get_database_connection_string()`；若异常或缺失，回退`settings.database.get_connection_string()`（兼容老测试）。

2) ExcelReader健壮化（C-020）
   - 文件：`src/work_data_hub/io/readers/excel_reader.py`
   - 在`_dataframe_to_rows`：
     - 保持“年”“月”列值为字符串（不向int收缩）；
     - 将列名形如`^Unnamed:\s*\d+`归一为`""`（空字符串）；
   - 在`read_rows`错误处理：捕获`zipfile.BadZipFile`、`openpyxl`相关异常，统一抛出`ExcelReadError("Failed to parse Excel file ...")`以匹配断言。

3) 月份提取稳健化（C-021）
   - 文件：`src/work_data_hub/io/connectors/file_connector.py`
   - 在`_scan_directory_for_domain`里，匹配后对`match`结果进行回退修正：
     - 若捕获`month`为一位数字，且文件名中该位后紧跟的字符与其组成的两位数在[10, 12]，则将`month`改为两位数（例如"12").
   - 注意：不改测试里给定的正则（测试自带sample config），仅在我们代码里做安全后处理。

4) 领域小数/百分比与量化稳健（C-022）
   - 文件：`src/work_data_hub/domain/trustee_performance/models.py`
   - 在`clean_decimal_fields`（`mode="before"`）：
     - 对`return_rate`：若输入为数值且>1（且合理上限<=100），按百分比解释（除以100），与`"5.5%"`一致；
     - 小数量化使用：`Decimal(1).scaleb(-places)`构造量化器 + `ROUND_HALF_UP`，增强稳健性；
   - 仅限上述字段，不影响`net_asset_value`/`fund_scale`语义。

## 非目标
- 不在本PR中统一“ops使用上下文管理器连接 vs 裸连接”的语义（留给C-023）。
- 不为全部失败一次性兜底。仅修复上述高杠杆问题。

## 集成与兼容性
- 现有入口保持不变：
  - `src/work_data_hub/orchestration/ops.py` 仅在DSN获取上做兼容处理；
  - 不改`data_sources.yml`，避免影响其他用例；
  - 不修改测试文件。

## 验证步骤（本地）
- 基线：
  - `uv run ruff check src/ --fix`
  - `uv run mypy src/`
  - `uv run pytest -v`（观察失败减少）
- 重点用例抽样（建议先聚焦以下）：
  - `uv run pytest -v tests/io/test_excel_reader.py -k "read_rows_success or corrupted_file or column_name_cleaning"`
  - `uv run pytest -v tests/io/test_file_connector.py -k latest_by_year_month_selection`
  - `uv run pytest -v tests/io/test_warehouse_loader.py -k DatabaseSettings`
  - `uv run pytest -v tests/e2e/test_trustee_performance_e2e.py -k complete_pipeline_plan_only_mode`
  - `uv run pytest -v tests/domain/trustee_performance/test_models.py -k validator_handles_various_input_types`

## 验收标准（小补丁）
- 配置兼容：`tests/io/test_warehouse_loader.py::TestDatabaseSettings::*`通过（可导入`DatabaseSettings`且生成正确DSN）。
- ExcelReader：
  - `test_read_rows_success`断言“年/月”为字符串通过；
  - `test_read_rows_corrupted_file`捕获“Failed to parse Excel file”通过；
  - `test_dataframe_to_rows_column_name_cleaning`包含空列名`""`通过。
- 文件发现：`test_latest_by_year_month_selection`能正确识别12月。
- 领域小数/百分比：`test_validator_handles_various_input_types`中`return_rate=5.5`按百分比转换为`0.055000`通过。
- 不引入新的mypy/ruff错误。

## 风险与回退
- Excel列名归一化把多个“Unnamed”映射为同一空列名；当前测试只断言存在空列名，不校验重复，风险可接受。
- 月份回退修正仅在明确两位数（10/11/12）时生效，不改变其他匹配路径。
- `return_rate`数值解释为百分比仅在>1（且<=100）时生效，避免误伤小于1的小数（已作为小数）。

## 附：涉及文件
- `src/work_data_hub/config/settings.py`
- `src/work_data_hub/orchestration/ops.py`
- `src/work_data_hub/io/readers/excel_reader.py`
- `src/work_data_hub/io/connectors/file_connector.py`
- `src/work_data_hub/domain/trustee_performance/models.py`

## 提交要求
- 变更保持最小、聚焦；不改测试文件；
- 通过`ruff`/`mypy`；关键用例通过如上；
- PR描述简要列出影响面与验证命令。
