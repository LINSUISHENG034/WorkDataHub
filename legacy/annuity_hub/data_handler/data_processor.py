import pandas as pd

from common_utils.common_utils import get_unique_combinations
from database_operations.mysql_ops import MySqlDBManager
from data_handler.cleaner_factory import CleanerFactory
from logger.logger import logger


class DataProcessor:
    def __init__(self, **kwargs):
        self.cleaner_class = kwargs.get('cleaner_class')
        self.target_database = kwargs.get('target_database')
        self.target_table = kwargs.get('target_table')
        self.update_based_on_field = kwargs.get('update_based_on_field')
        self.cleaner_factory = kwargs.get('cleaner_factory', CleanerFactory())
        self.database_manager = kwargs.get('database_manager', MySqlDBManager(database=self.target_database))
        self.data = []

    def __getitem__(self, key):
        # 检查请求的属性是否存在
        if hasattr(self, key):
            return getattr(self, key)
        else:
            raise KeyError(f"Property '{key}' not found in the instance.")

    def clean(self, file_path):
        cleaner_class = self.cleaner_factory.create_cleaner(self.cleaner_class)
        cleaner = cleaner_class(file_path)
        data = cleaner.clean()
        self.data.append(data)
        return data

    def delete_existing_records(self, db: MySqlDBManager, data: pd.DataFrame, fields: str):
        """
        根据指定字段的唯一组合，从数据库的指定表中删除记录。

        Args:
        - db (MySqlDBManager): 数据库管理器实例。
        - data (pd.DataFrame): 数据源。
        - fields (str): 需要组合的字段名，可以是单一字段，也可以是多个字段组合（用"+"分隔）。
        """
        # 解析字段，如果包含 "+" 则为多字段组合
        field_list = fields.split("+")

        # 获取唯一组合
        unique_combinations = get_unique_combinations(data, field_list)

        # 从数据库中删除这些组合对应的记录
        db.delete_rows_by_criteria(table_name=self.target_table, criteria=unique_combinations, fields=field_list)

    def _import(self, db: MySqlDBManager):
        # 检查 db 是否是 MySqlDBManager 的实例
        if not isinstance(db, MySqlDBManager):
            raise TypeError("db must be an instance of MySqlDBManager")

        data = pd.concat(self.data, ignore_index=True)

        import_columns = data.columns.to_list()
        database_columns = db.get_column_names(table_name=self.target_table)

        if not set(import_columns).issubset(set(database_columns)):
            info = {'table_name': self.target_table, 'import_columns': sorted(import_columns),
                    'database_columns': sorted(database_columns)}
            logger.error(info)
            raise ValueError(f"Import columns do not match database columns for table {self.target_table}")

        # 调用统一的删除方法
        if self.update_based_on_field:
            self.delete_existing_records(db, data, self.update_based_on_field)

        try:
            db.import_data(table_name=self.target_table, data=data, delete_existing=False)
        except Exception as e:
            self._log_and_handle_error(data, table_name=self.target_table, error=e)

    def _log_and_handle_error(self, data: pd.DataFrame, table_name: str, error: Exception):
        if "import_data" in str(error):
            logger.error(f'Error importing data to {table_name}: {str(error)}')
        else:
            logger.error(f'Unexpected error importing data to {table_name}: {str(error)}')
        self._handle_failed_import(data, table_name)

    @staticmethod
    def _handle_failed_import(data: pd.DataFrame, table_name: str):
        temp_db_manager = MySqlDBManager(database='temp')
        temp_table_name = f"temp_{table_name}"
        try:
            temp_db_manager.import_data(table_name=temp_table_name, data=data, delete_existing=False)
            logger.info(f"Failed data imported to temp database in table {temp_table_name}")
        except Exception as temp_e:
            logger.error(f'Error importing data to temp database: {str(temp_e)}')
        # 不再重新抛出异常，以避免重复记录错误

    def execute(self, db: MySqlDBManager):
        try:
            self._import(db)
        except ValueError as e:
            logger.error(f'Import error: {e}')
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
