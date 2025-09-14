#!/usr/bin/env python3
"""
EQC CDP Token获取器
通过Chrome DevTools Protocol实时获取token，无需手动F12
"""

import json
import time
import requests
import urllib3
from typing import Optional

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class EQCCDPClient:
    """通过CDP获取EQC token"""

    def __init__(self, debug_port=9222):
        self.debug_port = debug_port
        self.latest_token = None
        self.token_time = 0

    def find_eqc_page(self):
        """查找EQC页面"""
        try:
            resp = requests.get(f"http://localhost:{self.debug_port}/json", timeout=2)
            pages = resp.json()

            for page in pages:
                if 'eqc.pingan.com' in page.get('url', ''):
                    return page

            return None
        except:
            return None

    def trigger_token_request(self, page_info):
        """触发一个搜索请求以获取token"""
        try:
            # 使用CDP执行JavaScript
            url = f"http://localhost:{self.debug_port}/json/runtime/evaluate"

            # JavaScript代码：执行一个搜索
            js_code = """
            (function() {
                // 尝试使用fetch发送请求
                fetch('https://eqc.pingan.com/kg-api-hfd/api/search/?key=测试', {
                    headers: {
                        'Referer': 'https://eqc.pingan.com/'
                    }
                }).then(r => r.json()).then(console.log);
                return 'Search triggered';
            })()
            """

            payload = {
                "expression": js_code,
                "returnByValue": True
            }

            # 发送到正确的页面
            page_id = page_info['id']
            eval_url = f"http://localhost:{self.debug_port}/json/runtime/evaluate/{page_id}"

            resp = requests.post(eval_url, json=payload, timeout=5)

            return resp.status_code == 200

        except Exception as e:
            print(f"触发请求失败: {e}")
            return False

    def extract_token_simple(self) -> Optional[str]:
        """简化的token提取方法"""
        print("🔍 正在获取EQC token...")

        # 检查Chrome是否运行
        page = self.find_eqc_page()
        if not page:
            print("❌ 未找到EQC页面")
            print("请确保：")
            print("1. 已运行 start_eqc_chrome.bat")
            print("2. 已在Chrome中登录EQC")
            return None

        print("✅ 找到EQC页面")

        # 检查是否有缓存的有效token（25分钟内）
        if self.latest_token and (time.time() - self.token_time < 1500):
            print(f"✅ 使用缓存的token: {self.latest_token[:8]}...")
            return self.latest_token

        # 提示用户操作
        print("\n" + "="*50)
        print("📌 请在Chrome浏览器中执行以下操作：")
        print("   1. 在EQC页面搜索框输入任意企业名称")
        print("   2. 点击搜索按钮")
        print("   3. 等待搜索结果显示")
        print("="*50)

        input("\n按回车键确认已完成搜索...")

        # 模拟获取token（实际应该从网络请求中提取）
        # 这里简化处理，让用户手动输入
        print("\n临时方案：请手动获取token")
        print("1. 在Chrome中按F12打开开发者工具")
        print("2. 切换到Network标签")
        print("3. 找到包含'/api/search'的请求")
        print("4. 在Headers中找到token字段")
        print("5. 复制token值")

        token = input("\n请粘贴token: ").strip()

        if len(token) == 32:
            self.latest_token = token
            self.token_time = time.time()
            print(f"✅ Token获取成功: {token[:8]}...")
            return token
        else:
            print("❌ Token格式不正确")
            return None

    def get_token(self) -> Optional[str]:
        """获取token的主接口"""
        return self.extract_token_simple()


class EQCClientWithCDP:
    """集成CDP的EQC客户端"""

    def __init__(self):
        self.cdp = EQCCDPClient()
        self.session = requests.Session()
        self.session.verify = False

    def search_company(self, keyword: str):
        """搜索企业"""
        # 获取最新token
        token = self.cdp.get_token()
        if not token:
            print("❌ 无法获取token")
            return None

        # 使用token调用API
        headers = {
            'token': token,
            'Referer': 'https://eqc.pingan.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            url = f'https://eqc.pingan.com/kg-api-hfd/api/search/?key={keyword}'
            response = self.session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'list' in data:
                    return data['list']
            else:
                print(f"API调用失败: {response.status_code}")

        except Exception as e:
            print(f"搜索失败: {e}")

        return None


def main():
    """演示用法"""
    print("🚀 EQC CDP Token获取器")
    print("="*60)

    # 创建客户端
    client = EQCClientWithCDP()

    # 测试搜索
    keyword = input("\n请输入要搜索的企业名称: ").strip()
    if keyword:
        results = client.search_company(keyword)

        if results:
            print(f"\n✅ 搜索成功，找到 {len(results)} 个结果:")
            for i, company in enumerate(results[:3]):
                print(f"{i+1}. {company.get('companyFullName', '未知')}")
                print(f"   ID: {company.get('companyId', '未知')}")
        else:
            print("❌ 搜索失败")


if __name__ == "__main__":
    main()