# EQC Token获取难度降低方案（实用版）

## 问题本质
- Token 30分钟过期（无法长期存储）
- 需要手机验证码（无法自动化）
- 需要滑动验证（难以自动化）
- **核心需求**：用户登录一次后，能持续工作

## 🎯 方案一：Chrome DevTools Protocol（推荐）

### 原理
用户正常登录EQC后，Python程序通过CDP连接到Chrome，实时获取网络请求中的token。

### 实现步骤

#### 1. 启动Chrome开启调试端口
```batch
# Windows批处理文件：start_eqc_chrome.bat
@echo off
echo 启动EQC专用Chrome浏览器...
start chrome --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome_eqc" https://eqc.pingan.com/
echo.
echo 请在浏览器中：
echo 1. 登录EQC平台
echo 2. 保持浏览器开启
echo 3. 程序会自动获取token
pause
```

#### 2. Python实时获取Token
```python
# tools/eqc_token_extractor.py
import json
import time
from typing import Optional
import websocket
import requests

class ChromeTokenExtractor:
    """通过Chrome DevTools Protocol实时获取token"""

    def __init__(self, debug_port=9222):
        self.debug_port = debug_port
        self.ws = None
        self.latest_token = None
        self.token_timestamp = 0

    def connect(self) -> bool:
        """连接到Chrome调试端口"""
        try:
            # 获取WebSocket端点
            resp = requests.get(f"http://localhost:{self.debug_port}/json")
            endpoints = resp.json()

            if not endpoints:
                print("❌ 未找到Chrome标签页，请确保Chrome已启动并登录EQC")
                return False

            # 找到EQC标签页
            eqc_page = None
            for page in endpoints:
                if 'eqc.pingan.com' in page.get('url', ''):
                    eqc_page = page
                    break

            if not eqc_page:
                print("❌ 未找到EQC页面，请在Chrome中打开EQC")
                return False

            # 连接WebSocket
            self.ws = websocket.create_connection(eqc_page['webSocketDebuggerUrl'])

            # 启用网络监控
            self.ws.send(json.dumps({
                "id": 1,
                "method": "Network.enable"
            }))

            print("✅ 已连接到Chrome，正在监控网络请求...")
            return True

        except Exception as e:
            print(f"❌ 连接Chrome失败: {e}")
            print("请确保已运行 start_eqc_chrome.bat")
            return False

    def extract_token_from_request(self, headers: dict) -> Optional[str]:
        """从请求头中提取token"""
        for key, value in headers.items():
            if key.lower() == 'token':
                return value
        return None

    def monitor_and_extract(self) -> Optional[str]:
        """监控网络请求并提取token"""
        if not self.ws:
            if not self.connect():
                return None

        # 如果有30分钟内的token，直接返回
        if self.latest_token and (time.time() - self.token_timestamp < 1800):
            return self.latest_token

        print("🔍 等待EQC API请求以获取token...")
        print("💡 提示：在浏览器中搜索任意企业名称")

        start_time = time.time()
        timeout = 30  # 等待30秒

        while time.time() - start_time < timeout:
            try:
                message = json.loads(self.ws.recv())

                # 检查是否是网络请求
                if message.get('method') == 'Network.requestWillBeSent':
                    params = message.get('params', {})
                    request = params.get('request', {})
                    url = request.get('url', '')

                    # 检查是否是EQC API请求
                    if '/api/search' in url:
                        headers = request.get('headers', {})
                        token = self.extract_token_from_request(headers)

                        if token:
                            self.latest_token = token
                            self.token_timestamp = time.time()
                            print(f"✅ 成功获取token: {token[:8]}...")
                            return token

            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                print(f"监控出错: {e}")
                break

        print("⏱️ 超时：未检测到包含token的请求")
        print("请在浏览器中执行一次搜索操作")
        return None

    def get_token(self) -> Optional[str]:
        """获取token的主接口"""
        return self.monitor_and_extract()

# 使用示例
def get_eqc_token():
    """获取EQC token的便捷函数"""
    extractor = ChromeTokenExtractor()
    return extractor.get_token()
```

