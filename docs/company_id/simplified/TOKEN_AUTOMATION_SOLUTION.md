# EQC Token自动化获取方案

## 🎯 问题分析

**现状痛点**：
- 需要手动登录网站 → F12 → Network → 找到token
- 操作复杂，技术门槛高
- Token过期后需要重复操作
- 影响项目可用性和用户体验

## 💡 解决方案（三层递进）

### Layer 1: 智能Token管理器（立即实施）

```python
import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional
import requests
from cryptography.fernet import Fernet

class EQCTokenManager:
    """智能Token管理器，自动处理token生命周期"""

    def __init__(self, token_file: str = ".eqc_token.enc"):
        self.token_file = token_file
        self.encryption_key = self._get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        self._token_cache = None
        self._last_check = None

    def _get_or_create_key(self) -> bytes:
        """获取或创建加密密钥"""
        key_file = ".eqc_key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            # 设置文件权限为仅用户可读
            os.chmod(key_file, 0o600)
            return key

    def save_token(self, token: str, username: str = None):
        """加密保存token"""
        data = {
            "token": token,
            "username": username,
            "saved_at": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat()
        }
        encrypted = self.cipher.encrypt(json.dumps(data).encode())
        with open(self.token_file, "wb") as f:
            f.write(encrypted)
        os.chmod(self.token_file, 0o600)
        print(f"✅ Token已安全保存")

    def get_token(self) -> Optional[str]:
        """获取token，自动检查有效性"""
        if not os.path.exists(self.token_file):
            return None

        # 使用缓存减少文件IO
        if self._token_cache and self._last_check:
            if datetime.now() - self._last_check < timedelta(minutes=5):
                return self._token_cache

        try:
            with open(self.token_file, "rb") as f:
                encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            data = json.loads(decrypted)

            token = data["token"]

            # 检查token年龄
            saved_at = datetime.fromisoformat(data["saved_at"])
            age_days = (datetime.now() - saved_at).days

            if age_days > 7:
                print(f"⚠️ Token已保存{age_days}天，建议更新")

            # 验证token有效性
            if self._validate_token(token):
                self._token_cache = token
                self._last_check = datetime.now()
                return token
            else:
                print("❌ Token已失效，请更新")
                return None

        except Exception as e:
            print(f"❌ 读取token失败: {e}")
            return None

    def _validate_token(self, token: str) -> bool:
        """验证token是否有效"""
        try:
            headers = {"token": token, "Referer": "https://eqc.pingan.com/"}
            response = requests.get(
                "https://eqc.pingan.com/kg-api-hfd/api/search/?key=测试",
                headers=headers,
                timeout=5,
                verify=False
            )
            return response.status_code == 200
        except:
            return False

    def interactive_update(self):
        """交互式更新token"""
        print("\n🔐 EQC Token更新向导")
        print("-" * 50)
        print("请选择更新方式：")
        print("1. 手动输入token")
        print("2. 自动登录获取（需要用户名密码）")
        print("3. 从剪贴板粘贴")

        choice = input("\n请选择 (1-3): ").strip()

        if choice == "1":
            token = input("请输入token: ").strip()
            if token and self._validate_token(token):
                self.save_token(token)
                print("✅ Token更新成功！")
            else:
                print("❌ Token无效")

        elif choice == "2":
            print("\n需要实现自动登录...")
            # 这里调用自动登录方法

        elif choice == "3":
            try:
                import pyperclip
                token = pyperclip.paste().strip()
                if token and self._validate_token(token):
                    self.save_token(token)
                    print("✅ Token更新成功！")
                else:
                    print("❌ 剪贴板中的token无效")
            except ImportError:
                print("❌ 需要安装pyperclip: pip install pyperclip")
```

### Layer 2: 自动登录获取Token（本周实施）

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

