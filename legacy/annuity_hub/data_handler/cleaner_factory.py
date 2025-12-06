from importlib import import_module

from logger.logger import logger


class CleanerFactory:
    """
    Factory class to create cleaner instances based on provided mappings.

    :param mappings: A list of dictionaries, each dictionary contains the mapping
                     information for creating a specific cleaner. Expected format:
                     [
                         {
                             'keyword': 'unique_keyword',
                             'cleaner_class': 'CleanerClassName',
                             'target_database': 'database_name',
                             'target_table': 'table_name',
                             'update_based_on_field': 'field_name'
                         },
                         ...
                     ]
    """

    def __init__(self, mappings: list = None):
        """
        Initializes the CleanerFactory with specified mappings.

        :param mappings: List of dictionaries containing mapping data.
        """
        self.mappings = mappings
        self.cleaner_module = r"data_handler.data_cleaner"

    def create_cleaner(self, cleaner_name):
        try:
            module = import_module(self.cleaner_module)
            cleaner_class = getattr(module, cleaner_name)
            return cleaner_class
        except Exception as e:
            logger.error(f"Error creating  cleaner {cleaner_name}. Error: {e}")
            return None

    # TODO: 针对同一文件通过关键字匹配创建多个cleaner
    def create_cleaners(self, keyword: str = None) -> list:
        """
        Creates cleaner instances based on the specified keyword.

        :param keyword: A string keyword to identify which cleaner(s) to create.
                        If the keyword is None, an empty list is returned.
        :return: A list of cleaner instances corresponding to the matched keyword.
        """
        if keyword:
            matched_mappings = [m for m in self.mappings if m["keyword"] == keyword]
            cleaners = []
            for m in matched_mappings:
                try:
                    module = import_module(self.cleaner_module)
                    cleaner_class = getattr(module, m["cleaner_class"])
                    cleaners.append(cleaner_class)
                except KeyError as e:
                    # 处理无法找到的类名
                    logger.error(f"Error fetching the cleaner class: {e}")
                except Exception as e:
                    # 处理其他可能的异常
                    logger.error(f"Error creating the cleaner class: {e}")
            return cleaners
        return []
