#!/usr/bin/env python3
"""
EQC Token实时提取器（最简实用版）
保持浏览器登录状态，自动提供token给Python程序
"""

import os
import json
import time
import threading
from typing import Optional
from datetime import datetime, timedelta

class TokenProvider:
    """Token提供器 - 最简单的实现"""

    def __init__(self):
        self.token_file = os.path.join(os.path.expanduser("~"), ".eqc_current_token.txt")
        self.last_token = None
        self.last_update = None

    def save_token(self, token: str):
        """保存token到文件"""
        with open(self.token_file, 'w') as f:
            f.write(f"{token}\n{time.time()}")
        self.last_token = token
        self.last_update = datetime.now()

    def get_token(self) -> Optional[str]:
        """获取token"""
        # 读取文件中的token
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        token = lines[0].strip()
                        if len(lines) > 1:
                            timestamp = float(lines[1].strip())
                            # 检查是否在25分钟内
                            if time.time() - timestamp < 1500:
                                return token
            except:
                pass

        # 如果没有有效token，提示用户操作
        print("\n" + "="*60)
        print("⚠️ 需要更新Token")
        print("="*60)
        print("\n请按以下步骤操作：")
        print("\n1. 确保Chrome浏览器已登录EQC")
        print("2. 在EQC页面执行一次搜索")
        print("3. 按F12打开开发者工具")
        print("4. 在Network标签找到api/search请求")
        print("5. 复制Headers中的token值")
        print("\n" + "-"*60)

        token = input("请粘贴token（32位字符）: ").strip()

        if len(token) == 32:
            self.save_token(token)
            print(f"✅ Token已更新: {token[:8]}...")
            return token
        else:
            print("❌ Token格式错误")
            return None


class SimpleEQCClient:
    """简化的EQC客户端"""

    def __init__(self):
        self.token_provider = TokenProvider()

    def ensure_token(self) -> Optional[str]:
        """确保有可用的token"""
        return self.token_provider.get_token()

    def search(self, company_name: str) -> list:
        """搜索企业"""
        token = self.ensure_token()
        if not token:
            return []

        import requests
        import urllib3
        urllib3.disable_warnings()

        headers = {
            'token': token,
            'Referer': 'https://eqc.pingan.com/',
            'User-Agent': 'Mozilla/5.0'
        }

        try:
            from urllib.parse import quote
            url = f'https://eqc.pingan.com/kg-api-hfd/api/search/?key={quote(company_name)}'

            response = requests.get(url, headers=headers, verify=False, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'list' in data:
                    return data['list']
                else:
                    print(f"⚠️ 未找到结果")
            elif response.status_code == 403:
                print("❌ Token已过期，需要更新")
                # 清除过期token
                if os.path.exists(self.token_provider.token_file):
                    os.remove(self.token_provider.token_file)
                # 递归调用，重新获取token
                return self.search(company_name)
            else:
                print(f"❌ API错误: {response.status_code}")

        except Exception as e:
            print(f"❌ 请求失败: {e}")

        return []


def create_browser_helper():
    """创建浏览器辅助脚本"""
    helper_js = """
// EQC Token Helper - 在浏览器Console中运行
(function() {
    console.log('🚀 EQC Token监控已启动');

    // 拦截所有XHR请求
    const originalXHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function() {
        const xhr = new originalXHR();
        const originalOpen = xhr.open;
        const originalSetRequestHeader = xhr.setRequestHeader;

        let headers = {};

        xhr.setRequestHeader = function(header, value) {
            headers[header] = value;
            if (header.toLowerCase() === 'token') {
                console.log('✅ 捕获到Token:', value);
                // 复制到剪贴板
                navigator.clipboard.writeText(value).then(() => {
                    console.log('📋 Token已复制到剪贴板');
                    alert('Token已复制到剪贴板，请粘贴到Python程序中');
                });
            }
            return originalSetRequestHeader.apply(this, arguments);
        };

        return xhr;
    };

    // 拦截fetch请求
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        if (options && options.headers && options.headers.token) {
            console.log('✅ 捕获到Token:', options.headers.token);
            navigator.clipboard.writeText(options.headers.token);
        }
        return originalFetch.apply(this, arguments);
    };

    console.log('💡 提示：执行一次搜索即可自动复制token');
})();
"""

    print("\n" + "="*60)
    print("🌐 浏览器辅助脚本")
    print("="*60)
    print("\n将以下JavaScript代码复制到浏览器Console中运行：")
    print("\n" + "-"*60)
    print(helper_js)
    print("-"*60)
    print("\n运行后，执行一次搜索就会自动复制token到剪贴板")


def main():
    """主程序"""
    print("🚀 EQC Token实用工具")
    print("="*60)

    print("\n请选择模式：")
    print("1. 测试企业搜索")
    print("2. 生成浏览器辅助脚本")
    print("3. 清除过期token")

    choice = input("\n请选择 (1-3): ").strip()

    if choice == "1":
        client = SimpleEQCClient()
        company = input("请输入企业名称: ").strip()
        if company:
            results = client.search(company)
            if results:
                print(f"\n找到 {len(results)} 个结果：")
                for i, r in enumerate(results[:5]):
                    print(f"{i+1}. {r.get('companyFullName', '未知')}")
            else:
                print("未找到结果")

    elif choice == "2":
        create_browser_helper()

    elif choice == "3":
        token_file = os.path.join(os.path.expanduser("~"), ".eqc_current_token.txt")
        if os.path.exists(token_file):
            os.remove(token_file)
            print("✅ 已清除过期token")
        else:
            print("没有保存的token")


if __name__ == "__main__":
    main()