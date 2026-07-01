"""快速登记日志 Tab。"""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

from ..jira_service import JiraService
from ..widgets import DurationEntry


class LogEntryView(ttk.Frame):
    """快速登记表单。

    外部提供 issue（来自 IssuePickerView）后，启用表单，提交后回调。
    """

    def __init__(self, master, service: Optional[JiraService],
                 on_log_added=None, **kw):
        super().__init__(master, padding=12, **kw)
        self.service = service
        self.on_log_added = on_log_added
        self._current_issue: Optional[Dict[str, Any]] = None

        self._var_issue = tk.StringVar(value="（请先在「Issue 浏览器」选择）")
        self._var_duration = tk.StringVar()
        self._var_comment = tk.StringVar()
        self._var_started = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self._var_adjust = tk.StringVar(value="leave")

        self._build_widgets()
        self._set_form_enabled(False)

    def set_service(self, service: JiraService):
        self.service = service

    def set_issue(self, issue: Dict[str, Any]):
        self._current_issue = issue
        self._var_issue.set(f"{issue.get('key','')}  —  {issue.get('summary','')}")
        self._set_form_enabled(True)
        self._duration_entry.clear()
        # 默认开始时间：现在
        self._var_started.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
        self._txt_comment.delete("1.0", "end")

    # ---------- UI 构建 ----------

    def _build_widgets(self):
        # 当前 issue
        row = 0
        ttk.Label(self, text="Issue").grid(row=row, column=0, sticky="nw", pady=4)
        ttk.Label(self, textvariable=self._var_issue, foreground="#0050b0",
                  wraplength=600).grid(row=row, column=1, sticky="ew", pady=4)

        # 耗时
        row += 1
        ttk.Label(self, text="耗时").grid(row=row, column=0, sticky="w", pady=4)
        dur_frame = ttk.Frame(self)
        dur_frame.grid(row=row, column=1, sticky="w", pady=4)
        self._duration_entry = DurationEntry(dur_frame, textvariable=self._var_duration, width=15)
        self._duration_entry.pack(side="left")
        ttk.Label(dur_frame, text="支持 1h30m / 90m / 1.5h / 5400s / 2d",
                  foreground="#888").pack(side="left", padx=8)

        # 开始时间
        row += 1
        ttk.Label(self, text="开始时间").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self._var_started, width=20).grid(
            row=row, column=1, sticky="w", pady=4
        )
        ttk.Label(self, text="格式 YYYY-MM-DD HH:MM，留空=服务器当前时间",
                  foreground="#888").grid(row=row, column=1, sticky="e", padx=4)

        # 工作描述
        row += 1
        ttk.Label(self, text="描述").grid(row=row, column=0, sticky="nw", pady=4)
        self._txt_comment = tk.Text(self, height=6, width=60)
        self._txt_comment.grid(row=row, column=1, sticky="ew", pady=4)

        # 调整估算
        row += 1
        ttk.Label(self, text="剩余估算").grid(row=row, column=0, sticky="w", pady=4)
        adj_frame = ttk.Frame(self)
        adj_frame.grid(row=row, column=1, sticky="w", pady=4)
        for val, label in [("leave", "不调整（默认）"), ("auto", "自动扣减"), ("new", "设为新值")]:
            ttk.Radiobutton(adj_frame, text=label, variable=self._var_adjust,
                            value=val).pack(side="left", padx=4)

        # 按钮
        row += 1
        btn_bar = ttk.Frame(self)
        btn_bar.grid(row=row, column=0, columnspan=2, sticky="ew", pady=12)
        self._btn_submit = ttk.Button(btn_bar, text="登记", command=lambda: self._submit(keep_issue=False))
        self._btn_submit.pack(side="left", padx=2)
        self._btn_submit_more = ttk.Button(
            btn_bar, text="登记并继续（保留 issue）",
            command=lambda: self._submit(keep_issue=True),
        )
        self._btn_submit_more.pack(side="left", padx=2)
        ttk.Button(btn_bar, text="清空", command=self._clear_form).pack(side="left", padx=2)

        row += 1
        self._status_label = ttk.Label(self, text="")
        self._status_label.grid(row=row, column=0, columnspan=2, sticky="w")

        self.columnconfigure(1, weight=1)

    # ---------- 状态 ----------

    def _set_form_enabled(self, enabled: bool):
        state = ("normal" if enabled else "disabled")
        self._btn_submit.configure(state=state)
        self._btn_submit_more.configure(state=state)

    def _set_status(self, text: str, error: bool = False):
        self._status_label.configure(
            text=text,
            foreground=("#cc0000" if error else "#008800"),
        )

    def _clear_form(self):
        self._duration_entry.clear()
        self._txt_comment.delete("1.0", "end")

    def _parse_started(self) -> Optional[datetime]:
        """解析开始时间字符串为带本地时区的 datetime；空字符串返回 None。"""
        s = self._var_started.get().strip()
        if not s:
            return None
        try:
            naive = datetime.strptime(s, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError(f"开始时间格式错误：'{s}'，应为 YYYY-MM-DD HH:MM")
        # 绑本地时区
        local_tz = datetime.now().astimezone().tzinfo
        return naive.replace(tzinfo=local_tz)

    # ---------- 提交 ----------

    def _submit(self, keep_issue: bool):
        if not self.service:
            messagebox.showwarning("未连接", "请先在「凭据」Tab 连接 JIRA。")
            return
        if not self._current_issue:
            messagebox.showwarning("未选 issue", "请先在「Issue 浏览器」选中一个 issue。")
            return
        time_spent = self._duration_entry.get()
        if not time_spent:
            messagebox.showwarning("耗时为空", "请填写耗时，例如 1h30m。")
            return
        comment = self._txt_comment.get("1.0", "end").strip()
        try:
            started = self._parse_started()
        except ValueError as e:
            messagebox.showerror("时间格式错误", str(e))
            return
        adjust_estimate = self._var_adjust.get()

        issue_key = self._current_issue["key"]
        self._set_buttons_enabled(False)
        self._set_status("提交中…")

        def worker():
            try:
                wl = self.service.add_worklog(
                    issue_key=issue_key,
                    time_spent=time_spent,
                    started=started,
                    comment=comment,
                    adjust_estimate=adjust_estimate,
                )
                self.after(0, lambda: self._on_submit_done(wl, keep_issue, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_submit_done(None, keep_issue, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_submit_done(self, worklog, keep_issue, error):
        self._set_buttons_enabled(True)
        if error:
            self._set_status(f"✗ {error}", error=True)
            messagebox.showerror("登记失败", str(error))
            return
        self._set_status(f"✓ 已登记 {worklog.get('time_spent','?')}（id={worklog.get('id')}）")
        if not keep_issue:
            self._current_issue = None
            self._var_issue.set("（请先在「Issue 浏览器」选择）")
            self._set_form_enabled(False)
        self._clear_form()
        if self.on_log_added:
            self.on_log_added()

    def _set_buttons_enabled(self, enabled: bool):
        state = ("normal" if enabled else "disabled")
        try:
            self._btn_submit.configure(state=state)
            self._btn_submit_more.configure(state=state)
        except tk.TclError:
            pass