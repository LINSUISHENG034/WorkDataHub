# /run.py
import pandas as pd

from tqdm import tqdm
from textwrap import dedent

from logger.logger import logger
from config_manager.config_manager import config
from crawler.qcc_crawler import QccCrawler
from crawler.eqc_crawler import EqcCrawler
from database_operations.mongo_ops import MongoDBManager


class DataCrawler:
    def __init__(self, eqc_token, db_name='enterprise_data'):
        # 初始化数据库管理器
        self.mdb = MongoDBManager(database_name=db_name)

        # 初始化爬虫实例
        # self.qcc_crawler = QccCrawler(cookie=qcc_cookie)
        self.eqc_crawler = EqcCrawler(token=eqc_token)

    def scrape(self, keywords, is_id=False):
        # 去重关键词
        keywords = list(set(keywords))

        # 初始化进度条
        progress_bar = tqdm(total=len(keywords), desc="Progress", ascii=True)

        for key_word in keywords:
            if key_word:
                # EQC 平台抓取数据
                base_info, business_info, biz_label = self.eqc_crawler.scrape_data(key_word, is_id)
                if base_info and business_info and biz_label:
                    # 将 EQC 数据保存到 MongoDB
                    self.eqc_crawler.save_to_mongodb(key_word, base_info, business_info, biz_label, self.mdb)

            # 更新进度条
            progress_bar.update(1)

        # 关闭进度条
        progress_bar.close()

        # 结束流程
        logger.info("Data scraping and processing completed.")

    def _scrapy_from_eqc(self, key_word):
        # QCC 平台抓取数据
        qcc_data = self.qcc_crawler.scrape_data(key_word)
        if qcc_data:
            # 将 QCC 数据保存到 MongoDB
            QccCrawler.save_to_mongodb(qcc_data, self.mdb)
            # 提取公司代码并用于 EQC 平台的抓取
            company_code = qcc_data.get('code')
            if company_code:
                # EQC 平台抓取数据
                base_info, business_info, biz_label = self.eqc_crawler.scrape_data(company_code)
                if base_info and business_info and biz_label:
                    # 将 EQC 数据保存到 MongoDB
                    self.eqc_crawler.save_to_mongodb(key_word, base_info, business_info, biz_label, self.mdb)


# 使用示例
if __name__ == '__main__':
    # region >> 从配置中读取cookie和token
    # qcc_cookie = config.get_qcc_cookie(is_manual=True)
    # eqc_token = config.get_eqc_token(is_manual=True)
    # endregion

    # 手动配置token
    eqc_token = r'9d64a51d3435558e656c2956f962414d'

    # 初始化DataScraper类
    crawler = DataCrawler(eqc_token=eqc_token)

    selected_sub_process = int(input('Please enter an integer: '))

    # region >> 输入获取
    if selected_sub_process == 1:
        crawl_str = r'625091657,603254227,607519948,1904944425,608347154,616074572,641181923,641182935,637402542,601513054,601497262,631321723,600102670,602784500,613591762,604856838,602728951,638795949,1899177652,607380538,601730004,894741248,855791001'
        crawl_list = crawl_str.split(',')

        # manual crawl
        crawler.scrape(crawl_list, is_id=True)

        # import data
        from data_handler.extra_handler import sync_enterprise_data

        sync_enterprise_data()
    # endregion

    # region >> 清单获取
    elif selected_sub_process == 2:
        from database_operations.mysql_ops import MySqlDBManager

        with MySqlDBManager(database='business') as mysqldb:
            data = pd.read_sql('SELECT DISTINCT `客户名称` FROM `规模明细` WHERE `company_id` IS NULL;', mysqldb.engine)
            unique_list = data['客户名称'].dropna().tolist()

            # 执行数据爬取并存储
            crawler.scrape(unique_list)

            # 导入数据
            from data_handler.extra_handler import sync_enterprise_data

            sync_enterprise_data()
    # endregion
