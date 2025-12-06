# /crawler/eqc_crawler.py

import json
import os
import pandas as pd
import requests
import urllib3
from urllib.parse import quote
from pypac import PACSession
from logger.logger import logger
from config_manager.config_manager import config


class EqcCrawler:
    def __init__(self, token):
        # Disable InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        pac_config = config.get_pac_config()
        self.session = PACSession(
            pac_url=pac_config["url"],
            proxy_auth=requests.auth.HTTPProxyAuth(*pac_config["auth"]),
        )
        self.session.verify = False
        self.headers = config.get_base_headers()
        self.token = token

    def scrape_data(self, key_word, is_id=False):
        if is_id:
            return self._scrape_by_id(key_word)
        else:
            return self._scrape_by_keyword(key_word)

    def _scrape_by_id(self, key_word):
        business_info = self.get_business_info(key_word)
        biz_label = self.parse_label_info(self.get_label_info(key_word))
        key_word = business_info.get("company_name")
        base_info = self.get_base_info(key_info=key_word)
        logger.info(f"Successfully scraped data for {key_word}")
        return base_info, business_info, biz_label

    def _scrape_by_keyword(self, key_word):
        base_info = self.get_base_info(key_info=key_word)
        company_id = base_info.get("companyId")

        if not company_id:
            return None, None, None

        business_info = self.get_business_info(company_id)
        biz_label = self.parse_label_info(self.get_label_info(company_id))
        logger.info(f"Successfully scraped data for {key_word}")
        return base_info, business_info, biz_label

    def get_base_info(self, key_info):
        try:
            url = f"https://eqc.pingan.com/kg-api-hfd/api/search/?key={quote(str(key_info))}"
            headers = dict(
                self.headers,
                **{"Referer": "https://eqc.pingan.com/", "token": self.token},
            )
            logger.info("scrape CompanyID of key word [ %s ]", key_info)
            response = self.session.get(url=url, headers=headers)
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response text: {response.text}")
            if response.status_code == requests.codes.ok:
                logger.info("catch CompanyID of key word [ %s ]", key_info)
                js = json.loads(response.content.decode("utf-8")).get("list", None)
                result = {} if js is None or len(js) == 0 else dict(js[0])
                result["search_key_word"] = key_info
                return result
            else:
                logger.error(
                    "get invalid status code %s while scrape CompanyID [ %s ]",
                    response.status_code,
                    key_info,
                )
                return {}
        except requests.RequestException as e:
            logger.error(f"Error occurred while scrape CompanyID [ {key_info} ]: {e}")
            return {}

    def get_business_info(self, company_id):
        try:
            url = f"https://eqc.pingan.com/kg-api-hfd/api/search/findDepart?targetId={company_id}"
            headers = dict(
                self.headers,
                **{"Referer": "https://eqc.pingan.com/", "token": self.token},
            )
            logger.info("scrape BusinessInfo of CompanyID [ %s ]", company_id)
            response = self.session.get(url=url, headers=headers)
            if response.status_code == requests.codes.ok:
                logger.info("catch BusinessInfo of CompanyID [ %s ]", company_id)
                js = json.loads(response.content.decode("utf-8")).get(
                    "businessInfodto", None
                )
                result = {} if js is None else dict(js)
                return result
            else:
                logger.error(
                    "get invalid status code %s while scrape BusinessInfo [ %s ]",
                    response.status_code,
                    company_id,
                )
                return {}
        except requests.RequestException as e:
            logger.error(
                f"Error occurred while scrape BusinessInfo [ {company_id} ]: {e}"
            )
            return {}

    def get_label_info(self, company_id):
        try:
            url = f"https://eqc.pingan.com/kg-api-hfd/api/search/findLabels?targetId={company_id}"
            headers = dict(
                self.headers,
                **{"Referer": "https://eqc.pingan.com/", "token": self.token},
            )
            logger.info("scrape LabelInfo of CompanyID [ %s ]", company_id)
            response = self.session.get(url=url, headers=headers)
            if response.status_code == requests.codes.ok:
                logger.info("catch LabelInfo of CompanyID [ %s ]", company_id)
                js = json.loads(response.content.decode("utf-8")).get("labels", None)
                result = {} if js is None else js
                return result
            else:
                logger.error(
                    "get invalid status code %s while scrape LabelInfo [ %s ]",
                    response.status_code,
                    company_id,
                )
                return {}
        except requests.RequestException as e:
            logger.error(f"Error occurred while scrape LabelInfo [ {company_id} ]: {e}")
            return {}

    @staticmethod
    def parse_label_info(labels_json):
        all_labels = []
        for key in labels_json:
            for lab in key["labels"]:
                # 如果 companyId 为空，尝试从兄弟节点中获取
                if lab["companyId"] is None:
                    for sibling in key["labels"]:
                        if sibling["companyId"]:
                            lab["companyId"] = sibling["companyId"]
                            break

                labels = {
                    "type": key["type"],
                    "companyId": lab["companyId"],
                    "lv1Name": lab["lv1Name"],
                    "lv2Name": lab["lv2Name"],
                    "lv3Name": lab["lv3Name"],
                    "lv4Name": lab["lv4Name"],
                }
                all_labels.append(labels)

        logger.info("parse LabelInfo successfully!")
        return all_labels

    @staticmethod
    def save_to_excel(base_info, business_info, biz_label, save_path):
        company_name = base_info.get("companyFullName")
        unite_code = base_info.get("unite_code")

        file_path = f"{save_path}\\{unite_code}-{company_name}.xlsx"
        if not os.path.exists(file_path):
            df1 = pd.DataFrame([base_info])
            df2 = pd.DataFrame([business_info])
            df3 = pd.DataFrame(biz_label)
            with pd.ExcelWriter(file_path) as writer:
                df1.to_excel(writer, sheet_name="BaseInfo", index=False)
                df2.to_excel(writer, sheet_name="BusinessInfo", index=False)
                df3.to_excel(writer, sheet_name="BizLabel", index=False)
                logger.info(f"Data saved to {file_path}.")

    @staticmethod
    def save_to_mongodb(key_word, base_info, business_info, biz_label, db_manager):
        if not db_manager:
            logger.error("No MongoDBManager instance provided.")
            return

        # 插入数据到各个集合
        db_manager.insert_data("base_info", base_info)
        db_manager.insert_data("business_info", business_info)

        # 批量插入 biz_label 数据
        if biz_label:
            db_manager.insert_many_data("biz_label", biz_label)

        # 插入关键词与抓取结果的关系
        search_result = {
            "key_word": key_word,
            "company_id": base_info.get("company_id"),
            "company_name": base_info.get("companyFullName"),
            "unite_code": base_info.get("unite_code"),
            "result": "Success" if base_info and business_info else "Failed",
        }
        db_manager.insert_data("eqc_search_result", search_result)
