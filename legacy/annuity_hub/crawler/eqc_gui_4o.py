# eqc_gui.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from crawler.eqc_crawler import EqcCrawler


class EqcGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EQC Company Info Scraper")
        self.setGeometry(100, 100, 800, 600)

        # Initialize EQC Crawler
        self.crawler = EqcCrawler(token="fbaf2a0ae6effda674cf09e8921453c3")

        # Main Widget and Layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout()
        main_widget.setLayout(self.layout)

        # Input Section
        self.create_input_section()

        # Table Section
        self.create_table_section()

        # Apply Stylesheet
        self.apply_styles()

    def create_input_section(self):
        input_layout = QHBoxLayout()

        # Keyword Input
        self.keyword_input = QLineEdit(self)
        self.keyword_input.setPlaceholderText("Enter Keyword or Company ID")
        input_layout.addWidget(QLabel("Keyword/ID:"))
        input_layout.addWidget(self.keyword_input)

        # Search Button
        search_button = QPushButton("Search", self)
        search_button.clicked.connect(self.on_search_clicked)
        input_layout.addWidget(search_button)

        self.layout.addLayout(input_layout)

    def create_table_section(self):
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Company ID", "Name", "Unite Code", "Former Name"])
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.table)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QLabel, QLineEdit, QPushButton, QTableWidget {
                color: #ffffff;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #444444;
                border: 1px solid #555555;
                padding: 5px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QLineEdit {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 5px;
            }
            QTableWidget {
                background-color: #3b3b3b;
                border: 1px solid #555555;
            }
        """)

    def on_search_clicked(self):
        keyword = self.keyword_input.text().strip()
        if not keyword:
            self.show_message("Please enter a keyword or company ID.")
            return

        # Fetch Data
        try:
            base_info, _, _ = self.crawler.scrape_data(keyword, is_id=keyword.isdigit())
            if not base_info:
                self.show_message("No data found.")
                return

            # Populate Table
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem(base_info.get("companyId", "")))
            self.table.setItem(0, 1, QTableWidgetItem(base_info.get("companyFullName", "")))
            self.table.setItem(0, 2, QTableWidgetItem(base_info.get("unite_code", "")))
            self.table.setItem(0, 3, QTableWidgetItem(base_info.get("formerName", "")))
        except Exception as e:
            self.show_message(f"Error occurred: {e}")

    def show_message(self, message):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Warning", message, QMessageBox.Ok)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EqcGUI()
    window.show()
    sys.exit(app.exec_())
