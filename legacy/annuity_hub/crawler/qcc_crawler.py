# /crawler/qcc_crawler.py

import os
import pandas as pd
import re
import requests
import urllib3
from lxml import etree
from urllib.parse import quote
from logger.logger import logger
from config_manager.config_manager import config
from pypac import PACSession


class QccCrawler:
    def __init__(self, cookie):
        # Disable InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        pac_config = config.get_pac_config()
        self.session = PACSession(
            pac_url=pac_config["url"],
            proxy_auth=requests.auth.HTTPProxyAuth(*pac_config["auth"]),
        )
        self.session.verify = False
        self.headers = config.get_base_headers()
        self.headers.update({"Referer": "https://www.qcc.com/", "cookie": cookie})

    def scrape_data(self, key_word):
        try:
            url = f"https://www.qcc.com/web/search?key={quote(str(key_word))}"
            logger.info("scrape CreditCode of key_word (%s) -- %s", key_word, url)
            response = self.session.get(url=url, headers=self.headers)
            if response.status_code == requests.codes.ok:
                # 将 response.text 保存到本地文件中以供后续分析
                # with open(f'temp_response_{key_word}.html', 'w', encoding='utf-8') as f:
                #     f.write(response.text)
                # logger.info(f'Response text for {key_word} saved to temp_response_{key_word}.html')

                html = etree.HTML(response.text)
                company_name = html.xpath(
                    'normalize-space(//table[1]/tr[1]//div[@class="maininfo"]/span//a[@class="title copy-value"]//text())'
                )
                company_name = "".join(company_name)
                company_link = html.xpath(
                    '//table[1]/tr[1]//div[@class="maininfo"]//a[contains(@href, "https://www.qcc.com/firm/")]/@href'
                )
                former_name = html.xpath(
                    'normalize-space(//table[1]/tr[1]//div[@class="maininfo"]//div[@class="relate-info"]//span[contains(text(), "曾用名")]/span//text())'
                )
                former_name = "".join(former_name)
                company_type = html.xpath(
                    'normalize-space(//table[1]/tr[1]//div[@class="maininfo"]//div[@class="relate-info"]/div/span[4]/text())'
                )
                company_type = company_type.replace("：", "")
                code = html.xpath(
                    'normalize-space(//table[1]/tr[1]//div[@class="maininfo"]//div[@class="relate-info"]/div/span[4]/span//text())'
                )
                code = "".join(code)
                logger.info("catch CreditCode of key_word (%s)", key_word)
                return {
                    "key_words": key_word,
                    "company_name": company_name,
                    "company_link": company_link,
                    "former_name": former_name,
                    "type": company_type,
                    "code": code,
                    "result": "Accurate"
                    if key_word == company_name or key_word == former_name
                    else "Elastic",
                }
            else:
                logger.error(
                    "get invalid status code %s while scrape %s",
                    response.status_code,
                    key_word,
                )
                return None
        except requests.RequestException as e:
            logger.error("error occurred while scrape %s: %s", key_word, e)
            return None

    @staticmethod
    def save_to_excel(data, save_path):
        company_name = data.get("company_name")
        code = data.get("code")

        # 清理文件名中的非法字符
        safe_company_name = re.sub(r'[\/:*?"<>|\n\r]+', "_", company_name)

        file_path = f"{save_path}\\{code}-{safe_company_name}.xlsx"
        if not os.path.exists(file_path):
            df = pd.DataFrame([data])
            with pd.ExcelWriter(file_path) as writer:
                df.to_excel(writer, sheet_name="SearchResults", index=False)
                logger.info(f"Data saved to {file_path}.")

    @staticmethod
    def save_to_mongodb(data, db_manager):
        if not db_manager:
            logger.error("No MongoDBManager instance provided.")
            return

        # 插入数据到 CompanyInfo 集合
        db_manager.insert_data("qcc_search_result", data)
