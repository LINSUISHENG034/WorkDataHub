"""EQC authentication (minimal) via Playwright interactive login.

KISS/YAGNI: expose a single async function to capture the token from
intercepted requests after the user logs into EQC and performs a search.
"""

import asyncio
import logging
from typing import Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

# Configuration constants - make these configurable for easy maintenance
LOGIN_URL = "https://eqc.pingan.com/"
TARGET_API_PATH = "/kg-api-hfd/api/search/"
DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes

logger = logging.getLogger(__name__)


async def get_auth_token_interactively(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[str]:
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
    logger.info("Starting interactive EQC authentication...")
    logger.info(f"Timeout set to {timeout_seconds} seconds")

    try:
        async with async_playwright() as playwright:
            # Launch headed browser for user interaction
            logger.debug("Launching Chromium browser in headed mode")
            browser = await playwright.chromium.launch(headless=False)

            try:
                context = await browser.new_context()
                page = await context.new_page()

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
