#!/usr/bin/env python3
"""
EQC Token管理器 - 简化版实现
立即可用的token管理方案，降低使用门槛
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import requests
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SimpleEQCTokenManager:
    """简化版Token管理器，易于使用"""

    def __init__(self):
        # Token存储在用户目录下
        self.config_dir = Path.home() / ".workdatahub"
        self.config_dir.mkdir(exist_ok=True)
        self.token_file = self.config_dir / "eqc_token.json"

    def save_token(self, token: str, username: str = None) -> bool:
        """保存token到文件"""
        try:
            data = {
                "token": token,
                "username": username,
                "saved_at": datetime.now().isoformat(),
                "last_validated": datetime.now().isoformat()
            }

            with open(self.token_file, "w") as f:
                json.dump(data, f, indent=2)

            # Windows兼容的文件权限设置
            if os.name != 'nt':
                os.chmod(self.token_file, 0o600)

            print(f"✅ Token已保存到: {self.token_file}")
            return True

        except Exception as e:
            print(f"❌ 保存token失败: {e}")
            return False

    def get_token(self) -> Optional[str]:
        """获取保存的token"""
        if not self.token_file.exists():
            print(f"⚠️ 未找到保存的token，请先运行: python {__file__} --update")
            return None

        try:
            with open(self.token_file, "r") as f:
                data = json.load(f)

            token = data["token"]
            saved_at = datetime.fromisoformat(data["saved_at"])
            age = datetime.now() - saved_at

            # 提示token年龄
            if age.days > 0:
                print(f"ℹ️ Token已保存 {age.days} 天 {age.seconds//3600} 小时")

            if age.days > 7:
                print(f"⚠️ Token可能已过期，建议更新: python {__file__} --update")

            return token

        except Exception as e:
            print(f"❌ 读取token失败: {e}")
            return None

    def validate_token(self, token: str) -> bool:
        """验证token是否有效"""
        try:
            print("🔍 验证token有效性...")
            headers = {
                "token": token,
                "Referer": "https://eqc.pingan.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(
                "https://eqc.pingan.com/kg-api-hfd/api/search/?key=测试",
                headers=headers,
                timeout=10,
                verify=False
            )

            if response.status_code == 200:
                print("✅ Token有效！")
                return True
            else:
                print(f"❌ Token无效 (状态码: {response.status_code})")
                return False

        except Exception as e:
            print(f"❌ 验证失败: {e}")
            return False

    def interactive_update(self):
        """交互式更新token"""
        print("\n" + "="*60)
        print("🔐 EQC Token 更新向导")
        print("="*60)

        print("\n📋 获取Token的步骤：")
        print("1. 打开Chrome浏览器")
        print("2. 访问 https://eqc.pingan.com/")
        print("3. 使用您的账号密码登录")
        print("4. 登录成功后，按F12打开开发者工具")
        print("5. 切换到Network标签页")
        print("6. 在页面搜索框输入'中国平安'并搜索")
        print("7. 在Network中找到包含'/api/search/?key='的请求")
        print("8. 点击该请求，查看Headers标签")
        print("9. 找到Request Headers中的'token'字段")
        print("10. 复制token的值（通常是32位字符）")

        print("\n" + "-"*60)
        print("请粘贴您的token（或输入 'quit' 退出）:")

        token = input("> ").strip()

        if token.lower() == 'quit':
            print("👋 已退出")
            return False

        if len(token) < 20:
            print("❌ Token长度异常，请检查是否完整复制")
            return False

        # 验证token
        if self.validate_token(token):
            # 可选：询问用户名
            print("\n可选：请输入您的用户名（用于标记，直接回车跳过）:")
            username = input("> ").strip() or None

            if self.save_token(token, username):
                print("\n🎉 Token配置成功！")
                print(f"您现在可以正常使用EQC查询功能了")
                return True
        else:
            print("\n❌ Token验证失败，请确认：")
            print("1. Token是否完整复制")
            print("2. 是否已登录EQC平台")
            print("3. Token是否已过期")

        return False

    def check_status(self):
        """检查当前token状态"""
        print("\n" + "="*60)
        print("📊 Token状态检查")
        print("="*60)

        token = self.get_token()
        if token:
            print(f"\n✅ 找到保存的token")
            print(f"Token前缀: {token[:8]}...")

            if self.validate_token(token):
                print(f"\n🎉 Token状态：有效")
                return True
            else:
                print(f"\n❌ Token状态：无效或已过期")
                print(f"请运行 python {__file__} --update 更新token")
        else:
            print(f"\n❌ 未找到token")
            print(f"请运行 python {__file__} --update 设置token")

        return False

    def export_env(self):
        """导出为环境变量格式"""
        token = self.get_token()
        if token:
            print(f"\n# 添加到.env文件:")
            print(f"WDH_EQC_TOKEN={token}")
            print(f"\n# 或设置环境变量:")
            if os.name == 'nt':
                print(f"set WDH_EQC_TOKEN={token}")
            else:
                print(f"export WDH_EQC_TOKEN={token}")
            return True
        return False


def main():
    """主函数"""
    manager = SimpleEQCTokenManager()

    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--update" or command == "-u":
            manager.interactive_update()

        elif command == "--check" or command == "-c":
            manager.check_status()

        elif command == "--export" or command == "-e":
            manager.export_env()

        elif command == "--help" or command == "-h":
            print("EQC Token管理器")
            print("\n用法:")
            print(f"  python {sys.argv[0]} --update   # 更新token")
            print(f"  python {sys.argv[0]} --check    # 检查token状态")
            print(f"  python {sys.argv[0]} --export   # 导出环境变量")
            print(f"  python {sys.argv[0]} --help     # 显示帮助")

        else:
            print(f"❌ 未知命令: {command}")
            print(f"使用 python {sys.argv[0]} --help 查看帮助")

    else:
        # 默认执行状态检查
        if not manager.check_status():
            print(f"\n💡 提示：首次使用请运行 python {sys.argv[0]} --update 设置token")


if __name__ == "__main__":
    main()