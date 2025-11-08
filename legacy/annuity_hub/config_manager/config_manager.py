import os
import requests
import urllib3
from pypac import PACSession


class ConfigManager:
    def __init__(self):
        # MySQL configuration(# admin:payl12@10.179.53.136)
        self.MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
        self.MYSQL_PORT = 3306
        self.MYSQL_USER = os.environ.get("MYSQL_USER", "root")
        self.MYSQL_PASS = os.environ.get("MYSQL_PASS", "169828")
        self.CHARSET = 'utf8mb4'
        self.DB_NAME = "mis"
        self.DIMENSION_DB_NAME = "dimension"
        self.DATA_HANDLER_MAPPING = 'annuity_mapping'

        # Driver Configuration
        self.ACCESS_DRIVER = '{Microsoft Access Driver (*.mdb, *.accdb)}'

        # LocalFile configuration
        self.BASE_DIR = r'D:\Share\DATABASE'
        self.DAILY_SOURCE = os.path.join(self.BASE_DIR, 'Daily Update')
        self.MONTHLY_SOURCE = os.path.join(self.BASE_DIR, 'Monthly Update')

        # Other constants
        self.API_ENDPOINT = "https://api.example.com/v1/"
        self.DEBUG_MODE = True

        # Crawler configuration
        self.PAC_URL = r'http://proxy.paic.com.cn/proxyformwg.pac'
        self.PROXY_AUTH_USER = 'LINSUISHENG034'
        self.PROXY_AUTH_PASS = 'Lin20250101'
        self.BASE_HEADERS = {
            'User-Agent': r'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/101.0.0.0 Safari/537.36',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9'
        }

    def get_mysql_config(self):
        return {
            "host": self.MYSQL_HOST,
            "port": self.MYSQL_PORT,
            "user": self.MYSQL_USER,
            "pass": self.MYSQL_PASS,
            "charset": self.CHARSET,
            "db_name": self.DB_NAME
        }

    def get_local_file_config(self):
        return {
            "daily_source": self.DAILY_SOURCE,
            "monthly_source": self.MONTHLY_SOURCE
        }

    def get_other_config(self):
        return {
            "api_endpoint": self.API_ENDPOINT,
            "debug_mode": self.DEBUG_MODE
        }

    def get_access_driver_config(self):
        return {
            "access_driver": self.ACCESS_DRIVER
        }

    # region >> Crawler Setting
    def get_pac_config(self):
        return {
            "url": self.PAC_URL,
            "auth": (self.PROXY_AUTH_USER, self.PROXY_AUTH_PASS)
        }

    def get_base_headers(self):
        return self.BASE_HEADERS

    @staticmethod
    def get_qcc_cookie(is_manual=False):

        # Disable InsecureRequestWarning
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 从配置中获取代理设置
        pac_config = config.get_pac_config()

        # 初始化 PACSession 并设置代理
        session = PACSession(pac_url=pac_config['url'], proxy_auth=requests.auth.HTTPProxyAuth(*pac_config['auth']))
        session.verify = False  # 如果有SSL验证问题，可以禁用

        # 设置请求头
        headers = config.get_base_headers()

        # 访问 QCC 网站的 URL
        url = 'https://www.qcc.com/'

        # 发送 GET 请求
        response = session.get(url, headers=headers)

        if is_manual:
            cookie = r'qcc_did=23a5d00e-6feb-4640-aa1d-b125b209de6b; UM_distinctid=19191d566df120c-05119f0d37998-26031951-144000-19191d566e011e4; QCCSESSID=eb851419dd14feaba741ac374e; _uab_collina=172483450179300085212658; tfstk=fJhm6k9a8xyfkX_9mbVXBKkqwyvRGiN_UcCTX5EwUur5DiCx75ribuhYDqFVb1mi4onxHVQjFD3FMjpb61Vb15-pvBddlqN__iVpRzqjz4aZ1YIfiqgb1aamY2islOflX6Tg_cPzaPa0_P54QUbz-u547szN4U4_4lPa3ourzP4CbG540fFk3oGZab-2s5vXlynsZr2yeqrPlWluo-qEubfN_wz0nku4qHnbi_er5Rc1512-uvi_8mS2jlGozjkEY3BY0v4iJAmeWta8IjNubjRC-ulmSb2jeBSuPYuxQjicS1zjMXegA8YN1RFr9JkEmNTIzSzZfJG9AsZq72GIpWAcArDr-7jrmTWe_E1_zFhlCOw4PzqCSIx-J_BNx4Lkr98_3zabvfLlFVIC_1EBrUXeS-z7ut5..; acw_tc=0a47318217249244650367740e003ae37794a899fd94d6a2bd366cb7f49b90; CNZZDATA1254842228=1250018733-1724728568-https%253A%252F%252Fcn.bing.com%252F%7C1724924467'
            return cookie
        # 检查响应状态码并获取 Cookie
        elif response.status_code == 200:
            cookies = response.cookies.get_dict()
            cookie_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])
            return cookie_str
        else:
            raise Exception(f"Failed to retrieve cookies from {url}. Status code: {response.status_code}")

    @staticmethod
    def get_eqc_token(is_manual=False):
        if is_manual:
            token = r'''725fba8ccce70e207b43a12921ae4d6b'''
            return token

    # endregion


config = ConfigManager()


if __name__ == '__main__':
    qcc_cookie = config.get_qcc_cookie()
    print(f"Retrieved QCC cookie: {qcc_cookie}")
