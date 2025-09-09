# Legacy架构工作流分析报告

本文档客观描述 legacy/annuity_hub 的实际工作流与实现细节，不包含迁移建议或新架构对比。参阅：`README.md`（开发者快速上手）、`ROADMAP.md`（计划与状态）。

## 一、核心工作流程

### 1.1 整体流程图

```text
[数据文件夹]
    ↓ (扫描)
[文件列表]
    ↓ (关键字匹配)
[Cleaner 选择]
    ↓ (数据清洗)
[DataFrame 缓存]
    ↓ (批量导入)
[MySQL 数据库]
```

### 1.2 详细步骤（基于源码）

#### Step 1: 文件扫描与过滤

```python
# legacy/annuity_hub/main.py line 44
valid_files = get_valid_files(process['data_folder'], exclude_keyword='已写入')
```

要点：

- 扫描指定目录并返回文件列表。
- 跳过临时文件（文件名含 `~$`）。
- 支持后缀过滤（可选）；本项目调用通过 `exclude_keyword='已写入'` 排除已处理文件。

相关实现：`legacy/annuity_hub/common_utils/common_utils.py:get_valid_files`

#### Step 2: 处理器映射匹配

```python
# legacy/annuity_hub/main.py line 42, 56
data_handler_mapping = get_data_handler_mapping(database_name='config', update_frequency=selected_process_type)
handlers = data_handler_mapping.to_dict(orient='records')
matching_handlers = [item for item in handlers if item['keyword'] in file.name]
```

要点：

- 处理器配置从数据库读取（表名由 `config.DATA_HANDLER_MAPPING` 指定）。
- 基于文件名包含 `keyword` 进行匹配；一个文件可匹配多个处理器。
- 存在预处理步骤 `prefix_processing(valid_files)`。

相关实现：`legacy/annuity_hub/data_handler/mappings.py:get_data_handler_mapping`

#### Step 3: 数据清洗与缓存

```python
# legacy/annuity_hub/data_handler/data_processor.py line 26-30
def clean(self, file_path):
    cleaner_class = self.cleaner_factory.create_cleaner(self.cleaner_class)
    cleaner = cleaner_class(file_path)
    data = cleaner.clean()
    self.data.append(data)
```

要点：

- 通过工厂创建 Cleaner 实例执行清洗，返回 DataFrame。
- `DataProcessor.data` 缓存多个 DataFrame；导入前使用 `pd.concat(self.data)` 合并。

相关实现：`legacy/annuity_hub/data_handler/cleaner_factory.py`、`legacy/annuity_hub/data_handler/data_cleaner.py`、`legacy/annuity_hub/data_handler/data_processor.py`

#### Step 4: 批量数据导入

```python
# legacy/annuity_hub/main.py line 73-80
with MySqlDBManager() as mysqldb:
    new_database = process.get("reselected_database", None)
    if new_database:
        mysqldb.switch_database(new_database)
    for processor in tqdm(processor_cache.values(), desc="Importing Database"):
        if not new_database:
            mysqldb.switch_database(processor['target_database'])
        processor.execute(mysqldb)
```

要点：

- 使用 `MySqlDBManager` 统一管理事务与连接；可按需切换目标数据库。
- 若配置 `update_based_on_field`，导入前先删除对应唯一组合的既有记录，再导入新数据。
- 导入失败时，失败数据写入 `temp` 数据库的 `temp_<table>`。

相关实现：`legacy/annuity_hub/data_handler/data_processor.py:execute/_import/delete_existing_records`

## 二、映射系统（基于 mappings.py）

### 2.1 映射来源

- 主要映射通过数据库加载为 Python 字典，并在进程内使用：
  - `BUSINESS_TYPE_CODE_MAPPING`（产品线 → 产品线代码）
  - `PRODUCT_ID_MAPPING`（产品明细 → 产品ID）
  - `PROFIT_METRICS_MAPPING`（指标名称 → 指标编码）
  - `COMPANY_BRANCH_MAPPING`（机构名称 → 机构代码，含补充字典）
  - `COMPANY_ID1_MAPPING` / `COMPANY_ID2_MAPPING` / `COMPANY_ID4_MAPPING` / `COMPANY_ID5_MAPPING`
- 特例：`COMPANY_ID3_MAPPING` 为硬编码字典。
- 处理器配置：`get_data_handler_mapping(database='config', update_frequency=...)` 返回 DataFrame（字段：`keyword/cleaner_class/target_database/target_table/update_based_on_field`）。

相关实现：`legacy/annuity_hub/data_handler/mappings.py`

## 三、其他实现细节

- 导入前进行列校验：导入列需为数据库表列的子集；不满足会输出 columns 差异并报错。
- 警告抑制：入口模块通过 `warnings.filterwarnings` 忽略特定 Warning（含 openpyxl）。

---

Last reviewed: 2025-09-09
