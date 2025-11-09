"""EQC authentication with optional OpenCV-based slider solving.

This module keeps the original handler untouched and provides an alternative
flow that can:
- Autofill username/password from environment variables
- Detect and solve Geetest-style slider via OpenCV (with graceful fallback)
- Reuse storage_state to avoid repeated logins
- Capture the EQC token from request headers after normal login (no extra search)

Environment variables:
- EQC_USERNAME: account name to autofill
- EQC_PASSWORD: password to autofill
- EQC_OTP: optional one-time code if present (captcha/token still allowed manual)
- EQC_AUTO_SLIDER: 'true' to enable OpenCV slider attempts (default true)
- EQC_REUSE_SESSION: 'true' to load/save storage_state (default true)
- EQC_STORAGE_STATE: path to persist storage state
  (default .cache/eqc_storage_state.json)

Usage example:
    from src.work_data_hub.auth.eqc_auth_opencv import run_get_token
    token = run_get_token(180)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2  # type: ignore
import numpy as np
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from .eqc_settings import settings

logger = logging.getLogger(__name__)


# Configuration
LOGIN_URL = settings.login_url
DEFAULT_TIMEOUT_SECONDS = 300

EQC_USERNAME = settings.username
EQC_PASSWORD = settings.password
EQC_OTP = settings.otp  # optional 2FA token if enterprise policy allows
EQC_AUTO_SLIDER = settings.auto_slider
EQC_REUSE_SESSION = settings.reuse_session
EQC_CLEAR_SESSION = settings.clear_session
# 强制重置：在本次调用前直接删除 storage_state 文件，避免缓存干扰
EQC_RESET_STORAGE = settings.reset_storage
EQC_STORAGE_STATE = settings.storage_state
EQC_CAPTURE_URL_SUBSTR = settings.capture_url_substr


@dataclass
class SliderImages:
    bg_bytes: bytes
    full_bytes: bytes
    bg_width: int


class AuthTimeoutError(Exception):
    pass


async def _ensure_context_with_stealth(browser):
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
    )
    viewport_size = {"width": 1920, "height": 1080}
    context = await browser.new_context(
        user_agent=user_agent,
        viewport=viewport_size,
        screen=viewport_size,
        color_scheme="light",
        java_script_enabled=True,
    )
    page = await context.new_page()
    stealth = Stealth()
    await stealth.apply_stealth_async(page)
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
    )
    return context, page


async def _load_or_new_context(playwright):
    """Create a browser context, trying to reuse storage_state if enabled."""
    browser = await playwright.chromium.launch(headless=False)
    try:
        if (
            EQC_REUSE_SESSION
            and not EQC_CLEAR_SESSION
            and Path(EQC_STORAGE_STATE).exists()
        ):
            context = await browser.new_context(storage_state=EQC_STORAGE_STATE)
            page = await context.new_page()
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            # If already authenticated, the login form likely won't show
            if await page.locator("#loginBtn").count() == 0:
                logger.info("Reused existing EQC session from storage_state")
                return browser, context, page
            await context.close()

        context, page = await _ensure_context_with_stealth(browser)
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        return browser, context, page
    except Exception:
        await browser.close()
        raise


def _maybe_reset_storage_file() -> None:
    """Delete storage_state file when EQC_RESET_STORAGE=true.

    This is stronger than EQC_CLEAR_SESSION (which only ignores the file).
    """
    if not EQC_RESET_STORAGE:
        return
    try:
        p = Path(EQC_STORAGE_STATE)
        if p.exists():
            # 删除文件，确保本次运行绝对不受缓存影响
            p.unlink()
            logger.info(f"Reset storage_state file removed: {p}")
    except Exception as e:
        logger.warning(f"Failed to remove storage_state file: {e}")


async def _fill_login_form(page) -> bool:
    """Fill username/password/otp if available and click login.

    Returns True if the form was filled and login clicked; otherwise False.
    """
    # Selectors from docs/company_id/EQC/login_page_elements.md
    # 使用占位符定位更稳，CSS 作为回退
    sel_user = (
        "#app > div > div.login-input-wrap > div.login-content > "
        "div.password-login > div:nth-child(2) > form > "
        "div:nth-child(1) > div > div > input"
    )
    sel_pwd_relaxed = (
        "#app > div > div.login-input-wrap > div.login-content > "
        "div.password-login > div:nth-child(2) > form > "
        "div.el-form-item.form-input.pwd-input > div > div > input"
    )
    sel_otp = (
        "#app > div > div.login-input-wrap > div.login-content > "
        "div.password-login > div:nth-child(2) > form > "
        "div:nth-child(3) > div > div > input"
    )
    sel_btn = "#loginBtn"

    async def _ensure_account_tab() -> None:
        """If username field isn't visible, click the '账号登录/UM账号登录' tab."""
        try:
            fld = page.get_by_placeholder("平安集团UM账号").first
            if await fld.count() > 0 and await fld.is_visible():
                return
        except Exception:
            pass
        for text in ("账号登录", "UM账号登录", "账号", "UM"):
            try:
                tab = page.get_by_text(text, exact=False).first
                if await tab.count() > 0:
                    await tab.click()
                    await asyncio.sleep(0.2)
                    break
            except Exception:
                continue

    async def _ensure_agreement_checked() -> None:
        """Tick '已阅读并同意...' checkbox if present."""
        try:
            label = page.get_by_text("已阅读并同意", exact=False).first
            if await label.count() > 0:
                await label.click()
                await asyncio.sleep(0.1)
                return
        except Exception:
            pass
        try:
            box = page.locator(".el-checkbox__input, .el-checkbox__inner").first
            if await box.count() > 0:
                await box.click()
        except Exception:
            pass

    try:
        # 确保切换到账号登录 Tab
        await _ensure_account_tab()
        if EQC_USERNAME and EQC_PASSWORD:
            # username
            try:
                user_input = page.get_by_placeholder("平安集团UM账号")
                await user_input.fill(EQC_USERNAME)
            except Exception:
                user_input = page.locator(sel_user)
                await user_input.fill(EQC_USERNAME)

            # password（放宽选择器，避免状态类名匹配失败）
            try:
                pwd_input = page.get_by_placeholder("开机密码")
                await pwd_input.fill(EQC_PASSWORD)
            except Exception:
                pwd_input = page.locator(sel_pwd_relaxed)
                await pwd_input.fill(EQC_PASSWORD)
            if EQC_OTP:
                otp_input = page.locator(sel_otp)
                if await otp_input.count() > 0:
                    await otp_input.fill(EQC_OTP)
            # 勾选同意条款（如果需要）
            await _ensure_agreement_checked()
            # 等待登录按钮可用并点击
            btn = page.locator(sel_btn)
            try:
                await btn.wait_for()
            except Exception:
                pass
            await btn.click()
            return True
        else:
            logger.info(
                "Missing EQC_USERNAME/EQC_PASSWORD in env; please login manually."
            )
            return False
    except Exception as e:
        logger.warning(f"Auto-fill login form failed: {e}")
        return False


