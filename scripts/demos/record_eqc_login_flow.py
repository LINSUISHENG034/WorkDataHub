#!/usr/bin/env python3
"""
EQC 登录过程动作记录器（手动操作轨迹采集）

目的：当自动化失败或流程未知时，记录真实人工登录过程中的关键操作、
DOM/网络事件与截图，形成可复现的“时间线日志”，用于后续脚本自动化改造。

特性：
- 记录：点击/输入/切换 Tab/键盘等交互（内容脱敏，仅记录类型和目标选择器）
- 观察：极验面板（.geetest_panel）出现/消失、把手出现等关键信号
- 网络：记录请求基本信息（URL、方法、状态码）；token 仅记录“存在与长度”，不落盘明文
- 截图：关键事件自动截图；也可在终端按回车随时手动打点截图
- 输出：logs/eqc_login_record/<ts>/events.jsonl, requests.jsonl, timeline.md, screenshots/

运行：
    uv run python scripts/demos/record_eqc_login_flow.py

提示：
- 打开后请像平时一样手动完成整个登录过程。
- 当你认为“已经成功进入系统”时，回到终端按回车结束记录并生成报告。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

LOGIN_URL = os.getenv("EQC_LOGIN_URL", "https://eqc.pingan.com/")
OUT_DIR = Path(os.getenv("EQC_RECORD_OUT", "logs/eqc_login_record"))


@dataclass
class Recorder:
    out_dir: Path
    events: List[Dict[str, Any]]
    requests: List[Dict[str, Any]]
    step_id: int = 0

    async def snapshot(self, page, label: str) -> None:
        self.step_id += 1
        p = self.out_dir / "screenshots" / f"{self.step_id:03d}_{label}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            await page.screenshot(path=str(p), full_page=True)
        except Exception:
            pass

    def log_event(self, kind: str, data: Dict[str, Any]) -> None:
        evt = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "kind": kind,
            **data,
        }
        self.events.append(evt)

    def log_request(self, data: Dict[str, Any]) -> None:
        self.requests.append(
            {
                "ts": datetime.utcnow().isoformat() + "Z",
                **data,
            }
        )

    def flush(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        with (self.out_dir / "events.jsonl").open("w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with (self.out_dir / "requests.jsonl").open("w", encoding="utf-8") as f:
            for r in self.requests:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        # 简要时间线
        with (self.out_dir / "timeline.md").open("w", encoding="utf-8") as f:
            f.write("# EQC 登录动作记录时间线\n\n")
            for e in self.events:
                f.write(f"- [{e['ts']}] {e['kind']}: {e.get('summary', '')}\n")


INIT_JS = r"""
(() => {
  // 简易选择器构造（尽量稳定）
  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) return `#${el.id}`;
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 5) {
      let selector = el.nodeName.toLowerCase();
      if (el.className) {
        const cls = Array.from(el.classList).slice(0,2).join('.');
        if (cls) selector += '.' + cls;
      }
      const parent = el.parentNode;
      if (!parent) break;
      const siblings = Array.from(parent.children).filter(n => n.nodeName === el.nodeName);
      if (siblings.length > 1) {
        const index = siblings.indexOf(el) + 1;
        selector += `:nth-child(${index})`;
      }
      parts.unshift(selector);
      el = parent;
    }
    return parts.join(' > ');
  }

  function summarizeTarget(t) {
    try {
      return {
        tag: t.tagName,
        id: t.id || null,
        classes: t.className || null,
        name: t.getAttribute('name') || null,
        placeholder: t.getAttribute('placeholder') || null,
        role: t.getAttribute('role') || null,
        text: (t.innerText || '').slice(0, 20),
        css: cssPath(t),
      };
    } catch (_) { return { css: '[unavailable]' }; }
  }

  function emit(kind, payload) {
    const msg = { kind, payload };
    console.log('EQC_REC:' + JSON.stringify(msg));
  }

  // 交互监听：click/input/change/keydown
  ['click', 'change', 'input', 'keydown'].forEach(type => {
    document.addEventListener(type, (e) => {
      const t = e.target;
      const valInfo = (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA'))
        ? { value_len: (t.value || '').length }
        : {};
      emit('dom_event', {
        type,
        target: summarizeTarget(t),
        key: e.key || null,
        ...valInfo,
      });
    }, true);
  });

  // 极验面板观察
  const observer = new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (n.nodeType === 1 && n.matches && n.matches('div.geetest_panel')) {
          emit('geetest_panel', { action: 'added' });
        }
      }
      for (const n of m.removedNodes) {
        if (n.nodeType === 1 && n.matches && n.matches('div.geetest_panel')) {
          emit('geetest_panel', { action: 'removed' });
        }
      }
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
"""


async def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_DIR / ts
    rec = Recorder(out_dir=out_dir, events=[], requests=[])

    print("🔴 启动登录动作记录器...")
    print(f"输出目录: {out_dir}")
    print("操作指引：")
    print("1) 将弹出的浏览器窗口置于前台，按日常流程手动登录")
    print("2) 过程中脚本会自动记录动作与网络请求；如需手动打点截图，回到终端按回车")
    print("3) 登录成功后回到终端按回车结束并生成报告")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1366, "height": 900})
        page = await context.new_page()

        # 反指纹
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )
        await page.add_init_script(INIT_JS)

        # 页面事件
        page.on("console", lambda msg: _on_console(rec, msg))
        page.on(
            "framenavigated",
            lambda frame: rec.log_event(
                "framenavigated",
                {"url": frame.url, "summary": f"navigated: {frame.url}"},
            ),
        )
        page.on(
            "load",
            lambda: rec.log_event("load", {"url": page.url, "summary": "page load"}),
        )

        # 网络事件（无需拦截，避免干扰登录）
        page.on("requestfinished", lambda req: _on_request_finished(rec, req))
        page.on("response", lambda resp: _on_response(rec, resp))

        # 页面关闭/浏览器断开时自动收尾
        async def _finalize_and_close():
            try:
                await rec.snapshot(page, "final")
            except Exception:
                pass
            rec.flush()
            try:
                # 生成可回放脚本
                generate_replay_script(rec.events, out_dir)
            except Exception:
                pass
            print(f"✅ 已生成日志与回放脚本：{out_dir}")

        def _on_page_close():
            # 在事件循环中调度收尾，防止阻塞回调
            asyncio.create_task(asyncio.sleep(0))
            asyncio.create_task(_finalize_and_close())

        page.on("close", lambda: _on_page_close())
        browser.on("disconnected", lambda: _on_page_close())

        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await rec.snapshot(page, "landing")
        rec.log_event("open", {"url": LOGIN_URL, "summary": "open login url"})

        print("📼 已开始自动记录。关闭浏览器窗口以结束并生成报告与回放脚本...")
        # 等待页面关闭（用户手动关闭浏览器）
        try:
            await page.wait_for_event("close")
        except Exception:
            pass
        # 给予回调时间完成收尾
        await asyncio.sleep(0.5)
        try:
            await browser.close()
        except Exception:
            pass
        print(f"📦 输出目录：{out_dir}")


def _on_console(rec: Recorder, msg) -> None:
    try:
        txt = msg.text()
        if not txt.startswith("EQC_REC:"):
            return
        payload = json.loads(txt[len("EQC_REC:") :])
        kind = payload.get("kind", "console")
        data = payload.get("payload", {})
        # 补充摘要
        summary = data.get("type") or data.get("action") or "event"
        tgt = data.get("target", {})
        if tgt:
            summary += (
                f" @ {tgt.get('css') or tgt.get('placeholder') or tgt.get('id') or ''}"
            )
        rec.log_event(kind, {**data, "summary": summary})
    except Exception:
        pass


def _on_request_finished(rec: Recorder, req) -> None:
    try:
        hdrs = req.headers
        token = hdrs.get("token")
        rec.log_request(
            {
                "event": "requestfinished",
                "method": req.method,
                "url": req.url,
                "has_token": bool(token),
                "token_len": len(token) if token else 0,
            }
        )
    except Exception:
        pass


def _on_response(rec: Recorder, resp) -> None:
    try:
        rec.log_request(
            {
                "event": "response",
                "status": resp.status,
                "url": resp.url,
            }
        )
    except Exception:
        pass


def _choose_selector_snippet(target: Dict[str, Any]) -> str:
    """Choose a robust selector expression for Playwright code generation.

    Preference order: id -> placeholder -> text -> css
    """
    tid = target.get("id")
    placeholder = target.get("placeholder")
    text = (target.get("text") or "").strip()
    css = target.get("css") or ""
    if tid:
        return f"page.locator('#{tid}')"
    if placeholder:
        return f"page.get_by_placeholder('{placeholder}')"
    if text:
        # Escape quotes/simple truncation handled earlier
        return f"page.get_by_text('{text}')"
    if css:
        return f"page.locator('{css}')"
    return "page.locator('body')"


def _infer_fill_value_env(target: Dict[str, Any]) -> str:
    placeholder = target.get("placeholder") or ""
    text = (target.get("text") or "").strip()
    hint = placeholder + text
    if any(k in hint for k in ["UM", "账号", "用户名"]):
        return "os.getenv('EQC_USERNAME', '<REPLACE_ME>')"
    if any(k in hint for k in ["密码", "pass"]):
        return "os.getenv('EQC_PASSWORD', '<REPLACE_ME>')"
    if any(k in hint for k in ["令牌", "验证码", "OTP"]):
        return "os.getenv('EQC_OTP', '')"
    return "'<REPLACE_ME>'"


def generate_replay_script(events: List[Dict[str, Any]], out_dir: Path) -> None:
    """Generate a minimal Playwright Python script to replay key actions.

    We currently map click/input/keydown(Enter) into code, with basic waits.
    Sensitive values are read from environment variables or placeholders.
    """
    lines: List[str] = []
    lines.append("#!/usr/bin/env python3")
    lines.append("import asyncio, os")
    lines.append("from playwright.async_api import async_playwright")
    lines.append("")
    lines.append("LOGIN_URL = os.getenv('EQC_LOGIN_URL', 'https://eqc.pingan.com/')")
    lines.append("")
    lines.append("async def main():")
    lines.append("    async with async_playwright() as pw:")
    lines.append("        browser = await pw.chromium.launch(headless=False)")
    lines.append(
        "        context = await browser.new_context(viewport={'width':1366,'height':900})"
    )
    lines.append("        page = await context.new_page()")
    lines.append("        await page.goto(LOGIN_URL, wait_until='domcontentloaded')")
    lines.append("")

    # Deduplicate consecutive events on same selector/type
    last_key = None
    for e in events:
        if e.get("kind") == "dom_event":
            payload = e
            etype = payload.get("type")
            tgt = payload.get("target", {})
            sel = _choose_selector_snippet(tgt)
            key = (etype, sel)
            if key == last_key:
                continue
            last_key = key
            if etype == "click":
                lines.append(f"        await {sel}.wait_for()")
                lines.append(f"        await {sel}.click()")
            elif etype in ("input", "change"):
                val = _infer_fill_value_env(tgt)
                lines.append(f"        await {sel}.wait_for()")
                lines.append(f"        await {sel}.fill({val})")
            elif etype == "keydown" and (payload.get("key") or "").lower() == "enter":
                lines.append("        await page.keyboard.press('Enter')")
        elif e.get("kind") == "geetest_panel":
            action = e.get("action") or e.get("payload", {}).get("action")
            if action == "added":
                lines.append(
                    "        # Geetest panel detected -> complete slider manually or via automation here"
                )
            elif action == "removed":
                lines.append("        # Geetest panel closed")

    lines.append("        await page.wait_for_timeout(1000)")
    lines.append("        # Keep the browser open for inspection if needed")
    lines.append("        # await page.pause()")
    lines.append("        await browser.close()")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    asyncio.run(main())")

    out_dir.mkdir(parents=True, exist_ok=True)
    replay = out_dir / "replay.py"
    replay.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断，已退出。")
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        sys.exit(1)
