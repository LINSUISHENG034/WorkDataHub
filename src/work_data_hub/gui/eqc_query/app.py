"""
EQC Quick Query GUI Application.

Tkinter-based GUI for quick EQC company lookups with optional database persistence.
Uses a refined "Ping An Orange" theme with improved layout and usability.
"""

import multiprocessing
import tkinter as tk
from tkinter import messagebox
from typing import Callable

import pyperclip  # type: ignore

from work_data_hub.gui.eqc_query.controller import EqcQueryController, QueryResult
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

# --- Theme Configuration ---
THEME = {
    # Brand Colors - Refined for visual comfort
    "primary": "#FF6400",  # Ping An Orange (Primary buttons/Highlights only)
    "primary_hover": "#E65C00",
    "primary_active": "#CC5200",
    "primary_bg": "#FFFFFF",  # White for cleanliness
    "secondary": "#F5F7FA",  # Light gray for secondary elements
    "secondary_hover": "#E8EBF0",
    "secondary_active": "#DCDFE6",

    # Backgrounds
    "bg_window": "#F0F2F5",  # Neutral light gray (Anti-fatigue)
    "bg_card": "#FFFFFF",    # Clean white cards
    "bg_input": "#FAFBFC",   # Slightly off-white for inputs

    # Text - Softer contrast
    "text_main": "#1F2329",   # Dark gray instead of pure black
    "text_sub": "#606266",    # Medium gray for secondary text
    "text_placeholder": "#909399",
    "text_on_primary": "#FFFFFF",

    # Status Colors - Toned down saturation
    "success": "#52C41A",     # Softer green
    "success_hover": "#47A817",
    "warning": "#FAAD14",     # Softer orange
    "error": "#F5222D",       # Softer red

    # Borders
    "border": "#E4E7ED",      # Standard lighter border
    "border_focus": "#FF6400",

    # Shadows (simulated)
    "shadow": "#D9DCE1",
}

FONTS = {
    "h1": ("Microsoft YaHei UI", 18, "bold"),
    "h2": ("Microsoft YaHei UI", 14, "bold"),
    "body": ("Microsoft YaHei UI", 10),
    "body_bold": ("Microsoft YaHei UI", 10, "bold"),
    "small": ("Microsoft YaHei UI", 9),
    "mono": ("Consolas", 10),
}