class EQCAutoLogin:
    """自动登录EQC获取token"""

    def __init__(self, headless: bool = True):
        self.headless = headless

    def login_and_get_token(self, username: str, password: str) -> Optional[str]:
        """自动登录并获取token"""

        # 配置Chrome选项
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(options=options)

        try:
            # 1. 访问登录页
            print("🌐 访问EQC登录页...")
            driver.get("https://eqc.pingan.com/")

            # 2. 等待登录表单加载
            wait = WebDriverWait(driver, 10)

            # 3. 输入用户名密码
            print("🔑 输入登录凭据...")
            username_input = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_input = driver.find_element(By.ID, "password")

            username_input.send_keys(username)
            password_input.send_keys(password)

            # 4. 点击登录
            login_button = driver.find_element(By.CLASS_NAME, "login-btn")
            login_button.click()

            # 5. 等待登录成功
            time.sleep(3)

            # 6. 执行搜索触发API请求
            print("🔍 执行搜索以触发API请求...")
            search_input = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "search-input"))
            )
            search_input.send_keys("中国平安")
            search_input.submit()

            time.sleep(2)

            # 7. 从浏览器日志中提取token
            print("📝 提取token...")
            token = self._extract_token_from_network(driver)

            if token:
                print(f"✅ 成功获取token: {token[:20]}...")
                return token
            else:
                print("❌ 未能提取到token")
                return None

        except Exception as e:
            print(f"❌ 自动登录失败: {e}")
            return None

        finally:
            driver.quit()

    def _extract_token_from_network(self, driver) -> Optional[str]:
        """从网络请求中提取token"""
        # 方法1：通过JavaScript获取
        script = """
        return performance.getEntriesByType('resource')
            .filter(e => e.name.includes('/api/search'))
            .map(e => e.name);
        """
        urls = driver.execute_script(script)

        # 从URL中解析token（如果在URL中）
        for url in urls:
            if 'token=' in url:
                token = url.split('token=')[1].split('&')[0]
                return token

        # 方法2：通过浏览器存储获取
        script = """
        return localStorage.getItem('eqc_token') ||
               sessionStorage.getItem('eqc_token');
        """
        token = driver.execute_script(script)
        if token:
            return token

        # 方法3：拦截网络请求（需要使用selenium-wire）
        # 这里需要更复杂的实现

        return None
```

### Layer 3: Token服务化（长期方案）

```python
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import threading
import time

class TokenService:
    """Token集中管理服务"""

    def __init__(self):
        self.app = Flask(__name__)
        self.token_manager = EQCTokenManager()
        self.auto_login = EQCAutoLogin()
        self.current_token = None
        self.token_expires_at = None
        self.setup_routes()
        self.start_refresh_thread()

    def setup_routes(self):
        """设置API路由"""

        @self.app.route('/token', methods=['GET'])
        def get_token():
            """获取当前有效token"""
            if self.current_token and self.token_expires_at > datetime.now():
                return jsonify({
                    "token": self.current_token,
                    "expires_in": (self.token_expires_at - datetime.now()).seconds
                })
            else:
                return jsonify({"error": "Token expired or not available"}), 503

        @self.app.route('/token/refresh', methods=['POST'])
        def refresh_token():
            """手动刷新token"""
            auth = request.authorization
            if auth:
                token = self.auto_login.login_and_get_token(
                    auth.username,
                    auth.password
                )
                if token:
                    self.current_token = token
                    self.token_expires_at = datetime.now() + timedelta(hours=24)
                    self.token_manager.save_token(token, auth.username)
                    return jsonify({"message": "Token refreshed successfully"})
            return jsonify({"error": "Refresh failed"}), 500

        @self.app.route('/health', methods=['GET'])
        def health():
            """健康检查"""
            return jsonify({
                "status": "healthy",
                "token_valid": bool(self.current_token),
                "expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None
            })

    def start_refresh_thread(self):
        """启动自动刷新线程"""
        def refresh_loop():
            while True:
                # 每小时检查一次token
                time.sleep(3600)
                if self.token_expires_at and \
                   self.token_expires_at - datetime.now() < timedelta(hours=2):
                    print("🔄 Token即将过期，尝试自动刷新...")
                    # 这里需要存储的凭据来自动刷新

        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()

    def run(self, host='0.0.0.0', port=5000):
        """运行服务"""
        self.app.run(host=host, port=port)
```

## 🚀 实施路径

### Phase 1: 立即实施（今天）
1. 部署`EQCTokenManager`类
2. 将当前有效token加密存储
3. 修改EQCClient使用TokenManager

### Phase 2: 本周内
1. 实现`EQCAutoLogin`自动登录
2. 处理可能的验证码（OCR或手动输入）
3. 建立定期更新机制

### Phase 3: 按需实施
1. 部署Token服务
2. 多用户token管理
3. Token使用统计和监控

## 🔐 安全考虑

1. **加密存储**：所有token和凭据必须加密
2. **权限控制**：文件权限600，仅用户可读
3. **环境隔离**：生产/测试环境分离
4. **审计日志**：记录token获取和使用
5. **定期轮换**：强制定期更新token

## 📊 效果对比

| 方案 | 用户操作 | 技术门槛 | 自动化程度 |
|------|---------|---------|------------|
| 原始方案 | 登录→F12→找token | 高 | 0% |
| Token管理器 | 首次输入，后续自动 | 中 | 70% |
| 自动登录 | 输入用户名密码 | 低 | 90% |
| Token服务 | 无需操作 | 无 | 100% |

## 🎯 推荐方案

**立即实施Token管理器 + 本周实施自动登录**

这样可以：
- 立即改善用户体验
- 逐步提高自动化程度
- 保持实施风险可控
- 为长期方案打基础