"""Enhanced EQC authentication with automated QR code login switching.

This script extends the functionality of eqc_auth_handler.py by automatically
browsing to the QR code login section, reducing manual user steps.
"""

import asyncio
import logging
import multiprocessing
import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import PhotoImage
from typing import Optional

# Ensure 'src' is in sys.path to allow direct execution
# Points to E:\Projects\WorkDataHub\src based on file location
src_path = Path(__file__).resolve().parents[3]
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from playwright.async_api import Page, Route, ViewportSize, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

from work_data_hub.io.auth.models import AuthTimeoutError, BrowserError
from work_data_hub.io.auth.eqc_auth_handler import (
    LOGIN_URL,
    TARGET_API_PATH,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_ENV_FILE,
    EQC_TOKEN_KEY,
    _update_env_file
)

logger = logging.getLogger(__name__)


def _show_qr_ui(image_path: str, status_queue: multiprocessing.Queue):
    """
    Display the QR code in a polished, modern Tkinter window.
    Designed to run in a separate process.
    """
    try:
        # Enable High DPI support for Windows (fixes blurry text)
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        root = tk.Tk()
        root.title("扫码登录 - 平安E企查")

        # --- Theme Config ---
        THEME = {
            "primary": "#FF6400",        # Ping An Orange
            "primary_bg": "#FFF0E6",     # Very light orange background
            "bg": "#F5F7FA",             # Window background
            "card": "#FFFFFF",           # Card background
            "text_main": "#1F2329",
            "text_sub": "#8F959E",
            "border": "#E4E7ED",
            "success": "#52C41A"
        }

        # Callback for manual close
        def on_close():
            status_queue.put("USER_CLOSED")
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)

        # Window Layout
        window_width = 360
        window_height = 480
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)

        root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        root.resizable(False, False)
        root.configure(bg=THEME["bg"])
        root.attributes('-topmost', True)

        # Main Card Container
        main_frame = tk.Frame(root, bg=THEME["card"], padx=20, pady=20)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=15, pady=15)

        # --- Header ---
        header_frame = tk.Frame(main_frame, bg=THEME["card"])
        header_frame.pack(fill=tk.X, pady=(10, 20))

        title_label = tk.Label(
            header_frame,
            text="扫码安全登录",
            font=("Microsoft YaHei UI", 16, "bold"),
            bg=THEME["card"],
            fg=THEME["text_main"]
        )
        title_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text="请使用「快乐平安」APP 扫一扫",
            font=("Microsoft YaHei UI", 9),
            bg=THEME["card"],
            fg=THEME["text_sub"]
        )
        subtitle_label.pack(pady=(5, 0))

        # --- QR Code Section with Viewfinder ---
        qr_frame = tk.Frame(main_frame, bg=THEME["card"])
        qr_frame.pack(expand=True)

        # Canvas for drawing viewfinder corners
        canvas_size = 200
        qr_canvas = tk.Canvas(
            qr_frame,
            width=canvas_size,
            height=canvas_size,
            bg=THEME["card"],
            highlightthickness=0,
            bd=0
        )
        qr_canvas.pack()

        try:
            # Load Image
            img_raw = PhotoImage(file=image_path)
            # Center image on canvas
            qr_canvas.create_image(canvas_size // 2, canvas_size // 2, image=img_raw)
            qr_canvas.image = img_raw  # Keep reference

            # Draw Viewfinder Corners
            length = 20
            width = 3
            color = THEME["primary"]
            w, h = canvas_size, canvas_size
            pad = 5  # Padding inside canvas edge

            # Top-Left
            qr_canvas.create_line(pad, pad, pad + length, pad, fill=color, width=width)
            qr_canvas.create_line(pad, pad, pad, pad + length, fill=color, width=width)

            # Top-Right
            qr_canvas.create_line(w - pad, pad, w - pad - length, pad, fill=color, width=width)
            qr_canvas.create_line(w - pad, pad, w - pad, pad + length, fill=color, width=width)

            # Bottom-Left
            qr_canvas.create_line(pad, h - pad, pad + length, h - pad, fill=color, width=width)
            qr_canvas.create_line(pad, h - pad, pad, h - pad - length, fill=color, width=width)

            # Bottom-Right
            qr_canvas.create_line(w - pad, h - pad, w - pad - length, h - pad, fill=color, width=width)
            qr_canvas.create_line(w - pad, h - pad, w - pad, h - pad - length, fill=color, width=width)

        except Exception as e:
            qr_canvas.create_text(
                canvas_size // 2,
                canvas_size // 2,
                text="二维码加载失败",
                fill="red",
                font=("Microsoft YaHei UI", 10)
            )

        # --- Instructions Pill ---
        instr_frame = tk.Frame(main_frame, bg=THEME["card"], pady=20)
        instr_frame.pack(fill=tk.X)

        pill_frame = tk.Frame(instr_frame, bg=THEME["primary_bg"], padx=15, pady=8)
        pill_frame.pack()

        instr_label = tk.Label(
            pill_frame,
            text="打开APP  >  右上角 + 号  >  扫一扫",
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=THEME["primary_bg"],
            fg=THEME["primary"]
        )
        instr_label.pack()

        # --- Footer Status ---
        footer_frame = tk.Frame(main_frame, bg=THEME["card"])
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))

        status_label = tk.Label(
            footer_frame,
            text="等待扫码中...",
            font=("Microsoft YaHei UI", 9),
            bg=THEME["card"],
            fg=THEME["text_sub"]
        )
        status_label.pack()

        # Simple Text Animation
        def animate_status(count=0):
            dots = "." * ((count % 3) + 1)
            status_label.config(text=f"等待扫码中{dots}")
            root.after(600, lambda: animate_status(count + 1))

        animate_status()

        root.mainloop()
    except Exception:
        # Fail silently in UI process to not crash main logic
        pass


