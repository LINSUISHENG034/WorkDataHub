# /gui/eqc_gui.py
import tkinter as tk
from tkinter import messagebox, ttk
from eqc_crawler import EqcCrawler


class EqcGUI:
    def __init__(self, root, token):
        self.root = root
        self.token = token
        self.crawler = EqcCrawler(token)
        self.root.title("公司信息查询工具")
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=("Helvetica", 12))
        self.style.configure("TButton", background="#007bff", foreground="white", font=("Helvetica", 12), padding=10)
        self.style.map("TButton", background=[("active", "#0056b3")])

        self.create_widgets()

    def create_widgets(self):
        # 主框架
        frame = ttk.Frame(self.root, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.label = ttk.Label(frame, text="请输入关键字或Company ID:")
        self.label.grid(row=0, column=0, padx=5, pady=5)

        self.entry = ttk.Entry(frame, width=50, font=("Helvetica", 12))
        self.entry.grid(row=0, column=1, padx=5, pady=5)

        self.search_button = ttk.Button(frame, text="查询", command=self.search_data)
        self.search_button.grid(row=1, column=0, columnspan=2, pady=10)

        self.result_label = ttk.Label(frame, text="查询结果:", font=("Helvetica", 14, "bold"))
        self.result_label.grid(row=2, column=0, columnspan=2, pady=10)

        self.result_text = tk.Text(frame, height=15, width=80, font=("Helvetica", 12), borderwidth=2, relief="groove")
        self.result_text.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        self.result_text.config(state=tk.DISABLED)

    def search_data(self):
        search_key = self.entry.get().strip()

        if not search_key:
            messagebox.showwarning("输入错误", "请输入有效的关键字或Company ID")
            return

        is_id = search_key.isdigit()

        try:
            base_info, business_info, biz_label = self.crawler.scrape_data(search_key, is_id)

            if not base_info:
                messagebox.showerror("查询失败", "未能找到相关信息")
                return

            self.display_result(base_info, business_info, biz_label)
        except Exception as e:
            messagebox.showerror("查询失败", f"查询过程中发生错误: {str(e)}")

    def display_result(self, base_info, business_info, biz_label):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)

        result = f"公司ID: {base_info.get('company_id', 'N/A')}\n"
        result += f"公司名称: {base_info.get('companyFullName', 'N/A')}\n"
        result += f"统一社会信用代码: {base_info.get('unite_code', 'N/A')}\n"
        result += f"曾用名: {base_info.get('companyFormerName', 'N/A')}\n"

        if business_info:
            result += "\n业务信息:\n"
            for key, value in business_info.items():
                result += f"{key}: {value}\n"

        if biz_label:
            result += "\n标签信息:\n"
            for label in biz_label:
                result += f"类型: {label.get('type', 'N/A')}, LV1: {label.get('lv1Name', 'N/A')}, LV2: {label.get('lv2Name', 'N/A')}\n"

        self.result_text.insert(tk.END, result)
        self.result_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    token = "9d64a51d3435558e656c2956f962414d"  # 替换为实际的token
    root = tk.Tk()
    gui = EqcGUI(root, token)
    root.mainloop()