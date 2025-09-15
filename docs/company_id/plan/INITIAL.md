# `INITIAL.md`: 自动化 EQC 平台认证 Token 获取

## 1\. 任务目标 (Task Goal)

优化 `eqc_crawler.py` 脚本，实现认证 Token 的自动化获取。通过集成浏览器自动化库，引导用户在程序启动的浏览器窗口中完成登录操作，并由程序自动捕获和使用登录后生成的 Token，彻底取代当前需要手动从开发者工具中复制粘贴Token的繁琐流程。

## 2\. 背景与上下文 (Background & Context)

当前 `eqc_crawler.py` 脚本在初始化 `EqcCrawler` 类时，需要一个外部传入的 `token` 参数。该 `token` 目前只能通过用户登录 `https://eqc.pingan.com/` 后，手动打开浏览器开发者工具（F12），在网络请求中找到并复制，操作流程复杂、对非技术用户不友好，且Token会过期，导致可用性极差。

用户的核心诉求是简化这一流程，实现“程序内登录，自动获取”。

## 3\. 核心需求 (Core Requirements)

1.  **引入浏览器自动化库**：为项目添加一个新的依赖库，如 `Playwright`，用于驱动浏览器执行自动化操作。
2.  **创建独立的认证模块**：新增一个Python模块，例如 `src/auth/eqc_auth_handler.py`，专门负责处理Token的获取逻辑，以遵循单一职责原则。
3.  **实现交互式登录流程**：
      * 在该模块中创建一个函数，例如 `get_auth_token_interactively()`。
      * 此函数启动一个\*\*有头模式（headed）\*\*的浏览器实例，并导航到E企查的登录页面。
      * 程序需明确提示用户：“浏览器已打开，请在窗口中完成登录操作。成功登录后，程序将自动捕获凭证并关闭浏览器。”
4.  **自动捕获Token**：
      * 在用户登录期间，程序需要监听浏览器发出的所有网络请求。
      * 识别并拦截包含了 `token` 请求头的特定API调用（例如，对 `https://eqc.pingan.com/kg-api-hfd/api/search/` 的请求）。
      * 从请求头中成功提取 `token` 字符串。
5.  **健壮的流程控制**：
      * 一旦成功捕获到Token，应立即关闭浏览器窗口，并将Token返回。
      * 设置一个合理的超时机制（例如，300秒）。如果用户在超时时间内未能完成登录，函数应优雅地中止，并返回 `None`，同时打印提示信息。
      * 如果用户在登录前手动关闭了浏览器窗口，程序也应能正确处理此异常并退出。
6.  **集成到主流程**：
      * 修改当前脚本的主执行逻辑。在实例化 `EqcCrawler` 之前，首先调用 `get_auth_token_interactively()` 函数获取Token。
      * 如果成功获取到Token，则用它来初始化`EqcCrawler`并继续执行后续的爬虫任务。
      * 如果未能获取Token（因为超时或用户取消），则程序应终止，并给出明确的退出信息。

