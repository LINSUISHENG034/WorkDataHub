# 清洗组件补强与域内最小改动（INITIAL.md）

本 INITIAL 面向“规模明细（annuity_performance）”落地时暴露的重复清洗问题，给出最小增量的补强方案，确保遵循 KISS/YAGNI，同时对 legacy/annuity_hub 的关键清洗点实现“功能等价或更稳健”的覆盖。

## Feature（目标）

- 在不引入复杂框架/DSL 的前提下，补强通用数值清洗与输入层列名标准化，消除跨域重复实现。
- 保持业务强相关逻辑在域层（或后续映射服务）处理，避免组件臃肿。
- 对 legacy 的关键清洗差异进行最小改动补齐，降低回归风险。

## 背景与现状

- 新架构已提供通用数值清洗组件 `src/work_data_hub/cleansing`，并在受托/年金两域落地，显著减少重复代码。
- 评估发现以下差距会影响与 legacy 的“完全覆盖”：
  1) 百分号变体与负百分比处理不完全（`％`、负值）；
  2) Excel 列名未去除换行/制表符，可能导致列投影 `project_columns` 丢列；
  3) 少量域内“格式修正”仍缺失（如 `组合代码` 去除 `^F` 前缀）。
- 公司名称清洗、company_id 回填、计划代码特殊替换、机构代码默认值等均为强业务/映射逻辑，建议维持在域层或 M2 的 Mapping Service 中处理。

## 范围（In‑scope）

1) 通用数值清洗规则增强（不改 API）
   - 在 `handle_percentage_conversion` 中：
     - 识别全角百分号 `％` 与半角 `%`；
     - 对数值型输入在“收益率字段”中按百分比处理，规则：当 `abs(value) > 1` 时视为百分数并除以 100，保留符号。
   - 与现有 `standardize_null_values`、`remove_currency_symbols`、`decimal_quantization` 协同，确保异常信息清晰。

2) 输入层列名标准化（ExcelReader）
   - 在 `src/work_data_hub/io/readers/excel_reader.py::_dataframe_to_rows`：对列名统一执行 `replace("\n", "").replace("\t", "")`，与已有 `strip()` 组合，确保 `project_columns` 不丢列。

3) 域内最小改动（年金）
   - 在 `annuity_performance` 域服务中对 `组合代码` 进行前缀剥离（等价 legacy：去 `^F`）。

4) 保持现有公共 API 稳定：`comprehensive_decimal_cleaning`、`decimal_fields_cleaner` 不变。

## 非目标（Non‑goals）

- 不引入通用字符串大而全清洗（如完整公司名正则库）；复杂规则继续留在域层。
- 不实现 company_id 多级回填、计划代码特殊替换、机构代码默认值（M2 Mapping Service 负责，见 MIGRATION_REFERENCE）。
- 不改数据表/DDL、Orchestration 入口与配置结构。
- 不引入规则流水线/DSL/外部配置驱动的复杂系统。

## 详细规范（Spec）

1) 数值清洗规则（`rules/numeric_rules.py`）
   - `handle_percentage_conversion(value, field_name)`：
     - 字符串：若包含 `%` 或 `％`，移除符号后按 100 进行转换；失败抛出 `ValueError`，错误消息保留原值。
     - 数值：当字段名包含“收益率”或 `.lower().find("rate") >= 0` 且 `abs(value) > 1`，视作百分数并除以 100，保留正负号。
     - 其它场景：原值返回。
   - 与 `decimal_quantization` 协同：在综合规则 `comprehensive_decimal_cleaning` 中先进行百分比转换，再量化；量化精度按 `precision_config` 或默认表。

2) Excel 列名标准化（`io/readers/excel_reader.py`）
   - 在 `_dataframe_to_rows` 中，列名清洗流程：
     1) 将 `None/Unnamed: n` 处理为 `""`（保持现有逻辑）；
     2) `str(col).strip()`；
     3) 追加 `.replace("\n", "").replace("\t", "")`。
   - 兼容性：若归一化导致重名，沿用 pandas 行为（后者覆盖），该风险可接受且较少出现。

3) 年金域内改动（`domain/annuity_performance/service.py`）
   - 在提取/整理元数据时（建议在 `_extract_metadata_fields` 或模型构建前）：
     - 若存在 `组合代码` 且为字符串，执行正则 `'^F'` 剥离前缀（与 legacy 等价）；字段缺失时不作处理。

4) 可选后续（仅当多域共用且仍简单时再考虑）
   - `rules/string_rules.py` 增加极简 `normalize_company_name(value: str)`：仅做去首尾空白、半角/全角括号统一；复杂简称/行业后缀剔除仍留域层。