async def _wait_login_or_slider(page, timeout_ms: int = 25000) -> dict:
    success_sel = "text=搜索"
    panel_sel = "div.geetest_panel"
    handle_sel = "div.geetest_slider_button"

    t_success = asyncio.create_task(
        page.wait_for_selector(success_sel, timeout=timeout_ms)
    )
    t_slider = asyncio.create_task(
        page.wait_for_selector(f"{panel_sel}, {handle_sel}", timeout=timeout_ms)
    )
    done, pending = await asyncio.wait(
        {t_success, t_slider}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()

    if t_success in done:
        return {"status": "logged_in"}
    if t_slider in done:
        return {"status": "slider"}
    return {"status": "unknown"}


async def _capture_slider_images(page) -> Optional[SliderImages]:
    """Capture geetest bg/full canvases as PNG bytes.

    Returns None if canvases are not available.
    """
    # Prefer precise paths from docs; fallback to generic class names
    bg = page.locator(
        "body > div.geetest_panel.geetest_wind.geetest_customtype > "
        "div.geetest_panel_box.geetest_panel_type4.geetest_panelshowslide > "
        "div.geetest_panel_next > div > div.geetest_wrap > div.geetest_widget > "
        "div > a > div.geetest_canvas_img.geetest_absolute > div > "
        "canvas.geetest_canvas_bg.geetest_absolute, .geetest_canvas_bg"
    ).first
    fullbg = page.locator(
        "body > div.geetest_panel.geetest_wind.geetest_customtype > "
        "div.geetest_panel_box.geetest_panel_type4.geetest_panelshowslide > "
        "div.geetest_panel_next > div > div.geetest_wrap > div.geetest_widget > "
        "div > a > div.geetest_canvas_img.geetest_absolute > canvas, "
        ".geetest_canvas_fullbg"
    ).first
    widget = page.locator("div.geetest_canvas_img, div.geetest_widget").first

    try:
        # Some implementations hide fullbg; temporarily reveal
        await page.evaluate(
            """
            () => {
              const el = document.querySelector('.geetest_canvas_fullbg');
              if (el) { el.style.display='block'; el.style.opacity=1; }
            }
            """
        )
    except Exception:
        pass

    try:
        if await bg.count() > 0 and await fullbg.count() > 0:
            bg_bytes = await bg.screenshot(type="png")
            full_bytes = await fullbg.screenshot(type="png")
            # Decode to get width
            arr = np.frombuffer(bg_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return SliderImages(
                bg_bytes=bg_bytes, full_bytes=full_bytes, bg_width=int(img.shape[1])
            )
        elif await bg.count() > 0:
            # bg 存在但 full 不可见：先返回仅 bg，由上游选择边缘投影算法
            bg_bytes = await bg.screenshot(type="png")
            arr = np.frombuffer(bg_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return SliderImages(
                bg_bytes=bg_bytes, full_bytes=bg_bytes, bg_width=int(img.shape[1])
            )
        elif await widget.count() > 0:
            # 最弱回退：对容器截图做边缘投影
            w = await widget.screenshot(type="png")
            arr = np.frombuffer(w, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return SliderImages(bg_bytes=w, full_bytes=w, bg_width=int(img.shape[1]))
    except Exception as e:
        logger.warning(f"Capture slider images failed: {e}")
    return None


def _solve_offset_with_opencv(bg_bytes: bytes, full_bytes: bytes) -> int:
    bg = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    full = cv2.imdecode(np.frombuffer(full_bytes, np.uint8), cv2.IMREAD_COLOR)
    if bg is None or full is None:
        raise RuntimeError("Failed to decode slider images")

    h = min(bg.shape[0], full.shape[0])
    w = min(bg.shape[1], full.shape[1])
    bg, full = bg[:h, :w], full[:h, :w]

    # 如果 full 与 bg 几乎一致（无 full 可用），退化为单图边缘投影
    if np.array_equal(full, bg):
        gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        col_sum = edges.sum(axis=0)
    else:
        diff = cv2.absdiff(full, bg)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        col_sum = th.sum(axis=0)
    x = int(np.argmax(col_sum))
    return x


async def _drag_by_offset(page, offset_px: int, bg_img_width: int) -> None:
    handle = page.locator("div.geetest_slider_button").first
    track = page.locator("div.geetest_slider, div.geetest_widget").first
    box_track = await track.bounding_box()
    box_handle = await handle.bounding_box()
    if not box_track or not box_handle:
        raise RuntimeError("Failed to get slider bounding boxes")

    scale = box_track["width"] / float(bg_img_width)
    distance = offset_px * scale - (box_handle["width"] / 2)

    start_x = box_handle["x"] + box_handle["width"] / 2
    start_y = box_handle["y"] + box_handle["height"] / 2

    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    steps = 30
    for i in range(steps):
        t = i / (steps - 1)
        eased = 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t
        x = start_x + distance * eased
        y = start_y
        await page.mouse.move(x, y, steps=1)
        await asyncio.sleep(0.01)
    # slight overshoot and settle
    await page.mouse.move(start_x + distance + 2, start_y)
    await asyncio.sleep(0.05)
    await page.mouse.move(start_x + distance, start_y)
    await page.mouse.up()


async def _try_solve_slider(page) -> bool:
    if not EQC_AUTO_SLIDER:
        logger.info("Auto slider disabled by EQC_AUTO_SLIDER=false")
        return False
    try:
        # 确保面板/把手已出现
        try:
            await page.wait_for_selector("div.geetest_slider_button", timeout=10000)
        except PlaywrightTimeoutError:
            logger.info("Slider handle not visible; skip auto solve.")
            return False

        for attempt in range(1, 3):  # 尝试两次
            imgs = await _capture_slider_images(page)
            if not imgs:
                logger.info("Slider images not available; please solve manually.")
                return False
            offset = _solve_offset_with_opencv(imgs.bg_bytes, imgs.full_bytes)
            await _drag_by_offset(page, offset, imgs.bg_width)

            # Wait for panel to disappear or success hint
            try:
                await page.wait_for_selector(
                    "div.geetest_panel", state="detached", timeout=4000
                )
                logger.info("Slider likely solved (panel closed).")
                return True
            except PlaywrightTimeoutError:
                try:
                    await page.wait_for_selector(
                        ".geetest_success, text=验证成功", timeout=2000
                    )
                    logger.info("Slider solved with success hint.")
                    return True
                except PlaywrightTimeoutError:
                    logger.info(f"Slider attempt {attempt} uncertain; retrying...")
                    await asyncio.sleep(0.6)
        logger.info("Slider auto-solve attempts exhausted; please complete manually.")
        return False
    except Exception as e:
        logger.warning(f"Auto slider solve failed: {e}")
        return False


async def get_auth_token_interactively(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Login to EQC and capture token from request headers.

    This version attempts OpenCV-based slider solving and does not trigger
    extra search requests; it captures the first request that carries a
    'token' header after login.
    """
    token_future: asyncio.Future[str] = asyncio.Future()

    # 可选：在本次调用前清空 storage_state 文件
    _maybe_reset_storage_file()

    async with async_playwright() as pw:
        browser, context, page = await _load_or_new_context(pw)

        # Intercept all requests; pick first 'token' header
        # parse capture substrings (comma-separated)
        capture_subs = [
            s.strip() for s in EQC_CAPTURE_URL_SUBSTR.split(",") if s.strip()
        ]

        async def intercept(route):
            try:
                req = route.request
                token = req.headers.get("token")
                # Only capture when URL matches whitelist and token looks valid
                url_ok = (
                    any(sub in req.url for sub in capture_subs)
                    if capture_subs
                    else True
                )
                token_ok = (
                    token is not None
                    and token not in ("", "null", "undefined")
                    and len(token) >= 16
                )
                if url_ok and token_ok and not token_future.done():
                    logger.info(f"Captured token from {req.url}")
                    token_future.set_result(token)  # noqa: F821
                await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass

        await context.route("**/*", intercept)

        try:
            # If login button exists, assume not logged in
            if await page.locator("#loginBtn").count() > 0:
                await _fill_login_form(page)
                # Wait for either success or slider
                res = await _wait_login_or_slider(page, timeout_ms=15000)
                if res.get("status") == "slider":
                    solved = await _try_solve_slider(page)
                    if not solved:
                        logger.info("Please complete slider manually if still present.")

            # Wait for token up to timeout
            token = await asyncio.wait_for(token_future, timeout=timeout_seconds)

            if EQC_REUSE_SESSION:
                Path(EQC_STORAGE_STATE).parent.mkdir(parents=True, exist_ok=True)
                try:
                    await context.storage_state(path=EQC_STORAGE_STATE)
                    logger.info(f"Saved storage_state to {EQC_STORAGE_STATE}")
                except Exception as e:
                    logger.warning(f"Failed to save storage_state: {e}")
            return token

        except asyncio.TimeoutError:
            logger.error(f"Authentication timed out after {timeout_seconds} seconds")
            raise AuthTimeoutError(
                f"Authentication timed out after {timeout_seconds} seconds"
            )
        except PlaywrightTimeoutError as e:
            logger.error(f"Playwright timeout: {e}")
            return None
        except Exception as e:
            logger.error(f"Auth flow error: {e}")
            return None
        finally:
            try:
                await browser.close()
            except Exception:
                pass


def run_get_token(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Optional[str]:
    try:
        return asyncio.run(get_auth_token_interactively(timeout_seconds))
    except Exception as e:
        logger.error(f"Synchronous wrapper failed: {e}")
        return None
