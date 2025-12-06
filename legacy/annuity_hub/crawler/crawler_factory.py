from importlib import import_module
from logger.logger import logger


class CrawlerFactory:
    """
    Factory class to create crawler instances based on provided mappings.

    :param mappings: A list of dictionaries, each dictionary contains the mapping
                     information for creating a specific crawler. Expected format:
                     [
                         {
                             'keyword': 'unique_keyword',
                             'crawler_class': 'CrawlerClassName',
                             'target_database': 'database_name',
                             'target_collection': 'collection_name',
                             'auth_token': 'auth_token_value'
                         },
                         ...
                     ]
    """

    def __init__(self, mappings: list = None):
        """
        Initializes the CrawlerFactory with specified mappings.

        :param mappings: List of dictionaries containing mapping data.
        """
        self.mappings = mappings
        self.crawler_module = r"crawler.eqc_crawler"

    def create_crawler(self, crawler_name):
        try:
            module = import_module(self.crawler_module)
            crawler_class = getattr(module, crawler_name)
            return crawler_class
        except Exception as e:
            logger.error(f"Error creating crawler {crawler_name}. Error: {e}")
            return None

    def create_crawlers(self, keyword: str = None) -> list:
        """
        Creates crawler instances based on the specified keyword.

        :param keyword: A string keyword to identify which crawler(s) to create.
                        If the keyword is None, an empty list is returned.
        :return: A list of crawler instances corresponding to the matched keyword.
        """
        if keyword:
            matched_mappings = [m for m in self.mappings if m["keyword"] == keyword]
            crawlers = []
            for m in matched_mappings:
                try:
                    module = import_module(self.crawler_module)
                    crawler_class = getattr(module, m["crawler_class"])
                    crawlers.append(
                        crawler_class(
                            m["auth_token"],
                            m["target_database"],
                            m["target_collection"],
                        )
                    )
                except KeyError as e:
                    logger.error(f"Error fetching the crawler class: {e}")
                except Exception as e:
                    logger.error(f"Error creating the crawler class: {e}")
            return crawlers
        return []
