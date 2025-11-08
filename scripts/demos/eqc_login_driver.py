#!/usr/bin/env python3
"""
EQC 登录驱动脚本（半自动）：
- 自动：切换到账号登录、填入账号/密码、勾选协议、点击登录
- 自动（可选）：尝试极验滑块（OpenCV），失败则手工完成
- 手工：验证码/令牌（你可在终端输入让脚本代填，或直接在浏览器里填）
- 结果：登录成功后拦截到首个带 token 头的请求并打印（不强制发搜索）

环境变量：
- EQC_USERNAME / EQC_PASSWORD（必需，或运行时交互输入）
- EQC_OTP（可选；若不提供，脚本会提示）
- EQC_LOGIN_URL（默认 https://eqc.pingan.com/）
- EQC_AUTO_SLIDER=true|false（默认 true）

运行：uv run python scripts/demos/eqc_login_driver.py
"""

from __future__ import annotations

import asyncio
import getpass
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

# 直接复用增强模块中的图像/拖拽工具
from work_data_hub.auth.eqc_auth_opencv import (
    _capture_slider_images,  # type: ignore
    _solve_offset_with_opencv,  # type: ignore
    _drag_by_offset,  # type: ignore
)


LOGIN_URL = os.getenv("EQC_LOGIN_URL", "https://eqc.pingan.com/")
EQC_AUTO_SLIDER = os.getenv("EQC_AUTO_SLIDER", "true").lower() == "true"


async def ensure_context_with_stealth(browser):
    context = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await context.new_page()
    stealth = Stealth()
    await stealth.apply_stealth_async(page)
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
    )
    return context, page


async def ensure_account_tab(page):
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


async def ensure_agreement_checked(page):
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


async def fill_credentials(page, username: str, password: str) -> None:
    # 占位符优先；CSS 回退
    sel_user = (
        "#app > div > div.login-input-wrap > div.login-content > div.password-login > "
        "div:nth-child(2) > form > div:nth-child(1) > div > div > input"
    )
    sel_pwd_relaxed = (
        "#app > div > div.login-input-wrap > div.login-content > div.password-login > "
        "div:nth-child(2) > form > div.el-form-item.form-input.pwd-input > div > div > input"
    )
    try:
        await ensure_account_tab(page)
        try:
            u = page.get_by_placeholder("平安集团UM账号")
            await u.fill(username)
        except Exception:
            await page.locator(sel_user).fill(username)
        try:
            p = page.get_by_placeholder("开机密码")
            await p.fill(password)
        except Exception:
            await page.locator(sel_pwd_relaxed).fill(password)
    except Exception as e:
        print(f"⚠️ 填写账号密码失败: {e}")


async def maybe_fill_otp(page, otp_env: Optional[str]) -> None:
    sel_otp = (
        "#app > div > div.login-input-wrap > div.login-content > div.password-login > "
        "div:nth-child(2) > form > div:nth-child(3) > div > div > input"
    )
    otp_box = page.locator(sel_otp)
    try:
        if await otp_box.count() == 0:
            return
        if otp_env:
            await otp_box.fill(otp_env)
            return
        print("🔐 检测到验证码/令牌输入框。")
        choice = input("在终端输入(1) 或 在浏览器中手动输入后按回车(2) [默认2]: ").strip() or "2"
        if choice == "1":
            otp = input("请输入验证码/令牌: ").strip()
            await otp_box.fill(otp)
        else:
            input("请在浏览器中输入验证码/令牌，完成后按回车继续...")
    except Exception:
        pass


async def click_login(page):
    await ensure_agreement_checked(page)
    btn = page.locator("#loginBtn")
    try:
        await btn.wait_for(timeout=10000)
    except Exception:
        pass
    await btn.click()


async def try_slider(page) -> bool:
    try:
        await page.wait_for_selector("div.geetest_slider_button", timeout=8000)
    except PlaywrightTimeoutError:
        return False
    if not EQC_AUTO_SLIDER:
        print("ℹ️ 检测到滑块，但已关闭自动解算。请手工完成后按回车继续...")
        input()
        return True
    print("🧩 检测到滑块，尝试自动解算...")
    for attempt in range(1, 3):
        imgs = await _capture_slider_images(page)
        if not imgs:
            print("⚠️ 无法获取滑块图片，改为手工。完成后按回车继续...")
            input()
            return True
        offset = _solve_offset_with_opencv(imgs.bg_bytes, imgs.full_bytes)
        await _drag_by_offset(page, offset, imgs.bg_width)
        try:
            await page.wait_for_selector("div.geetest_panel", state="detached", timeout=4000)
            print("✅ 滑块已关闭。")
            return True
        except PlaywrightTimeoutError:
            print(f"⚠️ 第 {attempt} 次尝试未确认成功，重试...")
            await asyncio.sleep(0.6)
    print("ℹ️ 自动解算不稳定，请手工完成后按回车继续...")
    input()
    return True


async def main():
    user = os.getenv("EQC_USERNAME") or input("请输入 EQC_USERNAME: ").strip()
    pwd = os.getenv("EQC_PASSWORD") or getpass.getpass("请输入 EQC_PASSWORD: ")
    otp_env = os.getenv("EQC_OTP")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context, page = await ensure_context_with_stealth(browser)

        # 捕获 token
        token_future: asyncio.Future[str] = asyncio.Future()

        async def intercept(route):
            try:
                req = route.request
                token = req.headers.get("token")
                if token and not token_future.done():
                    token_future.set_result(token)
                await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass

        await context.route("**/*", intercept)

        print("🌐 打开登录页...")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await ensure_account_tab(page)
        await fill_credentials(page, user, pwd)
        await maybe_fill_otp(page, otp_env)
        await click_login(page)

        # 等待滑块或直接成功
        res = None
        try:
            await page.wait_for_selector("div.geetest_panel, div.geetest_slider_button", timeout=6000)
            res = "slider"
        except PlaywrightTimeoutError:
            res = "maybe-logged"
        if res == "slider":
            await try_slider(page)

        print("⏳ 等待登录后请求出现 token（或手工完成剩余验证）...")
        try:
            token = await asyncio.wait_for(token_future, timeout=300)
            print(f"🎉 成功获取 token（长度 {len(token)}）: {token}")
        except asyncio.TimeoutError:
            print("❌ 在超时时间内未捕获到 token。请确认是否已进入系统主页。")

        try:
            await browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())