## 集成点（文件路径）

- 通用清洗：`src/work_data_hub/cleansing/rules/numeric_rules.py`
- Pydantic 集成：`src/work_data_hub/cleansing/integrations/pydantic_adapter.py`
- Excel 读取：`src/work_data_hub/io/readers/excel_reader.py`
- 年金域服务：`src/work_data_hub/domain/annuity_performance/service.py`

## 示例（片段）

1) 负百分比与全角百分号
```python
from decimal import Decimal
from src.work_data_hub.cleansing.rules.numeric_rules import comprehensive_decimal_cleaning

assert comprehensive_decimal_cleaning("-5%", "当期收益率") == Decimal("-0.050000")
assert comprehensive_decimal_cleaning("12.3％", "当期收益率") == Decimal("0.123000")
assert comprehensive_decimal_cleaning(-12.3, "当期收益率") == Decimal("-0.123000")
```

2) Excel 列名含换行/制表符
```text
原列名: "期初资产规模\n(万元)"、"当期收益率\t(%)"
读取后列名: "期初资产规模(万元)"、"当期收益率(%)"
```

3) 年金域 `组合代码` 前缀
```python
输入: {"组合代码": "F12345"}  →  输出: {"组合代码": "12345"}
```

## 验证与命令（Validation Gates）

基础校验（保持绿灯）：
```bash
uv venv && uv sync
uv run ruff format .
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```

聚焦用例（新增/调整）：
```bash
# 通用清洗：负百分比/全角百分号/仅货币符号为空
uv run pytest -v tests/test_cleansing_framework.py -k "percentage or percent or currency"

# ExcelReader：列名换行/制表符归一化
uv run pytest -v tests/io/readers/test_excel_reader.py -k "header or column or newline or tab"

# 年金域：组合代码 ^F 前缀剥离
uv run pytest -v tests/domain/annuity_performance/test_service.py -k "组合代码 or portfolio or prefix"
```

## 验收标准（Acceptance Criteria）

- 数值清洗
  - `"-5%"` → `Decimal("-0.050000")` 于收益率字段；
  - `"12.3％"` 与 `"12.3%"` 结果一致；
  - 非收益率字段的 `-5` 保持 `-5` 数值，不误作百分比；
  - 仅包含货币符号/分隔符的值经标准化后应返回 `None`（经空值规则判定）。
- ExcelReader 列名
  - 读取后列名不包含 `\n`/`\t`；
  - `project_columns` 不因换行/制表符导致列遗漏。
- 年金域
  - `组合代码` 若以 `F` 开头，读取/转换后不再含该前缀；
  - 其它字段与现状保持一致，无非预期变更。
- 回归
  - 现有测试全部通过；新增测试通过；无性能退化和异常告警增加。

## 风险与缓解

- 百分比歧义：`0.95` 在收益率字段按“已是小数”处理，只有 `abs(value) > 1` 才视为百分比（与现行为一致且可解释）。
- 列名归一化引发重名：极少见，如发生按 pandas 默认覆盖处理；属于可接受权衡。
- 货币符号集合有限：当前覆盖 `¥/$/￥/€/£/₽`，后续如遇新符号按需要增补，不预先过度设计。

## 回滚策略

- 数值规则：回滚 `handle_percentage_conversion` 的本次增量改动即可。
- 列名标准化：去除列名 `replace("\n", "").replace("\t", "")` 即可回退。
- 年金域前缀：移除该行处理逻辑即可回退，不影响其它域。

## 任务拆分与交付物

1) 数值规则增强 + 单测（tests/test_cleansing_framework.py）
2) Excel 列名归一化 + 单测（tests/io/readers/test_excel_reader.py 新增/补充）
3) 年金域前缀剥离 + 单测（tests/domain/annuity_performance/test_service.py 补充）
4) 文档更新：本 INITIAL.md、`docs/overview/MIGRATION_REFERENCE.md` 附注“清洗与映射边界”一句（可选）

## 参考与对齐

- `README.md`（唯一当前概览入口）
- `ROADMAP.md`（状态唯一事实源）：将该任务标记为 M1 辅助性改进
- `docs/overview/MIGRATION_REFERENCE.md`（迁移总览）：确认 Mapping Service 的职责边界（M2）
- `docs/overview/LEGACY_WORKFLOW_ANALYSIS.md`（legacy事实）：核对 legacy 清洗点与本次等价覆盖
- Pydantic v2 文档（集成方式参考）

—— 本 INITIAL 坚持 KISS：通用组件仅承载“已复用且简单”的数值与输入标准化；坚持 YAGNI：强业务清洗暂留域层或 M2，按需推进。