## 4\. 技术选型与设计思路 (Technology Stack & Design Approach)

  * **技术选型**:

      * **核心库**: 推荐使用 **Playwright**。它提供了现代化的API和强大的网络请求拦截功能，非常适合此场景。相比Selenium，它的网络控制能力更原生、更强大。
      * **依赖管理**: 使用 `uv` 添加新依赖：`uv add playwright`。同时，需要执行 `uv run playwright install` 来安装浏览器驱动。

  * **设计思路**:

      * **KISS (Keep It Simple, Stupid)**: 我们不尝试用程序自动化输入用户名和密码，因为这会增加处理验证码、多因素认证等问题的复杂性，并且存在安全风险。让用户自己手动登录是最简单、最可靠的方案。程序的核心任务是“观察”和“捕获”。
      * **YAGNI (You Aren't Gonna Need It)**: 我们仅实现捕获Token这一个核心功能，不添加任何不必要的浏览器自动化特性。
      * **关注点分离 (Separation of Concerns)**: 将认证逻辑从爬虫逻辑 (`EqcCrawler`) 中完全分离出来。`EqcCrawler` 的职责是**使用**Token，而不是**获取**Token。这使得代码更模块化，易于测试和维护。

## 5\. 实现蓝图 (Implementation Blueprint)

### 步骤 1: 添加新依赖

```bash
# 添加Playwright库
uv add playwright

# 安装浏览器驱动
uv run playwright install
```

确保将 `playwright` 添加到 `pyproject.toml` 的 `dependencies` 中。

### 步骤 2: 创建认证模块 (`src/auth/eqc_auth_handler.py`)

```python
# src/auth/eqc_auth_handler.py (伪代码/结构示例)

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

LOGIN_URL = "https://eqc.pingan.com/"
# 目标API的URL特征，用于识别哪个请求包含我们需要的token
TARGET_API_PATH = "/kg-api-hfd/api/search/"
TIMEOUT_SECONDS = 300  # 5分钟超时

async def get_auth_token_interactively() -> str | None:
    """
    启动一个浏览器窗口，让用户手动登录E企查平台，
    并自动捕获登录后的认证Token。

    Returns:
        成功捕获的Token字符串，如果超时或失败则返回None。
    """
    print("正在启动浏览器，请在新窗口中完成登录操作...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        token_found = asyncio.Future()

        async def intercept_request(route):
            request = route.request
            if TARGET_API_PATH in request.url:
                token = request.headers.get("token")
                if token and not token_found.done():
                    print("成功捕获到Token！浏览器将自动关闭。")
                    token_found.set_result(token)
            await route.continue_()
        
        await context.route("**/*", intercept_request)

        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            
            # 等待用户登录并触发API调用，或者等待超时
            token = await asyncio.wait_for(token_found, timeout=TIMEOUT_SECONDS)
            return token
        except (PlaywrightTimeoutError, asyncio.TimeoutError):
            print(f"操作超时（{TIMEOUT_SECONDS}秒），未能捕获到Token。")
            return None
        except Exception as e:
            # 处理用户提前关闭浏览器等异常
            print(f"在获取Token时发生错误: {e}")
            return None
        finally:
            await browser.close()

# 异步入口的辅助函数
def run_get_token():
    return asyncio.run(get_auth_token_interactively())

```

### 步骤 3: 修改主执行流程

修改调用 `EqcCrawler` 的地方，例如一个 `main.py` 或脚本的执行入口。

```python
# main.py (或类似的入口文件)

# from crawler.eqc_crawler import EqcCrawler
# from src.auth.eqc_auth_handler import run_get_token

def main():
    # 1. 自动获取Token
    print("开始获取E企查平台认证Token...")
    auth_token = run_get_token()

    if not auth_token:
        print("获取Token失败，程序退出。")
        return

    print("已成功获取Token，开始执行爬虫任务。")
    
    # 2. 使用获取到的Token初始化爬虫
    crawler = EqcCrawler(token=auth_token)
    
    # 3. 执行原有的爬虫逻辑
    key_word = "平安银行" # 示例关键词
    base_info, business_info, biz_label = crawler.scrape_data(key_word)
    
    if base_info:
        print(f"成功抓取到公司 '{base_info.get('company_name')}' 的数据。")
        # ... 后续数据处理 ...
    else:
        print(f"未能抓取到关键词 '{key_word}' 的相关数据。")


if __name__ == "__main__":
    main()
```

## 6\. 验收标准与验证方法 (Acceptance Criteria & Validation)

1.  执行主脚本后，能自动打开一个浏览器窗口并导航至E企查登录页。
2.  命令行显示清晰的提示信息，指导用户进行登录操作。
3.  用户在浏览器中成功输入账号密码（及验证码）并登录后，浏览器窗口应在数秒内自动关闭。
4.  浏览器关闭后，程序能继续执行，并使用捕获到的Token成功发起API请求（日志中应能看到 `Successfully scraped data for ...`）。
5.  如果在指定的超时时间内（例如5分钟）用户未完成登录，程序应能打印超时信息并正常退出。
6.  如果用户在登录前就手动关闭了浏览器窗口，程序也应能捕获到异常并优雅退出，而不是崩溃。
7.  最终实现的功能应完全替代手动查找和配置Token的步骤。

## 7\. 风险与注意事项 (Risks & Considerations)

  * **网站变更风险**: EQC平台可能会更改其API端点URL (`TARGET_API_PATH`) 或存放Token的请求头名称 (`token`)。实现时应将这些关键字符串定义为模块顶部的常量，方便未来修改。
  * **首次运行**: 需要告知用户，首次运行脚本时会下载浏览器内核，可能需要一些时间。`playwright install` 这一步至关重要。
  * **环境兼容性**: Playwright在某些无图形界面的服务器环境（Headless Linux）中运行可能会遇到挑战，但由于本方案要求用户交互，因此主要目标是在桌面环境下运行，此风险较低。