async def _take_debug_screenshot(page: Page, name_suffix: str) -> None:
    """Helper to take timestamped screenshots for debugging."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"debug_eqc_{timestamp}_{name_suffix}.png"
        screenshot_path = Path("debug_screenshots") / filename
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        await page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Saved debug screenshot to: {screenshot_path}")
    except Exception as e:
        logger.warning(f"Failed to take debug screenshot: {e}")


async def get_auth_token_auto_qr(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """
    Launch browser, auto-navigate to QR login, and capture token.

    Args:
        timeout_seconds: Maximum time to wait for authentication

    Returns:
        Captured authentication token string, or None
    """
    logger.info("Starting auto-QR EQC authentication...")
    
    # Store process reference to cleanup later
    qr_ui_process: Optional[multiprocessing.Process] = None
    qr_image_path: Optional[Path] = None

    try:
        async with async_playwright() as playwright:
            browser = None
            try:
                # Launch browser in headless mode for better experience
                logger.debug("Launching Chromium browser in headless mode")
                browser = await playwright.chromium.launch(headless=True)

                # --- Stealth Config ---
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/116.0.0.0 Safari/537.36"
                )
                viewport_size: ViewportSize = {"width": 1920, "height": 1080}

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
                
                js_stealth = """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                """
                await page.add_init_script(js_stealth)
                # ---------------------

                token_future: asyncio.Future[str] = asyncio.Future()

                async def intercept_request(route: Route) -> None:
                    try:
                        request = route.request
                        if TARGET_API_PATH in request.url:
                            token = request.headers.get("token")
                            if token and not token_future.done():
                                logger.info("Successfully captured authentication token")
                                token_future.set_result(token)
                        await route.continue_()
                    except Exception as e:
                        logger.error(f"Error in request interception: {e}")
                        try:
                            await route.continue_()
                        except Exception:
                            pass

                await context.route("**/*", intercept_request)

                logger.info("Navigating to EQC login page...")
                await page.goto(LOGIN_URL, wait_until="domcontentloaded")

                # --- 1. Robust Navigation Logic ---
                logger.info("Verifying page state...")
                await page.wait_for_timeout(2000)
                current_url = page.url
                
                if "login" not in current_url and ("index" in current_url or current_url.endswith("/")):
                    logger.info("Detected Index page. Attempting to navigate to Login...")
                    try:
                        experience_btn = page.locator("text=立即体验").first
                        login_btn = page.locator("text=登录").first
                        
                        if await experience_btn.is_visible(timeout=5000):
                            logger.info("Clicking '立即体验'...")
                            await experience_btn.click()
                        elif await login_btn.is_visible(timeout=5000):
                            logger.info("Clicking '登录'...")
                            await login_btn.click()
                        else:
                            logger.warning("No navigation buttons found. Forcing URL navigation.")
                            await page.goto(f"{LOGIN_URL.rstrip('/')}/#/login")
                        
                        try:
                            await page.wait_for_url("**/login", timeout=10000)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.error(f"Navigation logic failed: {e}")
                        await page.goto(f"{LOGIN_URL.rstrip('/')}/#/login")

                # --- 2. Ensure Login Page Loaded ---
                user_provided_xpath = "xpath=/html/body/div[1]/div/div[3]/div[2]/div[1]/img"
                
                try:
                    await page.wait_for_selector(".login_box", state="visible", timeout=5000)
                    logger.info("Login box detected.")
                except Exception:
                    logger.info("Standard '.login_box' not found, checking user-provided XPath...")
                    try:
                        if await page.locator(user_provided_xpath).is_visible(timeout=5000):
                             logger.info("Login page element detected via user XPath.")
                        else:
                             await page.wait_for_selector(".login_box", state="visible", timeout=5000)
                    except Exception:
                        logger.warning("Login page elements check failed (might still work if partially loaded).")

                # --- 3. Auto-Switch to QR Code ---
                logger.info("Attempting to switch to QR code login view...")
                try:
                    if await page.locator("text=扫描二维码").is_visible(timeout=2000):
                        logger.info("QR code view appears to be already active.")
                    else:
                        potential_selectors = [
                            user_provided_xpath,
                            ".login_box > img",
                            ".login_box div > img",
                            ".login_box .login_switch",
                            "img[src*='qr']",
                            "img[src*='code']"
                        ]
                        
                        switch_found = False
                        for selector in potential_selectors:
                            elements = await page.locator(selector).all()
                            for el in elements:
                                if await el.is_visible():
                                    box = await el.bounding_box()
                                    if box and box['width'] < 100 and box['height'] < 100:
                                        await el.click()
                                        await page.wait_for_timeout(1000)
                                        if await page.locator("text=扫描二维码").is_visible() or \
                                           await page.locator("text=微信").is_visible():
                                            logger.info("Successfully switched to QR mode.")
                                            switch_found = True
                                            break
                            if switch_found:
                                break
                except Exception as e:
                    logger.warning(f"Error during QR switch attempt: {e}")

                # --- 4. Auto-Agree Checkbox ---
                logger.info("Checking for User Agreement...")
                try:
                    js_click = """
                    () => {
                        const el = document.querySelector('.statement .el-checkbox__inner');
                        if (el) {
                            el.click();
                            return true;
                        }
                        return false;
                    }
                    """
                    clicked = await page.evaluate(js_click)
                    if clicked:
                         logger.info("Clicked Agreement checkbox via JS.")
                    else:
                         logger.warning("Could not find checkbox via JS selector")
                except Exception as e:
                    logger.warning(f"Failed to handle agreement: {e}")

                # --- 5. Capture and Show QR Code (Unified UI) ---
                logger.info("Capturing QR code...")
                status_queue = multiprocessing.Queue() # Create queue for UI status

                try:
                    qr_box = page.locator(".qrcode-box")
                    await qr_box.wait_for(state="visible", timeout=10000)
                    
                    # Save temporary screenshot
                    timestamp = datetime.now().strftime("%H%M%S")
                    qr_image_path = Path(f"temp_qr_{timestamp}.png").resolve()
                    await qr_box.screenshot(path=str(qr_image_path))
                    logger.info(f"QR Code captured.")
                    
                    # Launch Unified UI in separate process
                    qr_ui_process = multiprocessing.Process(
                        target=_show_qr_ui, 
                        args=(str(qr_image_path), status_queue)
                    )
                    qr_ui_process.start()
                    logger.info("Popup opened. Waiting for scan...")
                    
                except Exception as e:
                    logger.error(f"Failed to capture/show QR code: {e}")
                    pass

                # ---------------------------------------------

                # Wait for token OR UI close
                async def check_ui_close():
                    while True:
                        if not status_queue.empty():
                            msg = status_queue.get()
                            if msg == "USER_CLOSED":
                                return "USER_CLOSED"
                        await asyncio.sleep(0.5)
                
                ui_task = asyncio.create_task(check_ui_close())
                
                done, pending = await asyncio.wait(
                    [token_future, ui_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=timeout_seconds
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # Check results
                if ui_task in done:
                    try:
                        if ui_task.result() == "USER_CLOSED":
                            logger.warning("用户手动关闭了二维码窗口，登录已取消。")
                            return None
                    except asyncio.CancelledError:
                        pass
                
                if token_future in done:
                    token = token_future.result()
                    logger.info("Authentication completed successfully")
                    return token
                
                # If neither is done, it means timeout occurred (asyncio.wait timeout)
                raise AuthTimeoutError(f"Authentication timed out after {timeout_seconds} seconds")

            except AuthTimeoutError:
                raise
            except PlaywrightTimeoutError as exc:
                logger.error("Playwright timeout error")
                raise BrowserError("Playwright timed out") from exc
            except Exception as exc:
                logger.error("Browser operation error: %s", exc)
                raise BrowserError("Browser operation failed") from exc
            finally:
                # 1. Close Browser
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                
                # 2. Close UI Popup
                if qr_ui_process and qr_ui_process.is_alive():
                    logger.debug("Closing QR Code window...")
                    qr_ui_process.terminate()
                    qr_ui_process.join(timeout=1)
                
                # 3. Clean up temp file
                if qr_image_path and qr_image_path.exists():
                    try:
                        qr_image_path.unlink()
                        logger.debug(f"Cleaned up temp QR file: {qr_image_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {qr_image_path}: {e}")

    except BrowserError:
        raise
    except Exception as exc:
        logger.error("Unexpected authentication error: %s", exc)
        raise BrowserError("Unexpected authentication error") from exc


def run_get_token_auto_qr(
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    save_to_env: bool = False,
    env_file: str = DEFAULT_ENV_FILE,
) -> Optional[str]:
    """Sync wrapper for auto_eqc_auth."""
    def _mask_token(value: str) -> str:
        if not value:
            return "<empty>"
        if len(value) <= 12:
            return "<redacted>"
        return f"{value[:8]}...{value[-4:]}"

    try:
        token = asyncio.run(get_auth_token_auto_qr(timeout_seconds))
        
        if token and save_to_env:
            # Add timestamp comment to the token value
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            token_with_comment = f"{token} # Updated: {timestamp}"
            
            success = _update_env_file(env_file, EQC_TOKEN_KEY, token_with_comment)
            if success:
                print(f"✅ Token 已自动保存到 {env_file}")
            else:
                print(f"⚠️ Token 保存失败，请手动更新 {env_file}")
                print(f"   {EQC_TOKEN_KEY}={_mask_token(token)}  # redacted")
        
        return token
    except Exception as exc:
        logger.error("Synchronous wrapper failed: %s", exc)
        return None

if __name__ == "__main__":
    # Needed for multiprocessing on Windows
    multiprocessing.freeze_support()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    print("Running Auto-QR Auth Script...")
    token = run_get_token_auto_qr(save_to_env=True)
    if token:
        print(f"Success! Token captured.")
    else:
        print("Failed to get token.")
