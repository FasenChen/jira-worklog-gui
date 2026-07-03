"""主窗口：Notebook 4 Tab + 顶栏连接状态 + 关闭确认。"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from typing import Optional

# 把项目根加入路径，让 src/ 和 config.py 可被 import
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .config_store import GuiConfig, load_config  # noqa: E402
from .jira_service import JiraService  # noqa: E402
from .widgets import install_invalid_entry_style  # noqa: E402
from .views import CredentialsView, TaskSummaryView, LogEntryView, TodayLogView  # noqa: E402


APP_TITLE = "JIRA 工作日志登记工具"
APP_VERSION = "0.1.0"


class App(tk.Tk):
    """应用主窗口。"""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1100x720")
        self.minsize(900, 600)

        # Windows DPI：让文字不那么糊
        try:
            self.tk.call("tk", "scaling", 1.25)
        except tk.TclError:
            pass

        install_invalid_entry_style(self)

        self._service: Optional[JiraService] = None
        self._cfg: GuiConfig = load_config()

        self._build_menu()
        self._build_status_bar()
        self._build_notebook()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 启动时若配置无效，强制停在凭据 Tab
        if not self._cfg.is_valid():
            self._set_status("⚠ 请先填写凭据并连接 JIRA", error=True)
            # 禁用其他 Tab
            for i in range(1, self.nb.index("end")):
                try:
                    self.nb.tab(i, state="disabled")
                except tk.TclError:
                    pass

    # ---------- UI 构建 ----------

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="刷新近 7 天日志", command=self._refresh_today)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.config(menu=menubar)

    def _build_status_bar(self):
        bar = ttk.Frame(self, relief="sunken", padding=(8, 4))
        bar.pack(fill="x", side="bottom")
        self._dot = tk.Canvas(bar, width=12, height=12, highlightthickness=0)
        self._dot.pack(side="left")
        self._draw_dot(connected=False)
        self._status_text = ttk.Label(bar, text="未连接")
        self._status_text.pack(side="left", padx=6)
        # 「重连」button 初始就 pack，但默认隐藏（连接成功后显示）
        self._btn_reconnect = ttk.Button(bar, text="重连", command=self._reconnect, width=8)
        self._btn_reconnect.pack(side="right", padx=2)

    def _draw_dot(self, connected: bool):
        self._dot.delete("all")
        color = "#22aa22" if connected else "#cc0000"
        self._dot.create_oval(2, 2, 11, 11, fill=color, outline=color)

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.cred_view = CredentialsView(self.nb, on_connected=self._on_connected)
        self.nb.add(self.cred_view, text="① 凭据配置")

        self.task_summary_view = TaskSummaryView(
            self.nb, service=None, on_issue_selected=self._on_issue_picked
        )
        self.nb.add(self.task_summary_view, text="② 任务汇总")

        self.entry_view = LogEntryView(
            self.nb, service=None, on_log_added=self._refresh_today
        )
        self.nb.add(self.entry_view, text="③ 快速登记")

        self.today_view = TodayLogView(self.nb, service=None)
        self.nb.add(self.today_view, text="④ 近 7 天日志")

    # ---------- 事件回调 ----------

    def _on_connected(self, service: JiraService):
        """CredentialsView 连接成功后调用。"""
        self._service = service
        # 启用其他 Tab
        for i in range(1, self.nb.index("end")):
            try:
                self.nb.tab(i, state="normal")
            except tk.TclError:
                pass
        # 把 service 注入各 view
        self.task_summary_view.set_service(service)
        self.entry_view.set_service(service)
        self.today_view.set_service(service)
        # 顶栏状态
        try:
            info = service.connection.test_connection()
            user = info.get("user", "?")
        except Exception:
            user = "?"
        self._set_status(f"已连接：{user}", connected=True)
        # 默认跳到任务汇总
        self.nb.select(self.task_summary_view)

    def _on_issue_picked(self, issue: dict):
        """TaskSummaryView 选中叶子 issue 后调用：切换到登记 Tab 并预填。"""
        self.entry_view.set_issue(issue)
        self.nb.select(self.entry_view)

    def _refresh_today(self):
        """切到近 7 天日志 Tab 并刷新。"""
        self.nb.select(self.today_view)
        self.today_view.refresh()

    def _reconnect(self):
        if not self._cfg.is_valid():
            messagebox.showwarning("未配置", "请先在「凭据配置」Tab 填写凭据。")
            self.nb.select(self.cred_view)
            return
        self.cred_view._on_connect()

    # ---------- 状态 ----------

    def _set_status(self, text: str, connected: bool = False, error: bool = False):
        self._status_text.configure(
            text=text,
            foreground=("#cc0000" if error else ("#008800" if connected else "#444444")),
        )
        self._draw_dot(connected=connected)
        # 「重连」button 仅在未连接时显示（已连接时干扰）
        if connected:
            self._btn_reconnect.pack_forget()
        else:
            try:
                self._btn_reconnect.pack(side="right", padx=2)
            except tk.TclError:
                pass

    # ---------- 关闭 ----------

    def _on_close(self):
        if messagebox.askokcancel("退出", "确定退出 JIRA 工作日志工具？"):
            if self._service:
                try:
                    self._service.disconnect()
                except Exception:
                    pass
            self.destroy()

    def _show_about(self):
        messagebox.showinfo(
            "关于",
            f"{APP_TITLE}\n版本：{APP_VERSION}\n\n"
            f"底层库：jira_worklog_gui._vendor.jira (JiraConnection)\n"
            f"项目根：{PROJECT_ROOT}\n\n"
            f"配置文件：~/.jira_worklog_gui/config.json",
        )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()