## 🎯 方案二：浏览器扩展（备选）

### Chrome扩展自动提取Token

#### manifest.json
```json
{
  "manifest_version": 3,
  "name": "EQC Token Helper",
  "version": "1.0",
  "description": "自动提取EQC token供本地程序使用",
  "permissions": ["webRequest", "storage"],
  "host_permissions": ["*://eqc.pingan.com/*"],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html"
  }
}
```

#### background.js
```javascript
// 监听EQC API请求
chrome.webRequest.onBeforeSendHeaders.addListener(
  function(details) {
    // 查找token
    let token = null;
    for (let header of details.requestHeaders) {
      if (header.name.toLowerCase() === 'token') {
        token = header.value;
        break;
      }
    }

    if (token) {
      // 保存token到本地存储
      chrome.storage.local.set({
        'eqc_token': token,
        'timestamp': Date.now()
      });

      // 发送到本地服务器（可选）
      fetch('http://localhost:8765/token', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token: token})
      }).catch(() => {
        // 忽略错误（本地服务器可能未运行）
      });
    }
  },
  {urls: ["*://eqc.pingan.com/*/api/*"]},
  ["requestHeaders"]
);
```

## 🎯 方案三：半自动化助手（最简单）

### 一键复制Token工具
```python
# tools/eqc_helper.py
import pyperclip
import keyboard
import time

class EQCHelper:
    """EQC操作助手，简化token获取"""

    def __init__(self):
        self.monitoring = False

    def start_monitoring(self):
        """开始监控剪贴板"""
        print("📋 EQC Token助手已启动")
        print("="*50)
        print("使用方法：")
        print("1. 在Chrome中登录EQC")
        print("2. 按F12打开开发者工具")
        print("3. 执行一次搜索")
        print("4. 在Network中找到API请求")
        print("5. 右键点击token值 -> Copy value")
        print("6. 助手会自动检测并使用token")
        print("="*50)
        print("按 Ctrl+C 退出")

        last_clipboard = ""

        while True:
            try:
                current = pyperclip.paste()

                # 检测是否是token（32位字符）
                if current != last_clipboard and len(current) == 32:
                    if all(c in '0123456789abcdef' for c in current):
                        print(f"\n✅ 检测到token: {current[:8]}...")

                        # 立即使用token
                        self.use_token(current)

                        last_clipboard = current

                time.sleep(0.5)

            except KeyboardInterrupt:
                print("\n👋 助手已停止")
                break

    def use_token(self, token):
        """使用获取到的token"""
        print("🚀 正在使用token执行任务...")

        # 这里调用实际的业务逻辑
        # 例如：执行company_id查询

        print("✅ 任务完成")
```

## 📊 方案对比

| 方案 | 技术难度 | 用户操作 | 稳定性 | 推荐度 |
|------|---------|---------|--------|--------|
| CDP方案 | 中 | 运行bat启动Chrome | 高 | ⭐⭐⭐⭐⭐ |
| 浏览器扩展 | 高 | 安装扩展 | 高 | ⭐⭐⭐⭐ |
| 剪贴板监控 | 低 | 手动复制token | 中 | ⭐⭐⭐ |

## 🚀 推荐实施方案

### 立即实施：CDP方案
1. 创建`start_eqc_chrome.bat`启动脚本
2. 实现`ChromeTokenExtractor`类
3. 集成到EQC客户端中

### 优势
- ✅ 用户只需登录一次
- ✅ 自动获取token，无需F12
- ✅ 保持登录状态可持续工作
- ✅ 实现相对简单

### 使用流程
1. 运行`start_eqc_chrome.bat`
2. 在浏览器中登录（手机验证码+滑动验证）
3. Python程序自动获取token
4. 每次需要时自动更新token

## 💡 终极建议

考虑到各种限制，**最实用的方案是CDP**：
- 用户体验好（登录一次即可）
- 技术实现可行
- 不需要额外安装软件

如果CDP有困难，退而求其次：
- 提供清晰的操作指南
- 配合剪贴板工具
- 尽量减少手动步骤