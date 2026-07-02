"""快速登记日志 Tab。"""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

from ..jira_service import JiraService
from ..widgets import DurationEntry, accumulate_duration


class LogEntryView(ttk.Frame):
    """快速登记表单。

    外部提供 issue（来自 TaskSummaryView）后，启用表单，提交后回调。
    """

    def __init__(self, master, service: Optional[JiraService],
                 on_log_added=None, **kw):
        super().__init__(master, padding=12, **kw)
        self.service = service
        self.on_log_added = on_log_added
        self._current_issue: Optional[Dict[str, Any]] = None

        self._var_issue = tk.StringVar(value="（请先在「任务汇总」选择）")
        self._var_duration = tk.StringVar()
        self._var_comment = tk.StringVar()
        self._var_started = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        # adjust_estimate 永远是 leave，不再让 UI 选择

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
        for label, secs in [("+30min", 30 * 60), ("+1h", 3600), ("+2h", 2 * 3600),
                            ("+4h", 4 * 3600), ("+8h", 8 * 3600)]:
            ttk.Button(dur_frame, text=label, width=6,
                       command=lambda s=secs: self._on_quick_duration(s)).pack(side="left", padx=2)
        ttk.Label(dur_frame, text="支持 1h30m / 90m / 1.5h / 5400s / 2d",
                  foreground="#888").pack(side="left", padx=8)

        # 开始时间：第一行手输 + 日期快捷；第二行时段快捷
        row += 1
        ttk.Label(self, text="开始时间").grid(row=row, column=0, sticky="nw", pady=4)
        started_frame = ttk.Frame(self)
        started_frame.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Entry(started_frame, textvariable=self._var_started, width=20).pack(side="left")
        ttk.Label(started_frame, text="格式 YYYY-MM-DD HH:MM",
                  foreground="#888").pack(side="left", padx=8)

        # 日期快捷：近 7 天（今天 / 昨天 / ... / 6 天前）+ 一个"现在"按钮
        date_row = ttk.Frame(self)
        date_row.grid(row=row, column=1, sticky="w", pady=(0, 4))
        ttk.Label(date_row, text="日期：", foreground="#666").pack(side="left", padx=(0, 4))
        # 「现在」按钮：填入今天 + 当前小时分钟
        ttk.Button(date_row, text="现在", width=5,
                   command=lambda: self._on_started_date(0, keep_time=True)).pack(side="left", padx=1)
        for i in range(7):  # 0=今天, 1=昨天, ..., 6=6 天前
            label = "今" if i == 0 else f"{i}天前"
            ttk.Button(date_row, text=label, width=5,
                       command=lambda d=i: self._on_started_date(d, keep_time=False)).pack(side="left", padx=1)

        # 时段快捷：8/9/10/11/14/15/16/17/18 点（跳过 12/13 午休）
        hour_row = ttk.Frame(self)
        hour_row.grid(row=row, column=1, sticky="w", pady=(0, 4))
        ttk.Label(hour_row, text="时段：", foreground="#666").pack(side="left", padx=(0, 4))
        for h in (8, 9, 10, 11, 14, 15, 16, 17, 18):
            ttk.Button(hour_row, text=f"{h}点", width=5,
                       command=lambda hh=h: self._on_started_hour(hh)).pack(side="left", padx=1)

        # 工作描述
        row += 1
        ttk.Label(self, text="描述").grid(row=row, column=0, sticky="nw", pady=4)
        self._txt_comment = tk.Text(self, height=6, width=60)
        self._txt_comment.grid(row=row, column=1, sticky="ew", pady=4)

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

    def _on_quick_duration(self, add_seconds: int):
        """快捷按钮：把 add_seconds 累加到当前输入框。"""
        current = self._var_duration.get().strip()
        try:
            new_text = accumulate_duration(current, add_seconds)
        except ValueError:
            messagebox.showwarning("输入有误", f"当前耗时 '{current}' 无法解析，请先修正或清空。")
            return
        self._var_duration.set(new_text)
        self._duration_entry._refresh_style()

    # ---------- 开始时间快捷 ----------

    def _on_started_date(self, days_ago: int, keep_time: bool = False):
        """日期快捷按钮：days_ago=0=今天, 1=昨天, ..., 6=6 天前。

        keep_time=True（「现在」按钮）：只换日期，保留原小时分钟。
        keep_time=False：只换日期，时间归零到 00:00（让用户接着点时段按钮）。
        """
        new_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        s = self._var_started.get().strip()
        if keep_time and s:
            # 保留原时间部分
            try:
                _ = datetime.strptime(s, "%Y-%m-%d %H:%M")
                time_part = s[11:]  # "HH:MM"
            except ValueError:
                time_part = datetime.now().strftime("%H:%M")
        else:
            time_part = "00:00"
        self._var_started.set(f"{new_date} {time_part}")

    def _on_started_hour(self, hour: int):
        """时段快捷按钮：替换或补全输入框的小时部分（分钟归零）。"""
        s = self._var_started.get().strip()
        date_part = datetime.now().strftime("%Y-%m-%d")
        if s:
            try:
                datetime.strptime(s, "%Y-%m-%d %H:%M")
                date_part = s[:10]
            except ValueError:
                pass
        self._var_started.set(f"{date_part} {hour:02d}:00")

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
            messagebox.showwarning("未选 issue", "请先在「任务汇总」选中一个 issue。")
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
        # adjust_estimate 永远是 leave（设计决策：不调整 issue 剩余估算）
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
            self._var_issue.set("（请先在「任务汇总」选择）")
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