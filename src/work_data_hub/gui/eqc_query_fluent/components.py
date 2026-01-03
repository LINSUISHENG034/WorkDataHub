"""
EQC Query Fluent GUI - Reusable Components.

Card-based components built with PyQt-Fluent-Widgets.
"""

from typing import Callable

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CardWidget,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    SearchLineEdit,
    StrongBodyLabel,
    SubtitleLabel,
    TextEdit,
)


class SearchCard(CardWidget):
    """Search input card with mode selection."""

    def __init__(
        self,
        on_search: Callable[[str, str], None],
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_search = on_search
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(0)

        mode_label = StrongBodyLabel("查询方式:")
        mode_layout.addWidget(mode_label)
        mode_layout.addSpacing(16)

        self.name_radio = RadioButton("企业名称")
        self.name_radio.setChecked(True)
        self.id_radio = RadioButton("Company ID")

        mode_layout.addWidget(self.name_radio)
        mode_layout.addSpacing(16)
        mode_layout.addWidget(self.id_radio)
        mode_layout.addStretch()

        layout.addLayout(mode_layout)

        # Search row
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)

        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("输入企业名称或 Company ID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._do_search)

        self.search_btn = PrimaryPushButton("查询")
        self.search_btn.setFixedWidth(100)
        self.search_btn.clicked.connect(self._do_search)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_btn)

        layout.addLayout(search_layout)

    def _do_search(self) -> None:
        query = self.search_input.text().strip()
        mode = "id" if self.id_radio.isChecked() else "name"
        self._on_search(query, mode)

    def get_query(self) -> str:
        return self.search_input.text().strip()

    def set_busy(self, busy: bool) -> None:
        self.search_btn.setEnabled(not busy)
        self.search_btn.setText("..." if busy else "查询")

    def clear(self) -> None:
        self.search_input.clear()
        self.search_input.setFocus()


class ResultsCard(CardWidget):
    """Results display card with action buttons."""

    def __init__(
        self,
        on_copy_id: Callable[[], None],
        on_copy_name: Callable[[], None],
        on_save: Callable[[], None],
        parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_copy_id = on_copy_id
        self._on_copy_name = on_copy_name
        self._on_save = on_save
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header with actions
        header_layout = QHBoxLayout()

        title = SubtitleLabel("查询结果")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.copy_id_btn = PushButton("复制ID")
        self.copy_id_btn.setEnabled(False)
        self.copy_id_btn.clicked.connect(self._on_copy_id)

        self.copy_name_btn = PushButton("复制全称")
        self.copy_name_btn.setEnabled(False)
        self.copy_name_btn.clicked.connect(self._on_copy_name)

        self.save_btn = PrimaryPushButton("💾 保存到数据库")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)

        header_layout.addWidget(self.copy_id_btn)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.copy_name_btn)
        header_layout.addSpacing(12)
        header_layout.addWidget(self.save_btn)

        layout.addLayout(header_layout)

        # Results display
        self.result_display = TextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setPlaceholderText("查询结果将显示在这里...")

        layout.addWidget(self.result_display, 1)

    def show_loading(self) -> None:
        self.result_display.setPlainText("正在查询...")
        self._disable_actions()

    def show_result(
        self,
        official_name: str | None,
        company_id: str | None,
        unified_credit_code: str | None,
        confidence: float | None,
        match_type: str | None,
        can_save: bool
    ) -> None:
        lines = [
            "状态: ✓ 查询成功",
            "",
            f"公司全称: {official_name or 'N/A'}",
            f"Company ID: {company_id or 'N/A'}",
            f"统一信用代码: {unified_credit_code or 'N/A'}",
        ]
        if confidence:
            lines.append(f"置信度: {confidence:.2f}")
        lines.append(f"匹配类型: {match_type or 'N/A'}")

        self.result_display.setPlainText("\n".join(lines))

        self.copy_id_btn.setEnabled(bool(company_id))
        self.copy_name_btn.setEnabled(bool(official_name))
        self.save_btn.setEnabled(can_save)

    def show_error(self, message: str) -> None:
        self.result_display.setPlainText(f"❌ {message}")
        self._disable_actions()

    def _disable_actions(self) -> None:
        self.copy_id_btn.setEnabled(False)
        self.copy_name_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

    def set_save_success(self) -> None:
        self.save_btn.setText("✅ 已保存")
        self.save_btn.setEnabled(False)

    def set_save_failed(self) -> None:
        self.save_btn.setText("💾 保存失败")
        self.save_btn.setEnabled(True)


class StatusFooter(QFrame):
    """Status bar with message and budget display."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.status_label = BodyLabel(
            "就绪 · Enter 搜索 · Ctrl+Shift+C 复制ID · Ctrl+S 保存"
        )
        self.status_label.setStyleSheet("color: #606266;")

        self.budget_label = BodyLabel("API 配额: -- / --")
        self.budget_label.setStyleSheet("color: #303133;")

        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.budget_label)

    def set_status(self, text: str, color: str = "#909399") -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def reset_status(self) -> None:
        self.status_label.setText(
            "就绪 · Enter 搜索 · Ctrl+Shift+C 复制ID · Ctrl+S 保存"
        )
        self.status_label.setStyleSheet("color: #606266;")

    def set_budget(self, remaining: int, total: int) -> None:
        self.budget_label.setText(f"API 配额: {remaining} / {total}")

    def set_budget_na(self) -> None:
        self.budget_label.setText("API 配额: N/A")
