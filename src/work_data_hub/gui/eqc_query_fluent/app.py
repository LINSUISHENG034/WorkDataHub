"""
EQC Query GUI - Fluent Version Main Application.

Modern GUI using PyQt-Fluent-Widgets with dark/light theme support.
"""

import sys
from typing import Optional

import pyperclip  # type: ignore[import-untyped]
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    MessageBox,
    PushButton,
    Theme,
    TitleLabel,
    isDarkTheme,
    setTheme,
    setThemeColor,
)

from work_data_hub.gui.eqc_query.controller import EqcQueryController, QueryResult
from work_data_hub.gui.eqc_query_fluent.components import (
    ResultsCard,
    SearchCard,
    StatusFooter,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

# Ping An Orange theme color
THEME_COLOR = "#FF6400"

# Light mode text colors (higher contrast)
LIGHT_MODE_TEXT = "#1F2329"
LIGHT_MODE_SUBTEXT = "#4A4D52"


class EqcFluentApp(QMainWindow):
    """
    EQC Query Fluent GUI Application.

    Features:
    - Microsoft Fluent Design with dark/light theme
    - Card-based layout
    - Keyboard shortcuts
    - Smooth animations
    """

    def __init__(self) -> None:
        super().__init__()
        self.controller = EqcQueryController()
        self.current_result: Optional[QueryResult] = None

        self._setup_window()
        self._create_widgets()
        self._bind_shortcuts()

        # Auto-login after window shows
        QTimer.singleShot(100, self._try_auto_login)

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("EQC 快速查询 - Fluent")
        self.resize(680, 780)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = (geometry.width() - 680) // 2
            y = (geometry.height() - 780) // 2
            self.move(x, y)

        self.setMinimumSize(600, 700)

        # Apply Fluent theme color
        setThemeColor(THEME_COLOR)

    def _create_widgets(self) -> None:
        """Create the main UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(20)

        # Header
        header = self._create_header()
        layout.addLayout(header)

        # Search Card
        self.search_card = SearchCard(on_search=self._on_search)
        layout.addWidget(self.search_card)

        # Results Card (expandable)
        self.results_card = ResultsCard(
            on_copy_id=self._copy_id,
            on_copy_name=self._copy_name,
            on_save=self._on_save
        )
        layout.addWidget(self.results_card, 1)

        # Status Footer
        self.status_footer = StatusFooter()
        layout.addWidget(self.status_footer)

    def _create_header(self) -> QHBoxLayout:
        """Create header with title and auth button."""
        layout = QHBoxLayout()

        # Title section
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title = TitleLabel("EQC 快速查询")
        title.setStyleSheet(f"color: {THEME_COLOR};")

        subtitle = CaptionLabel("企业数据一键检索工具")
        # Ensure readable in light mode
        if not isDarkTheme():
            subtitle.setStyleSheet(f"color: {LIGHT_MODE_SUBTEXT};")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Auth section
        auth_layout = QVBoxLayout()
        auth_layout.setSpacing(4)
        auth_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.auth_btn = PushButton("扫码登录")
        self.auth_btn.clicked.connect(self._on_authenticate)

        self.auth_status = CaptionLabel("未登录")
        self.auth_status.setAlignment(Qt.AlignmentFlag.AlignRight)

        auth_layout.addWidget(self.auth_btn, 0, Qt.AlignmentFlag.AlignRight)
        auth_layout.addWidget(self.auth_status, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(auth_layout)

        return layout

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        # Ctrl+Shift+C to copy ID
        copy_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        copy_shortcut.activated.connect(self._copy_id)

        # Ctrl+S to save
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._on_save)

        # Escape to clear
        clear_shortcut = QShortcut(QKeySequence("Escape"), self)
        clear_shortcut.activated.connect(self.search_card.clear)

        # Ctrl+D to toggle dark mode
        theme_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        theme_shortcut.activated.connect(self._toggle_theme)

    def _toggle_theme(self) -> None:
        """Toggle between dark and light theme."""
        if isDarkTheme():
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

    # --- Auth Logic ---

    def _try_auto_login(self) -> None:
        """Try to load existing token."""
        self.auth_status.setText("验证中...")
        self.auth_status.setStyleSheet("color: #FAAD14;")

        try:
            if self.controller.try_load_existing_token():
                self._update_auth_ui(True)
                logger.info("Fluent GUI: Auto-login success")
            else:
                self._update_auth_ui(False)
        except Exception as e:
            logger.error(f"Fluent GUI: Auto-login failed: {e}")
            self._update_auth_ui(False)

    def _on_authenticate(self) -> None:
        """Handle auth button click."""
        self.auth_btn.setEnabled(False)
        self.auth_btn.setText("Wait...")
        self.status_footer.set_status("请扫描控制台显示的二维码...", "#FAAD14")

        try:
            success = self.controller.authenticate()
            self._update_auth_ui(success)
            if success:
                MessageBox("成功", "登录成功！", self).exec()
            else:
                MessageBox("提示", "登录未完成", self).exec()
        finally:
            self.auth_btn.setEnabled(True)
            self.auth_btn.setText("扫码登录")
            self.status_footer.reset_status()

    def _update_auth_ui(self, success: bool) -> None:
        """Update auth status display."""
        if success:
            self.auth_status.setText("已登录")
            self.auth_status.setStyleSheet("color: #52C41A;")
            self.auth_btn.setText("重新登录")
            self._update_budget()
        else:
            self.auth_status.setText("未登录")
            self.auth_status.setStyleSheet("color: #F5222D;")
            self.status_footer.set_budget_na()

    def _update_budget(self) -> None:
        """Update API budget display."""
        self.status_footer.set_budget(
            self.controller.remaining_budget,
            self.controller.total_budget
        )

    # --- Search Logic ---

    def _on_search(self, query: str, mode: str) -> None:
        """Handle search action."""
        if not query:
            MessageBox("错误", "请输入查询内容", self).exec()
            return

        if not self.controller.is_authenticated:
            MessageBox("错误", "请先登录", self).exec()
            return

        # Busy state
        self.search_card.set_busy(True)
        self.results_card.show_loading()

        try:
            if mode == "id":
                result = self.controller.lookup_by_id(query)
            else:
                result = self.controller.lookup(query)

            self._display_result(result)
            self._update_budget()
        except Exception as e:
            self.results_card.show_error(str(e))
        finally:
            self.search_card.set_busy(False)

    def _display_result(self, result: QueryResult) -> None:
        """Display query result."""
        self.current_result = result

        if result.success:
            self.results_card.show_result(
                official_name=result.official_name,
                company_id=result.company_id,
                unified_credit_code=result.unified_credit_code,
                confidence=result.confidence,
                match_type=result.match_type,
                can_save=self.controller.can_save
            )
        else:
            self.results_card.show_error(result.error_message or "未知错误")

    # --- Action Logic ---

    def _copy_id(self) -> None:
        """Copy company ID to clipboard."""
        if self.current_result and self.current_result.company_id:
            pyperclip.copy(self.current_result.company_id)
            self.status_footer.set_status("✓ 已复制 Company ID!", "#52C41A")
            QTimer.singleShot(2500, self.status_footer.reset_status)

    def _copy_name(self) -> None:
        """Copy company name to clipboard."""
        if self.current_result and self.current_result.official_name:
            pyperclip.copy(self.current_result.official_name)
            self.status_footer.set_status("✓ 已复制企业全称!", "#52C41A")
            QTimer.singleShot(2500, self.status_footer.reset_status)

    def _on_save(self) -> None:
        """Save result to database."""
        if not self.current_result:
            return

        self.results_card.save_btn.setEnabled(False)
        self.results_card.save_btn.setText("保存中...")

        if self.controller.save_last_result():
            self.results_card.set_save_success()
            self.status_footer.set_status("✓ 数据已保存至 Base Info", "#52C41A")
            QTimer.singleShot(2500, self.status_footer.reset_status)
        else:
            self.results_card.set_save_failed()
            MessageBox("失败", "保存失败，请查看日志", self).exec()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Clean up on close."""
        self.controller.close()
        super().closeEvent(event)


def launch_gui() -> None:
    """Launch the Fluent GUI application."""
    # Enable High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Set default theme to DARK (better readability)
    setTheme(Theme.DARK)

    window = EqcFluentApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
