"""EQC authentication (minimal) via Playwright interactive login.

KISS/YAGNI: expose a single async function to capture the token from
intercepted requests after the user logs into EQC and performs a search.

Story 6.6: Added token auto-save functionality to .env file.
Story 6.6: Migrated from auth/ to io/auth/ for Clean Architecture compliance.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import Route, ViewportSize, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
from pydantic import ValidationError

from work_data_hub.io.auth.models import AuthTimeoutError, AuthTokenResult, BrowserError

# Configuration constants - make these configurable for easy maintenance
LOGIN_URL = "https://eqc.pingan.com/"
TARGET_API_PATH = "/kg-api-hfd/api/search/"
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_ENV_FILE = ".wdh_env"
EQC_TOKEN_KEY = "WDH_EQC_TOKEN"

logger = logging.getLogger(__name__)


def _update_env_file(env_file: str, key: str, value: str) -> bool:
    """
    Update a key in .env file, preserving comments and format.

    If the key exists, updates its value. If not, appends to end of file.

    Args:
        env_file: Path to .env file
        key: Environment variable key to update
        value: New value for the key

    Returns:
        True if update succeeded, False otherwise
    """
    env_path = Path(env_file)

    try:
        # Read existing content or start fresh
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
        else:
            lines = []

        # Pattern to match the key (handles KEY=value and KEY="value")
        pattern = re.compile(rf"^{re.escape(key)}\s*=")

        # Track if we found and updated the key
        key_found = False
        new_lines = []

        for line in lines:
            if pattern.match(line.strip()):
                # Replace the line with new value
                new_lines.append(f"{key}={value}\n")
                key_found = True
            else:
                new_lines.append(line)

        # If key not found, append to end
        if not key_found:
            # Ensure file ends with newline before appending
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"{key}={value}\n")

        # Write back to file
        env_path.write_text("".join(new_lines), encoding="utf-8")

        logger.info(
            "Updated .env file",
            extra={"key": key, "env_file": str(env_path), "action": "updated" if key_found else "appended"},
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to update .env file",
            extra={"key": key, "env_file": str(env_path), "error": str(e)},
        )
        return False


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
    logger.info(
        "Starting interactive EQC authentication with enhanced stealth options..."
    )
    logger.info(f"Timeout set to {timeout_seconds} seconds")

    try:
        async with async_playwright() as playwright:
            browser = None
            try:
                # Launch headed browser for user interaction
                logger.debug("Launching Chromium browser in headed mode")
                browser = await playwright.chromium.launch(headless=False)

                # --- START: 浏览器伪装配置 ---

                # 1. 设置一个真实的User-Agent
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/116.0.0.0 Safari/537.36"
                )

                # 2. 设置常规的视口大小
                viewport_size: ViewportSize = {"width": 1920, "height": 1080}

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

                async def intercept_request(route: Route) -> None:
                    """Intercept and check requests for authentication token."""
                    try:
                        request = route.request

                        # Check for specific API endpoint
                        if TARGET_API_PATH in request.url:
                            logger.debug(
                                "Intercepted target API request: %s", request.url
                            )

                            # Token is in 'token' header, not Authorization
                            token = request.headers.get("token")
                            if token and not token_future.done():
                                logger.info(
                                    "Successfully captured authentication token"
                                )
                                logger.debug("Captured token prefix: %s", token[:8])
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
                    "Browser opened - please complete login manually "
                    "and perform a search to capture token"
                )

                try:
                    # Wait for token with timeout
                    token = await asyncio.wait_for(
                        token_future, timeout=timeout_seconds
                    )
                    logger.info("Authentication completed successfully")
                    return token

                except asyncio.TimeoutError as exc:
                    logger.error(
                        "Authentication timed out after %s seconds", timeout_seconds
                    )
                    raise AuthTimeoutError(
                        f"Authentication timed out after {timeout_seconds} seconds. "
                        "Please ensure you complete login and perform a search "
                        "within the time limit."
                    ) from exc

            except AuthTimeoutError:
                raise
            except PlaywrightTimeoutError as exc:
                logger.error("Playwright timeout error: %s", exc)
                raise BrowserError("Playwright timed out during EQC login") from exc

            except Exception as exc:
                logger.error("Browser operation error: %s", exc)
                raise BrowserError("Browser operation failed") from exc

            finally:
                # Always cleanup browser resources
                if browser:
                    logger.debug("Closing browser")
                    try:
                        await browser.close()
                    except Exception as exc:
                        logger.warning("Error closing browser: %s", exc)

    except BrowserError:
        raise
    except AuthTimeoutError:
        raise
    except Exception as exc:
        logger.error("Unexpected authentication error: %s", exc)
        raise BrowserError("Unexpected authentication error") from exc


def run_get_token(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    save_to_env: bool = False,
    env_file: str = DEFAULT_ENV_FILE,
) -> Optional[str]:
    """
    Synchronous wrapper for async authentication with optional .env save.

    This function provides a synchronous interface to the async authentication
    process for compatibility with sync code. Optionally saves the captured
    token to a .env file for persistence.

    Args:
        timeout_seconds: Maximum time to wait for authentication
        save_to_env: If True, save captured token to .env file
        env_file: Path to .env file (default: ".env")

    Returns:
        Captured authentication token string, or None if authentication failed

    Example:
        >>> # Capture token only
        >>> token = run_get_token(timeout_seconds=180)

        >>> # Capture and save to .env
        >>> token = run_get_token(timeout_seconds=180, save_to_env=True)

        >>> # Capture and save to custom .env file
        >>> token = run_get_token(save_to_env=True, env_file=".env.local")
    """
    try:
        token = asyncio.run(get_auth_token_interactively(timeout_seconds))

        if token and save_to_env:
            success = _update_env_file(env_file, EQC_TOKEN_KEY, token)
            if success:
                print(f"✅ Token 已自动保存到 {env_file}")
            else:
                print(f"⚠️ Token 保存失败，请手动更新 {env_file}")
                print(f"   {EQC_TOKEN_KEY}={token}")

        return token
    except Exception as exc:
        logger.error("Synchronous authentication wrapper failed: %s", exc)
        return None


async def get_auth_token_with_validation(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[AuthTokenResult]:
    """
    Capture an authentication token and validate it via AuthTokenResult.

    Returns None if no token is captured or validation fails.
    """
    token = await get_auth_token_interactively(timeout_seconds=timeout_seconds)
    if not token:
        return None
    try:
        return AuthTokenResult(token=token, source_url=LOGIN_URL)
    except ValidationError as exc:
        logger.error("Captured token failed validation: %s", exc)
        return None


def run_get_token_with_validation(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[AuthTokenResult]:
    """Synchronous wrapper for get_auth_token_with_validation."""
    try:
        return asyncio.run(
            get_auth_token_with_validation(timeout_seconds=timeout_seconds)
        )
    except Exception as exc:
        logger.error("Synchronous validation wrapper failed to capture token: %s", exc)
        return None
