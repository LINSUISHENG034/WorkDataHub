import pandas as pd
import warnings

from tqdm import tqdm

from config_manager.config_manager import config
from common_utils.common_utils import get_valid_files
from data_handler.data_processor import DataProcessor
from database_operations.mysql_ops import MySqlDBManager
from data_handler.mappings import get_data_handler_mapping
from logger.logger import logger


def main():
    # Can add more data process options here
    processes = {
        "daily": {
            "reselected_database": "daily_update",
            "data_folder": config.DAILY_SOURCE,
        },
        "monthly": {"data_folder": config.MONTHLY_SOURCE},
        "test": {"reselected_database": "temp", "data_folder": config.MONTHLY_SOURCE},
    }

    # Show processes
    print(f"Available processes: {', '.join(processes.keys())}")

    # selected_process_type = input('Enter a process to run: ').lower()
    selected_process_type = "monthly"

    if selected_process_type not in processes.keys():
        return logger.info("Please select a valid import type.")

    # Run Process
    print(
        f"{selected_process_type.capitalize()} processing is currently running...".center(
            60, "*"
        )
    )
    process = processes.get(selected_process_type)
    data_handler_mapping = get_data_handler_mapping(
        database_name="config", update_frequency=selected_process_type
    )
    handlers = data_handler_mapping.to_dict(orient="records")
    valid_files = get_valid_files(process["data_folder"], exclude_keyword="已写入")

    # 用于缓存DataProcessor实例的字典
    processor_cache = {}

    # 预处理年金计划信息(可关闭)
    from data_handler.extra_handler import prefix_processing

    prefix_processing(valid_files)

    # 遍历处理所有文件
    for file in tqdm(valid_files, desc="Processing Data"):
        # 获取所有符合条件的处理器
        matching_handlers = [item for item in handlers if item["keyword"] in file.name]
        if not matching_handlers:
            continue

        # 对每个符合条件的处理器进行处理
        for handler in matching_handlers:
            # 检查是否已有缓存的DataProcessor实例，确保相同Cleaner只创建一个DataProcessor
            cleaner_class = handler["cleaner_class"]
            if cleaner_class in processor_cache:
                processor = processor_cache[cleaner_class]
            else:
                processor = DataProcessor(**handler)
                processor_cache[cleaner_class] = processor  # 缓存实例

            processor.clean(str(file))

    # 所有文件处理完毕后，进行数据导入
    with MySqlDBManager() as mysqldb:
        new_database = process.get("reselected_database", None)
        if new_database:
            mysqldb.switch_database(new_database)
        for processor in tqdm(processor_cache.values(), desc="Importing Database"):
            if not new_database:
                mysqldb.switch_database(processor["target_database"])
            processor.execute(mysqldb)


if __name__ == "__main__":
    # 通过设置mode.chained_assignment选项，可以更改Pandas如何处理链式赋值
    pd.options.mode.chained_assignment = None

    # 忽略特定模块的特定类别警告
    warnings.filterwarnings(
        action="ignore",
        category=Warning,
        module=r"common_utils\.common_utils|data_handler\.(data_cleaner|cleaner_factory)",
    )
    warnings.filterwarnings(action="ignore", category=UserWarning, module="openpyxl")

    # 忽略openpyxl模块中特定的UserWarning
    warnings.filterwarnings(
        action="ignore",
        category=UserWarning,
        module=r"openpyxl\.styles\.stylesheet",
        message="Workbook contains no default style, apply openpyxl's default",
    )

    warnings.filterwarnings(
        action="ignore",
        message=(
            r"""Workbook contains no default style, apply openpyxl\'s default'"""
            r"""warn("Workbook contains no default style, apply openpyxl\'s default")"""
            r"""UserWarning: pandas only supports SQLAlchemy connectable"""
        ),
    )

    main()
