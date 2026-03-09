"""
Tkinter GUI for intranet deployment packaging and assembly.
"""

from __future__ import annotations

import multiprocessing
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from typing import Any, Literal, cast

from work_data_hub.gui.eqc_query.app import FONTS, THEME, HoverButton
from work_data_hub.gui.intranet_deploy.controller import IntranetDeployController
from work_data_hub.gui.intranet_deploy.service import (
    DEFAULT_SKIP_FILES,
    AssembleResult,
    DeploymentBundleError,
    PackageResult,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

PACKAGE_COMPONENT_LABELS = {
    "repo-root": "仓库代码主体",
    "vendor": "离线依赖包",
    "config-seeds": "种子配置数据",
    "data-backups": "数据备份文件",
}

SKIP_FILE_LABELS = {
    "config/data_sources.yml": "保留数据源配置",
    ".wdh_env": "保留本地环境变量",
}


def _font(style: str) -> Any:
    """Return a tkinter-compatible font descriptor."""

    return FONTS[style]


class IntranetDeployApp:
    """Card-based deployment utility for intranet bundle workflows."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = IntranetDeployController()
        self._event_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._busy = False

        self.package_output_dir = tk.StringVar(
            value=str(self.controller.project_root / "dist")
        )
        self.package_bundle_dir = tk.StringVar()
        self.target_base_dir = tk.StringVar()
        self.status_text = tk.StringVar(value="就绪")

        self.skip_file_vars = {
            item: tk.BooleanVar(value=True) for item in DEFAULT_SKIP_FILES
        }
        self.package_component_vars = {
            name: tk.BooleanVar(value=True)
            for name in self.controller.package_components
        }

        self._setup_window()
        self._create_widgets()
        self._bind_shortcuts()
        self._poll_worker_events()

    def _setup_window(self) -> None:
        """Configure the main window."""

        self.root.title("内网部署打包工具")
        self.root.configure(bg=THEME["bg_window"])

        try:
            from ctypes import windll

            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        window_width = 820
        window_height = 950
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)

        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.root.minsize(760, 850)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _create_widgets(self) -> None:
        """Build the UI layout."""

        main_container = tk.Frame(self.root, bg=THEME["bg_window"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=28, pady=28)

        self._create_header_card(main_container)
        self._create_package_card(main_container)
        self._create_assemble_card(main_container)
        self._create_log_card(main_container)
        self._create_footer(main_container)

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""

        self.root.bind("<Control-p>", lambda _: self._on_package())
        self.root.bind("<Control-o>", lambda _: self._browse_package_bundle_dir())
        self.root.bind("<Control-r>", lambda _: self._on_assemble())

    def _create_header_card(self, parent: tk.Frame) -> None:
        """Top header with title and environment info."""

        header = tk.Frame(parent, bg=THEME["bg_window"])
        header.pack(fill=tk.X, pady=(0, 20))

        title_frame = tk.Frame(header, bg=THEME["bg_window"])
        title_frame.pack(side=tk.LEFT)

        tk.Label(
            title_frame,
            text="内网部署打包工具",
            font=_font("h1"),
            fg=THEME["primary"],
            bg=THEME["bg_window"],
        ).pack(anchor="w")
        tk.Label(
            title_frame,
            text="远端仓库打包、.7z 传输、目标目录组装一体化处理",
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_window"],
        ).pack(anchor="w", pady=(4, 0))

        info_frame = tk.Frame(header, bg=THEME["bg_window"])
        info_frame.pack(side=tk.RIGHT, anchor="e")

        tk.Label(
            info_frame,
            text="7-Zip",
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_window"],
        ).pack(anchor="e")
        tk.Label(
            info_frame,
            text=self.controller.seven_zip_executable,
            font=_font("small"),
            fg=THEME["text_main"],
            bg=THEME["bg_window"],
            wraplength=260,
            justify=tk.RIGHT,
        ).pack(anchor="e")

    def _create_package_card(self, parent: tk.Frame) -> None:
        """Package creation card."""

        card = self._create_card(parent, "1. 打包 .7z")
        inner = card["inner"]

        self._create_path_row(
            inner,
            label="输出目录",
            variable=self.package_output_dir,
            browse_command=self._browse_package_output_dir,
            button_text="选择文件夹",
        )

        tips = (
            "打包内容可按需勾选，默认全选：远端上游分支主体代码、vendor/、"
            "config/seeds/、data/backups/。\n"
            "每个组件会生成独立 .7z，文件名自动包含组件名、时间戳和提交短 SHA。"
        )
        tk.Label(
            inner,
            text=tips,
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_card"],
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(10, 0))

        component_frame = tk.Frame(inner, bg=THEME["bg_card"])
        component_frame.pack(fill=tk.X, pady=(16, 0))

        tk.Label(
            component_frame,
            text="打包内容选择",
            font=_font("body_bold"),
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
        ).pack(anchor="w")

        self._create_checkbox_grid(
            parent=component_frame,
            options=[
                (
                    PACKAGE_COMPONENT_LABELS.get(component_name, component_name),
                    variable,
                )
                for component_name, variable in self.package_component_vars.items()
            ],
            columns=2,
        )

        self.package_btn = HoverButton(
            inner,
            text="开始打包",
            bg_normal=THEME["primary"],
            bg_hover=THEME["primary_hover"],
            bg_active=THEME["primary_active"],
            font=_font("body_bold"),
            fg=THEME["text_on_primary"],
            activeforeground="white",
            relief=tk.FLAT,
            width=12,
            cursor="hand2",
            command=self._on_package,
        )
        self.package_btn.pack(anchor="e", pady=(20, 0))

    def _create_assemble_card(self, parent: tk.Frame) -> None:
        """Package assembly card."""

        card = self._create_card(parent, "2. 解压并组装")
        inner = card["inner"]

        self._create_path_row(
            inner,
            label="压缩包目录",
            variable=self.package_bundle_dir,
            browse_command=self._browse_package_bundle_dir,
            button_text="选择目录",
        )
        self._create_path_row(
            inner,
            label="目标目录",
            variable=self.target_base_dir,
            browse_command=self._browse_target_base_dir,
            button_text="选择文件夹",
        )

        skip_frame = tk.Frame(inner, bg=THEME["bg_card"])
        skip_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            skip_frame,
            text="默认跳过覆盖",
            font=_font("body_bold"),
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
        ).pack(anchor="w")

        self._create_checkbox_grid(
            parent=skip_frame,
            options=[
                (SKIP_FILE_LABELS.get(relative_path, relative_path), variable)
                for relative_path, variable in self.skip_file_vars.items()
            ],
            columns=2,
        )

        tk.Label(
            inner,
            text=(
                "若目标目录下已存在同名项目目录，默认会覆盖写入。"
                " 仅勾选项会在目标文件已存在时保留用户本地版本。"
            ),
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_card"],
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(10, 0))

        self.assemble_btn = HoverButton(
            inner,
            text="开始组装",
            bg_normal=THEME["success"],
            bg_hover=THEME["success_hover"],
            font=_font("body_bold"),
            fg="white",
            activeforeground="white",
            relief=tk.FLAT,
            width=12,
            cursor="hand2",
            command=self._on_assemble,
        )
        self.assemble_btn.pack(anchor="e", pady=(20, 0))

    def _create_log_card(self, parent: tk.Frame) -> None:
        """Log output card."""

        card = self._create_card(parent, "3. 执行日志", expand=True)
        inner = card["inner"]

        self.log_text = scrolledtext.ScrolledText(
            inner,
            font=_font("body"),
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            relief=tk.FLAT,
            height=14,
            wrap=tk.WORD,
            padx=14,
            pady=14,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)
        self._append_log("工具已就绪。")

    def _create_footer(self, parent: tk.Frame) -> None:
        """Footer status bar."""

        footer = tk.Frame(parent, bg=THEME["bg_window"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))

        tk.Label(
            footer,
            textvariable=self.status_text,
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_window"],
        ).pack(side=tk.LEFT)

        tk.Label(
            footer,
            text=f"项目根目录: {self.controller.project_root}",
            font=_font("small"),
            fg=THEME["text_sub"],
            bg=THEME["bg_window"],
        ).pack(side=tk.RIGHT)

    def _create_card(
        self,
        parent: tk.Frame,
        title: str,
        expand: bool = False,
    ) -> dict[str, tk.Frame]:
        """Create a standard card with shadow and inner container."""

        shadow = tk.Frame(parent, bg=THEME["shadow"])
        shadow.pack(
            fill=tk.BOTH if expand else tk.X,
            expand=expand,
            pady=(0, 18),
            padx=(3, 3),
        )

        card = tk.Frame(shadow, bg=THEME["bg_card"])
        card.config(
            highlightbackground=THEME["border"],
            highlightthickness=1,
            relief=tk.FLAT,
        )
        card.pack(fill=tk.BOTH, expand=expand, padx=(0, 3), pady=(0, 3))

        inner = tk.Frame(card, bg=THEME["bg_card"], padx=28, pady=24)
        inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            inner,
            text=title,
            font=_font("h2"),
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
        ).pack(anchor="w", pady=(0, 4))

        return {"card": card, "inner": inner}

    def _create_path_row(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        button_text: str,
    ) -> None:
        """Create a labeled path input row."""

        row = tk.Frame(parent, bg=THEME["bg_card"])
        row.pack(fill=tk.X, pady=(14, 0))

        tk.Label(
            row,
            text=label,
            width=12,
            anchor="w",
            font=_font("body_bold"),
            fg=THEME["text_main"],
            bg=THEME["bg_card"],
        ).pack(side=tk.LEFT)

        entry = tk.Entry(
            row,
            textvariable=variable,
            font=("Microsoft YaHei UI", 10),
            relief=tk.FLAT,
            bg=THEME["bg_input"],
            fg=THEME["text_main"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["primary"],
            insertbackground=THEME["primary"],
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), ipady=10)

        button = HoverButton(
            row,
            text=button_text,
            bg_normal=THEME["secondary"],
            bg_hover=THEME["secondary_hover"],
            bg_active=THEME["secondary_active"],
            font=_font("small"),
            fg=THEME["text_main"],
            relief=tk.FLAT,
            width=12,
            cursor="hand2",
            command=browse_command,
        )
        button.pack(side=tk.RIGHT)

    def _create_checkbox_grid(
        self,
        parent: tk.Frame,
        options: list[tuple[str, tk.BooleanVar]],
        columns: int,
    ) -> None:
        """Render compact checkbox rows using a fixed-width grid."""

        grid_frame = tk.Frame(parent, bg=THEME["bg_card"])
        grid_frame.pack(fill=tk.X, pady=(10, 0))

        for column in range(columns):
            grid_frame.columnconfigure(column, weight=1)

        for index, (label, variable) in enumerate(options):
            row = index // columns
            column = index % columns
            checkbox = tk.Checkbutton(
                grid_frame,
                text=label,
                variable=variable,
                font=_font("body"),
                bg=THEME["bg_card"],
                fg=THEME["text_main"],
                activebackground=THEME["bg_card"],
                selectcolor=THEME["bg_card"],
                anchor="w",
                justify=tk.LEFT,
                padx=0,
            )
            checkbox.grid(
                row=row,
                column=column,
                sticky="w",
                padx=(0, 20),
                pady=(0, 8),
            )

    def _browse_package_output_dir(self) -> None:
        """Choose the package output directory."""

        selected = filedialog.askdirectory(
            title="选择 .7z 输出目录",
            initialdir=(
                self.package_output_dir.get() or str(self.controller.project_root)
            ),
        )
        if selected:
            self.package_output_dir.set(selected)

    def _browse_package_bundle_dir(self) -> None:
        """Choose the directory containing component archives."""

        selected = filedialog.askdirectory(
            title="选择组件压缩包目录",
            initialdir=(
                self.package_bundle_dir.get()
                or self.package_output_dir.get()
                or str(self.controller.project_root)
            ),
        )
        if selected:
            self.package_bundle_dir.set(selected)

    def _browse_target_base_dir(self) -> None:
        """Choose the target base directory."""

        selected = filedialog.askdirectory(
            title="选择组装目标目录",
            initialdir=(
                self.target_base_dir.get() or str(self.controller.project_root)
            ),
        )
        if selected:
            self.target_base_dir.set(selected)

    def _on_package(self) -> None:
        """Start package creation in a worker thread."""

        output_dir_text = self.package_output_dir.get().strip()
        if not output_dir_text:
            messagebox.showerror("缺少目录", "请选择压缩包输出目录。")
            return
        selected_components = [
            component_name
            for component_name, enabled in self.package_component_vars.items()
            if enabled.get()
        ]
        if not selected_components:
            messagebox.showerror("缺少内容", "请至少勾选一个需要打包的内容。")
            return

        output_dir = Path(output_dir_text)
        self._run_in_background(
            label="打包中",
            target=lambda: self.controller.create_package(
                output_dir=output_dir,
                component_names=selected_components,
                progress=self._queue_progress,
            ),
            success_handler=self._handle_package_success,
        )

    def _on_assemble(self) -> None:
        """Start bundle assembly in a worker thread."""

        package_dir_text = self.package_bundle_dir.get().strip()
        target_text = self.target_base_dir.get().strip()
        if not package_dir_text:
            messagebox.showerror("缺少压缩包目录", "请选择包含组件 .7z 的目录。")
            return
        if not target_text:
            messagebox.showerror("缺少目标目录", "请选择组装目标目录。")
            return

        skip_files = [
            relative_path
            for relative_path, enabled in self.skip_file_vars.items()
            if enabled.get()
        ]
        package_dir = Path(package_dir_text)
        target_base_dir = Path(target_text)

        self._run_in_background(
            label="组装中",
            target=lambda: self.controller.assemble_package(
                package_dir=package_dir,
                target_base_dir=target_base_dir,
                skip_files=skip_files,
                progress=self._queue_progress,
            ),
            success_handler=self._handle_assemble_success,
        )

    def _run_in_background(
        self,
        label: str,
        target: Callable[[], object],
        success_handler: Callable[[object], None],
    ) -> None:
        """Run a long-running task in a background thread."""

        if self._busy:
            return

        self._set_busy(True, label)

        def worker() -> None:
            try:
                result = target()
            except Exception as exc:  # noqa: BLE001
                logger.exception("intranet_bundle.gui_worker_failed")
                self._event_queue.put(("error", exc))
            else:
                self._event_queue.put(("success", (success_handler, result)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_worker_events(self) -> None:
        """Process messages from background workers."""

        try:
            while True:
                event_type, payload = self._event_queue.get_nowait()
                if event_type == "progress":
                    self._append_log(str(payload))
                    self.status_text.set(str(payload))
                elif event_type == "error":
                    self._handle_worker_error(payload)
                elif event_type == "success":
                    success_handler, result = cast(
                        tuple[Callable[[object], None], object],
                        payload,
                    )
                    self._set_busy(False, "就绪")
                    success_handler(result)
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_worker_events)

    def _queue_progress(self, message: str) -> None:
        """Queue a progress message from the worker."""

        self._event_queue.put(("progress", message))

    def _handle_package_success(self, result: object) -> None:
        """Update UI after a successful package build."""

        package_result = result if isinstance(result, PackageResult) else None
        if package_result is None:
            raise DeploymentBundleError("打包结果类型无效。")

        summary = (
            f"打包完成，共生成 {len(package_result.archives)} 个压缩包。\n"
            f"远端引用: {package_result.git_ref}\n"
            f"提交: {package_result.git_commit}"
        )
        for archive in package_result.archives:
            self._append_log(f"[{archive.component_name}] {archive.archive_path}")
        self._append_log(summary)
        if package_result.archives:
            self.package_bundle_dir.set(
                str(package_result.archives[0].archive_path.parent)
            )
        self.status_text.set("打包完成")
        messagebox.showinfo("打包完成", summary)

    def _handle_assemble_success(self, result: object) -> None:
        """Update UI after successful assembly."""

        assemble_result = result if isinstance(result, AssembleResult) else None
        if assemble_result is None:
            raise DeploymentBundleError("组装结果类型无效。")

        skipped = "、".join(assemble_result.skipped_files)
        skipped = skipped if skipped else "无"
        summary = (
            f"组装完成: {assemble_result.project_dir}\n"
            f"新增文件: {assemble_result.copied_files}\n"
            f"覆盖文件: {assemble_result.overwritten_files}\n"
            f"跳过文件: {skipped}\n"
            f"处理组件: {', '.join(assemble_result.processed_components)}"
        )
        self._append_log(summary)
        self.status_text.set("组装完成")
        messagebox.showinfo("组装完成", summary)

    def _handle_worker_error(self, payload: object) -> None:
        """Render worker exceptions in the UI."""

        self._set_busy(False, "执行失败")
        message = str(payload)
        self._append_log(f"失败: {message}")
        messagebox.showerror("执行失败", message)

    def _append_log(self, message: str) -> None:
        """Append a line to the log text area."""

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool, status: str) -> None:
        """Toggle busy state and button availability."""

        self._busy = busy
        self.status_text.set(status)
        state: Literal["disabled", "normal"] = tk.DISABLED if busy else tk.NORMAL
        self.package_btn.config(state=state)
        self.assemble_btn.config(state=state)


def launch_gui() -> None:
    """Launch the intranet deployment GUI."""

    multiprocessing.freeze_support()
    root = tk.Tk()
    try:
        IntranetDeployApp(root)
    except DeploymentBundleError as exc:
        root.withdraw()
        messagebox.showerror("启动失败", str(exc))
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
