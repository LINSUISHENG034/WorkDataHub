"""EQC authentication (minimal) via Playwright interactive login.

KISS/YAGNI: expose a single async function to capture the token from
intercepted requests after the user logs into EQC and performs a search.
"""

import asyncio
import logging
from typing import Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Configuration constants - make these configurable for easy maintenance
LOGIN_URL = "https://eqc.pingan.com/#/login?redirect=%2Fhome"
TARGET_API_PATH = "/kg-api-hfd/api/search/"
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes

logger = logging.getLogger(__name__)


class AuthTimeoutError(Exception):
    """Custom exception for authentication timeouts."""

    pass


async def get_auth_token_interactively(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """
    Launch browser, allow user login, capture authentication token.

    This function launches a headed browser window that navigates to the EQC platform
    login page. The user can complete login manually (including 2FA, captchas, etc.).
    The function intercepts network requests to automatically capture the authentication
    token when the user performs any search action on the platform.

    Args:
        timeout_seconds: Maximum time to wait for authentication (default: 300 seconds)

    Returns:
        Captured authentication token string, or None if authentication failed

    Example:
        >>> token = await get_auth_token_interactively(timeout_seconds=180)
        >>> if token:
        ...     print(f"Got token: {token[:8]}...")
        ... else:
        ...     print("Authentication failed")
    """
    logger.info("Starting interactive EQC authentication with enhanced stealth options...")
    logger.info(f"Timeout set to {timeout_seconds} seconds")

    try:
        async with async_playwright() as playwright:
            # Launch headed browser for user interaction
            logger.debug("Launching Chromium browser in headed mode")
            browser = await playwright.chromium.launch(headless=False)

            try:
                # --- START: 浏览器伪装配置 ---

                # 1. 设置一个真实的User-Agent
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

                # 2. 设置常规的视口大小
                viewport_size = {"width": 1920, "height": 1080}

                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport=viewport_size,
                    # 可以考虑同时设置屏幕大小和色彩深度
                    screen=viewport_size,
                    color_scheme="light",
                    java_script_enabled=True,
                )

                page = await context.new_page()

                # --- 核心改动 ---
                # 2. 在所有操作之前，应用stealth补丁
                # 这会自动处理几十个浏览器指纹问题
                stealth = Stealth()
                await stealth.apply_stealth_async(page)
                # -----------------

                # 3. 注入JS脚本，隐藏自动化特征 (关键步骤)
                # 这段脚本会在页面加载任何其他脚本之前执行
                js_stealth = """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                """
                await page.add_init_script(js_stealth)

                # --- END: 浏览器伪装配置 ---

                # Use Future for cross-coroutine communication
                token_future: asyncio.Future[str] = asyncio.Future()

                async def intercept_request(route):
                    """Intercept and check requests for authentication token."""
                    try:
                        request = route.request

                        # Check for specific API endpoint
                        if TARGET_API_PATH in request.url:
                            logger.debug(f"Intercepted target API request: {request.url}")

                            # Token is in 'token' header, not Authorization
                            token = request.headers.get("token")
                            if token and not token_future.done():
                                logger.info("Successfully captured authentication token")
                                logger.debug(f"Captured token prefix: {token[:8]}...")
                                token_future.set_result(token)

                        # Must continue all requests or page will hang
                        await route.continue_()

                    except Exception as e:
                        logger.error(f"Error in request interception: {e}")
                        # Still continue the request to prevent hanging
                        try:
                            await route.continue_()
                        except Exception:
                            pass  # Route may already be handled

                # Intercept all network requests
                await context.route("**/*", intercept_request)

                # Navigate to login page
                logger.info("Navigating to EQC login page...")
                await page.goto(LOGIN_URL, wait_until="domcontentloaded")
                logger.info(
                    "Browser opened - please complete login manually and perform a search "
                    "to capture token"
                )

                try:
                    # Wait for token with timeout
                    token = await asyncio.wait_for(token_future, timeout=timeout_seconds)
                    logger.info("Authentication completed successfully")
                    return token

                except asyncio.TimeoutError:
                    logger.error(f"Authentication timed out after {timeout_seconds} seconds")
                    raise AuthTimeoutError(
                        f"Authentication timed out after {timeout_seconds} seconds. "
                        "Please ensure you complete login and perform a search "
                        "within the time limit."
                    )

            except PlaywrightTimeoutError as e:
                logger.error(f"Playwright timeout error: {e}")
                return None

            except Exception as e:
                logger.error(f"Browser operation error: {e}")
                return None

            finally:
                # Always cleanup browser resources
                logger.debug("Closing browser")
                try:
                    await browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")

    except Exception as e:
        logger.error(f"Unexpected authentication error: {e}")
        return None


def run_get_token(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[str]:
    """
    Synchronous wrapper for async authentication.

    This function provides a synchronous interface to the async authentication
    process for compatibility with sync code.

    Args:
        timeout_seconds: Maximum time to wait for authentication

    Returns:
        Captured authentication token string, or None if authentication failed

    Example:
        >>> token = run_get_token(timeout_seconds=180)
        >>> if token:
        ...     print(f"Got token: {token}")
        ... else:
        ...     print("Authentication failed")
    """
    try:
        return asyncio.run(get_auth_token_interactively(timeout_seconds))
    except Exception as e:
        logger.error(f"Synchronous authentication wrapper failed: {e}")
        return None