class HoverButton(tk.Button):
    """Button with hover effect."""

    def __init__(
        self,
        master: tk.Widget,
        bg_normal: str,
        bg_hover: str,
        bg_active: str | None = None,
        **kwargs: object
    ) -> None:
        super().__init__(master, bg=bg_normal, **kwargs)
        self.bg_normal = bg_normal
        self.bg_hover = bg_hover
        self.bg_active = bg_active or bg_hover

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        if str(self.cget("state")) != "disabled":
            self.config(bg=self.bg_hover)

    def _on_leave(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        if str(self.cget("state")) != "disabled":
            self.config(bg=self.bg_normal)

    def _on_press(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        if str(self.cget("state")) != "disabled":
            self.config(bg=self.bg_active)

    def _on_release(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        if str(self.cget("state")) != "disabled":
            self.config(bg=self.bg_hover)


class EqcQueryApp:
    """
    EQC Quick Query GUI Application (Optimized).

    Features:
    - Clean, card-based layout with hover effects
    - Rich text query results
    - One-click copy for Company ID and Unified Code
    - Keyboard shortcuts (Enter to search, Ctrl+C to copy ID)
    - Auto-authentication
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = EqcQueryController()

        # State variables
        self.search_mode = tk.StringVar(value="name")
        self.current_result: QueryResult | None = None

        self._setup_window()
        self._create_widgets()
        self._bind_shortcuts()

        # Auto-validate existing token on startup
        self.root.after(100, self._try_auto_login)

    def _setup_window(self) -> None:
        """Configure the main window settings."""
        self.root.title("EQC 快速查询 - 平安E企查")
        self.root.configure(bg=THEME["bg_window"])

        # Enable High DPI support
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # Center window
        window_width = 620  # Slightly wider for better spacing
        window_height = 750  # Taller for more content
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)

        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.root.minsize(560, 680)

        # Grid weight for responsiveness
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        # Enter to search (when entry focused)
        self.root.bind("<Control-Return>", lambda _: self._on_search())
        # Ctrl+Shift+C to copy ID
        self.root.bind("<Control-Shift-c>", lambda _: self._copy_id())
        # Ctrl+S to save
        self.root.bind("<Control-s>", lambda _: self._on_save())
        # Escape to clear
        self.root.bind("<Escape>", lambda _: self._clear_search())

    def _clear_search(self) -> None:
        """Clear search entry and results."""
        self.search_entry.delete(0, tk.END)
        self.search_entry.focus_set()

    def _create_widgets(self) -> None:
        """Create the entire UI hierarchy."""

        # Main Container (with padding)
        main_container = tk.Frame(self.root, bg=THEME["bg_window"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)

        # 1. Header Card
        self._create_header_card(main_container)

        # 2. Search Card
        self._create_search_card(main_container)

        # 3. Results Card (Expands)
        self._create_results_card(main_container)

        # 4. Footer / Status Bar
        self._create_footer(main_container)

    def _create_header_card(self, parent: tk.Frame) -> None:
        """Top section: Title and Auth Status."""
        header = tk.Frame(parent, bg=THEME["bg_window"])
        header.pack(fill=tk.X, pady=(0, 16))

        # Title Left
        title_frame = tk.Frame(header, bg=THEME["bg_window"])
        title_frame.pack(side=tk.LEFT)

        tk.Label(
            title_frame, text="EQC 快速查询",
            font=FONTS["h1"], fg=THEME["primary"], bg=THEME["bg_window"]
        ).pack(anchor="w")

        tk.Label(
            title_frame, text="企业数据一键检索工具",
            font=FONTS["small"], fg=THEME["text_sub"], bg=THEME["bg_window"]
        ).pack(anchor="w", pady=(2, 0))

        # Auth Button Right
        auth_frame = tk.Frame(header, bg=THEME["bg_window"])
        auth_frame.pack(side=tk.RIGHT, anchor="e")

        self.auth_btn = HoverButton(
            auth_frame, text="扫码登录",
            bg_normal=THEME["secondary"],
            bg_hover=THEME["secondary_hover"],
            bg_active=THEME["secondary_active"],
            font=FONTS["small"], fg=THEME["text_main"],
            relief=tk.FLAT,
            padx=14, pady=5, cursor="hand2",
            command=self._on_authenticate
        )
        self.auth_btn.pack()

        self.auth_status = tk.Label(
            auth_frame, text="未登录",
            font=FONTS["small"], fg=THEME["text_sub"], bg=THEME["bg_window"]
        )
        self.auth_status.pack(pady=(4, 0), anchor="e")

    def _create_search_card(self, parent: tk.Frame) -> None:
        """Middle section: Search inputs."""
        # Card with shadow effect
        card_shadow = tk.Frame(parent, bg=THEME["shadow"])
        card_shadow.pack(fill=tk.X, pady=(0, 16), padx=(2, 2))

        card = tk.Frame(card_shadow, bg=THEME["bg_card"])
        card.config(
            highlightbackground=THEME["border"],
            highlightthickness=1,
            relief=tk.FLAT
        )
        card.pack(fill=tk.X, padx=(0, 2), pady=(0, 2))

        inner = tk.Frame(card, bg=THEME["bg_card"], padx=24, pady=20)
        inner.pack(fill=tk.BOTH)

        # Mode Selection (Radio buttons)
        mode_frame = tk.Frame(inner, bg=THEME["bg_card"])
        mode_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            mode_frame, text="查询方式:",
            font=FONTS["body_bold"], bg=THEME["bg_card"], fg=THEME["text_main"]
        ).pack(side=tk.LEFT)

        modes = [("企业名称", "name"), ("Company ID", "id")]
        for text, val in modes:
            rb = tk.Radiobutton(
                mode_frame, text=text, value=val, variable=self.search_mode,
                font=FONTS["body"], bg=THEME["bg_card"], fg=THEME["text_main"],
                activebackground=THEME["bg_card"], selectcolor=THEME["bg_card"],
                cursor="hand2"
            )
            rb.pack(side=tk.LEFT, padx=(16, 0))

        # Search Bar Row
        search_row = tk.Frame(inner, bg=THEME["bg_card"])
        search_row.pack(fill=tk.X)

        # Entry Box with custom styling
        entry_frame = tk.Frame(search_row, bg=THEME["bg_card"])
        entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        self.search_entry = tk.Entry(
            entry_frame, font=("Microsoft YaHei UI", 11),
            relief=tk.FLAT, bg=THEME["bg_input"], fg=THEME["text_main"]
        )
        self.search_entry.pack(fill=tk.BOTH, ipady=10)

        # Entry border and focus effect
        self.search_entry.config(
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["primary"],
            insertbackground=THEME["primary"]
        )
        self.search_entry.bind("<Return>", lambda _: self._on_search())
        self.search_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_entry_focus_out)

        # Clear Button
        self.clear_btn = HoverButton(
            search_row, text="✕",
            bg_normal=THEME["bg_card"],
            bg_hover=THEME["secondary"],
            font=FONTS["small"], fg=THEME["text_sub"],
            relief=tk.FLAT, cursor="hand2",
            padx=8, pady=4,
            command=self._clear_search
        )
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 12))

        # Search Button
        self.search_btn = HoverButton(
            search_row, text="查询",
            bg_normal=THEME["primary"],
            bg_hover=THEME["primary_hover"],
            bg_active=THEME["primary_active"],
            font=FONTS["body_bold"],
            fg=THEME["text_on_primary"],
            activeforeground="white",
            relief=tk.FLAT, padx=28, pady=8, cursor="hand2",
            command=self._on_search
        )
        self.search_btn.pack(side=tk.RIGHT)

    def _on_entry_focus_in(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        """Highlight entry on focus."""
        self.search_entry.config(highlightbackground=THEME["primary"])

    def _on_entry_focus_out(self, _: tk.Event) -> None:  # type: ignore[type-arg]
        """Remove highlight on focus out."""
        self.search_entry.config(highlightbackground=THEME["border"])

    def _create_results_card(self, parent: tk.Frame) -> None:
        """Bottom section: Results display and Actions."""
        # Card with shadow effect
        card_shadow = tk.Frame(parent, bg=THEME["shadow"])
        card_shadow.pack(fill=tk.BOTH, expand=True, pady=(0, 16), padx=(2, 2))

        card = tk.Frame(card_shadow, bg=THEME["bg_card"])
        card.config(
            highlightbackground=THEME["border"],
            highlightthickness=1,
            relief=tk.FLAT
        )
        card.pack(fill=tk.BOTH, expand=True, padx=(0, 2), pady=(0, 2))

        inner = tk.Frame(card, bg=THEME["bg_card"], padx=24, pady=20)
        inner.pack(fill=tk.BOTH, expand=True)

        # Header of Results
        res_header = tk.Frame(inner, bg=THEME["bg_card"])
        res_header.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            res_header, text="查询结果",
            font=FONTS["h2"], bg=THEME["bg_card"], fg=THEME["text_main"]
        ).pack(side=tk.LEFT)

        # Action Buttons
        self.actions_frame = tk.Frame(res_header, bg=THEME["bg_card"])
        self.actions_frame.pack(side=tk.RIGHT)

        self.copy_id_btn = self._create_action_btn(
            self.actions_frame, "复制ID", self._copy_id
        )
        self.copy_name_btn = self._create_action_btn(
            self.actions_frame, "复制全称", self._copy_name
        )

        self.save_btn = HoverButton(
            self.actions_frame, text="💾 保存到数据库",
            bg_normal=THEME["success"],
            bg_hover=THEME["success_hover"],
            font=FONTS["small"], fg="white",
            activeforeground="white",
            relief=tk.FLAT, padx=12, pady=5, cursor="hand2",
            command=self._on_save, state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.LEFT, padx=(12, 0))

        # Rich Text Display
        self.result_text = tk.Text(
            inner, font=FONTS["body"], bg=THEME["bg_input"], fg=THEME["text_main"],
            relief=tk.FLAT, padx=16, pady=16,
            state=tk.DISABLED, wrap=tk.WORD, height=10,
            highlightthickness=1, highlightbackground=THEME["border"]
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Configure Text Tags
        self.result_text.tag_config(
            "label", font=FONTS["body_bold"], foreground=THEME["text_sub"]
        )
        self.result_text.tag_config(
            "value", font=FONTS["body"], foreground=THEME["text_main"]
        )
        self.result_text.tag_config(
            "highlight", font=FONTS["body_bold"], foreground=THEME["primary"]
        )
        self.result_text.tag_config("success", foreground=THEME["success"])
        self.result_text.tag_config("error", foreground=THEME["error"])

    def _create_action_btn(
        self, parent: tk.Frame, text: str, command: Callable[[], None]
    ) -> HoverButton:
        """Helper to create standard secondary action buttons."""
        btn = HoverButton(
            parent, text=text,
            bg_normal=THEME["secondary"],
            bg_hover=THEME["secondary_hover"],
            bg_active=THEME["secondary_active"],
            font=FONTS["small"],
            fg=THEME["text_main"],
            relief=tk.FLAT, padx=10, pady=5, cursor="hand2",
            command=command, state=tk.DISABLED
        )
        btn.pack(side=tk.LEFT, padx=(0, 6))
        return btn

    def _create_footer(self, parent: tk.Frame) -> None:
        """Bottom status bar."""
        footer = tk.Frame(parent, bg=THEME["bg_window"])
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.budget_label = tk.Label(
            footer, text="API 配额: -- / --",
            font=FONTS["small"], fg=THEME["text_sub"], bg=THEME["bg_window"]
        )
        self.budget_label.pack(side=tk.RIGHT)

        self.status_msg = tk.Label(
            footer, text="就绪 · Enter 搜索 · Ctrl+Shift+C 复制ID · Ctrl+S 保存",
            font=FONTS["small"], fg=THEME["text_placeholder"], bg=THEME["bg_window"]
        )
        self.status_msg.pack(side=tk.LEFT)

    # --- Logic ---

    def _try_auto_login(self) -> None:
        self.auth_status.config(text="验证中...", fg=THEME["warning"])
        self.root.update()

        try:
            if self.controller.try_load_existing_token():
                self._update_auth_ui(True)
                logger.info("Auto-login success")
            else:
                self._update_auth_ui(False)
        except Exception as e:
            logger.error(f"Auto-login failed: {e}")
            self._update_auth_ui(False)

    def _on_authenticate(self) -> None:
        self.auth_btn.config(state=tk.DISABLED, text="Wait...")
        self.status_msg.config(text="请扫描控制台显示的二维码...", fg=THEME["warning"])
        self.root.update()

        try:
            success = self.controller.authenticate()
            self._update_auth_ui(success)
            if success:
                messagebox.showinfo("成功", "登录成功！")
            else:
                messagebox.showwarning("提示", "登录未完成")
        finally:
            self.auth_btn.config(state=tk.NORMAL, text="扫码登录")
            self._reset_status_msg()

    def _update_auth_ui(self, success: bool) -> None:
        if success:
            self.auth_status.config(text="已登录", fg=THEME["success"])
            self.auth_btn.config(text="重新登录")
            self._update_budget()
        else:
            self.auth_status.config(text="未登录", fg=THEME["error"])
            self.budget_label.config(text="API 配额: N/A")

    def _update_budget(self) -> None:
        rem = self.controller.remaining_budget
        tot = self.controller.total_budget
        self.budget_label.config(text=f"API 配额: {rem} / {tot}")

    def _reset_status_msg(self) -> None:
        """Reset status message to default."""
        self.status_msg.config(
            text="就绪 · Enter 搜索 · Ctrl+Shift+C 复制ID · Ctrl+S 保存",
            fg=THEME["text_placeholder"]
        )

    def _on_search(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            self._show_error("请输入查询内容")
            return

        if not self.controller.is_authenticated:
            self._show_error("请先登录")
            return

        # UI Busy State
        self.search_btn.config(state=tk.DISABLED, text="...")
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "正在查询...", "value")
        self.result_text.config(state=tk.DISABLED)
        self.root.update()

        try:
            mode = self.search_mode.get()
            if mode == "id":
                result = self.controller.lookup_by_id(query)
            else:
                result = self.controller.lookup(query)

            self._display_result(result)
            self._update_budget()

        except Exception as e:
            self._show_error(str(e))
        finally:
            self.search_btn.config(state=tk.NORMAL, text="查询")

    def _display_result(self, result: QueryResult) -> None:
        self.current_result = result
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)

        if result.success:
            # Render Success
            self._append_kv("状态", "✓ 查询成功", "success")
            self._append_text("\n")
            self._append_kv("公司全称", result.official_name, "value")
            self._append_kv("Company ID", result.company_id, "highlight")
            self._append_kv("统一信用代码", result.unified_credit_code, "value")

            if result.confidence:
                self._append_kv("置信度", f"{result.confidence:.2f}", "value")

            self._append_kv("匹配类型", result.match_type, "value")

            # Enable Actions
            self.copy_id_btn.config(state=tk.NORMAL)
            self.copy_name_btn.config(state=tk.NORMAL)

            if self.controller.can_save:
                self.save_btn.config(
                    state=tk.NORMAL,
                    bg=THEME["success"],
                    text="💾 保存到数据库"
                )
                self.save_btn.bg_normal = THEME["success"]
                self.save_btn.bg_hover = THEME["success_hover"]
            else:
                self.save_btn.config(state=tk.DISABLED, text="⚠️ DB未连接")

        else:
            # Render Error
            self.result_text.insert(tk.END, f"❌ {result.error_message}", "error")
            self._disable_actions()

        self.result_text.config(state=tk.DISABLED)

    def _append_kv(self, key: str, value: str | None, tag: str) -> None:
        self.result_text.insert(tk.END, f"{key}: ", "label")
        self.result_text.insert(tk.END, f"{value or 'N/A'}\n", tag)

    def _append_text(self, text: str, tag: str = "value") -> None:
        self.result_text.insert(tk.END, text, tag)

    def _disable_actions(self) -> None:
        self.copy_id_btn.config(state=tk.DISABLED)
        self.copy_name_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)

    def _show_error(self, msg: str) -> None:
        messagebox.showerror("错误", msg)

    def _copy_id(self) -> None:
        if self.current_result and self.current_result.company_id:
            pyperclip.copy(self.current_result.company_id)
            self.status_msg.config(text="✓ 已复制 Company ID!", fg=THEME["success"])
            self.root.after(2500, self._reset_status_msg)

    def _copy_name(self) -> None:
        if self.current_result and self.current_result.official_name:
            pyperclip.copy(self.current_result.official_name)
            self.status_msg.config(text="✓ 已复制企业全称!", fg=THEME["success"])
            self.root.after(2500, self._reset_status_msg)

    def _on_save(self) -> None:
        if not self.current_result:
            return

        self.save_btn.config(state=tk.DISABLED, text="保存中...")
        self.root.update()

        if self.controller.save_last_result():
            self.save_btn.config(text="✅ 已保存")
            self.save_btn.bg_normal = THEME["secondary"]
            self.save_btn.config(bg=THEME["secondary"], fg=THEME["success"])
            self.status_msg.config(text="✓ 数据已保存至 Base Info", fg=THEME["success"])
            self.root.after(2500, self._reset_status_msg)
        else:
            self.save_btn.config(state=tk.NORMAL, text="💾 保存失败")
            messagebox.showerror("失败", "保存失败，请查看日志")

    def _on_close(self) -> None:
        self.controller.close()
        self.root.destroy()


def launch_gui() -> None:
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = EqcQueryApp(root)  # noqa: F841
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
