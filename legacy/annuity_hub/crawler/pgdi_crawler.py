import json
import os
import pandas as pd
import requests
import re
import urllib3
import time
from bs4 import BeautifulSoup
from urllib.parse import quote
from pypac import PACSession
from logger.logger import logger
from config_manager.config_manager import config
from database_operations.mongo_ops import MongoDBManager


class GpdiCrawler:
    def __init__(self, db_name="enterprise_data"):
        # Disable InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 初始化数据库管理器
        self.mdb = MongoDBManager(database_name=db_name)

        # PAC基本设置
        pac_config = config.get_pac_config()
        self.session = PACSession(
            pac_url=pac_config["url"],
            proxy_auth=requests.auth.HTTPProxyAuth(*pac_config["auth"]),
        )
        self.session.verify = False
        self.headers = config.get_base_headers()

        # 定义关键词列表
        self.china_mobile_keywords = [
            "中国移动",
            "中国移动通信集团有限公司",
            "中国移动有限公司",
            # 添加其他子公司名称
        ]

        self.health_keywords = [
            "补充医疗保险",
            "健康委托",
            # 添加其他相关关键词
        ]

    @staticmethod
    def contains_keywords(content, keywords):
        """检查内容是否包含指定的关键词列表中的任何一个"""
        for keyword in keywords:
            if keyword in content:
                return True
        return False

    @staticmethod
    def contains_china_mobile(content):
        # 关键词列表
        china_mobile_keywords = [
            "中国移动",
            "中国移动通信集团有限公司",
            "中国移动有限公司",
            "广东移动",
            "北京移动",
            # ... 添加其他子公司名称
        ]
        """判断内容是否涉及中国移动或其下属子公司"""
        for keyword in china_mobile_keywords:
            if keyword in content:
                return True
        return False

    @staticmethod
    def extract_key_data(content):
        """从内容中提取公司名称、员工人数、到期时间、规模等关键数据"""
        key_data = {}

        # 提取公司名称
        company_name_patterns = [
            r"采购人[:：]\s*(\S+)",
            r"招标人[:：]\s*(\S+)",
        ]
        for pattern in company_name_patterns:
            match = re.search(pattern, content)
            if match:
                key_data["company_name"] = match.group(1)
                break

        # 提取员工人数
        employee_count_pattern = r"员工人数[:：]\s*(\d+)"
        match = re.search(employee_count_pattern, content)
        if match:
            key_data["employee_count"] = int(match.group(1))

        # 提取到期时间
        expiry_date_pattern = r"到期时间[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)"
        match = re.search(expiry_date_pattern, content)
        if match:
            key_data["expiry_date"] = match.group(1)

        # 提取规模
        scale_pattern = r"(合同金额|规模)[:：]\s*([\d\.]+)(万元|元|亿)"
        match = re.search(scale_pattern, content)
        if match:
            key_data["scale"] = match.group(2) + match.group(3)

        return key_data

    def scrape_all_pages(self, total_pages=245):
        """提取指定页数内的所有信息。"""
        base_url = "https://www.gpdi.com/homepage/cggg/index{}.jspx"
        all_data = []

        for page_num in range(1, total_pages + 1):
            if page_num == 1:
                # 首页 URL 与其他页不同
                url = base_url.format("")
            else:
                url = base_url.format(f"_{page_num}")
            logger.info("正在请求页面: %s", url)
            page_data = self.scrape_li_elements(url)

            # 分页插入数据
            self.mdb.insert_many_data("bid_info", page_data)

            all_data.extend(page_data)

            # 可选：添加延迟，避免对服务器造成过大压力
            time.sleep(1)

        return all_data

    def scrape_li_elements(self, url):
        """从给定 URL 提取列表页信息。"""
        try:
            response = self.session.get(url, headers=self.headers)
            if response.status_code == requests.codes.ok:
                soup = BeautifulSoup(response.content, "lxml")
                # 选择所有匹配的<li>标签
                li_elements = soup.select(
                    "div.index-content div.right.list-right div.common-list ul.common-ul.common-current-ul li"
                )
                logger.info("成功获取页面中的<li>标签")

                # 提取每个<li>标签中的信息
                li_data = []
                for li in li_elements:
                    # 提取具有 data-url 属性的<a>标签
                    a_tag = li.select_one("p.pull-left > a[data-url]")
                    if a_tag:
                        data_url = a_tag.get("data-url")
                        text = a_tag.get_text(strip=True)
                    else:
                        data_url = None
                        text = None

                    # 提取具有类 "pull-right time" 的<i>标签
                    i_tag = li.select_one("i.pull-right.time")
                    if i_tag:
                        publication_date = i_tag.get_text(strip=True)
                    else:
                        publication_date = None

                    # 获取详情页内容
                    if data_url:
                        detail_data = self.scrape_detail_page(data_url)
                    else:
                        detail_data = {}

                    # 关键信息提取
                    content = detail_data.get("content")
                    key_data = self.extract_key_data(content)

                    item = {
                        "data_url": data_url,
                        "text": text,
                        "publication_date": publication_date,
                        "detail_title": detail_data.get("title"),
                        "detail_source": detail_data.get("source"),
                        "detail_content": detail_data.get("content"),
                        "is_china_mobile": self.contains_keywords(
                            content, self.china_mobile_keywords
                        ),
                        "has_key_product": self.contains_keywords(
                            content, self.health_keywords
                        ),
                        "company_name": key_data.get("company_name"),
                        "employee_count": key_data.get("employee_count"),
                        "expiry_date": key_data.get("expiry_date"),
                        "scale": key_data.get("scale"),
                    }

                    li_data.append(item)
                    logger.debug(
                        f"找到项 - data-url: {data_url}, 文本: {text}, 发布时间: {publication_date}"
                    )

                return li_data
            else:
                logger.error("无法获取页面，状态码: %s", response.status_code)
                return []
        except requests.RequestException as e:
            logger.error(f"请求页面时发生错误: {e}")
            return []

    def scrape_detail_page(self, data_url):
        """从 data_url 对应的详情页提取所需信息。"""
        try:
            # 有些链接可能是相对路径，需要拼接
            if not data_url.startswith("http"):
                data_url = requests.compat.urljoin("https://www.gpdi.com/", data_url)
            logger.info("正在请求详情页: %s", data_url)
            response = self.session.get(data_url, headers=self.headers)
            if response.status_code == requests.codes.ok:
                soup = BeautifulSoup(response.content, "lxml")

                # 提取标题
                title_tag = soup.select_one("div.detail-content div.content h4")
                title = title_tag.get_text(strip=True) if title_tag else None

                # 提取消息源
                source_tag = soup.select_one("div.detail-content div.content p.current")
                source = source_tag.get_text(strip=True) if source_tag else None

                # 提取正文内容
                p_tags = soup.select("div.detail-content div.content p[style]")
                content_paragraphs = []
                for p in p_tags:
                    text = p.get_text(strip=True)
                    content_paragraphs.append(text)

                content = "\n".join(content_paragraphs)

                logger.info("成功提取详情页内容")
                return {"title": title, "source": source, "content": content}
            else:
                logger.error("无法获取详情页，状态码: %s", response.status_code)
                return {}
        except requests.RequestException as e:
            logger.error(f"请求详情页时发生错误: {e}")
            return {}


if __name__ == "__main__":
    test_crawler = GpdiCrawler()
    all_data = test_crawler.scrape_all_pages(total_pages=245)

    # 打印或处理获取的数据
    for item in all_data:
        print(f"详情页标题: {item['detail_title']}")
