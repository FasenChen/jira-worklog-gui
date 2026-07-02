"""近 7 天日志 Tab：展示 + 编辑 + 删除。"""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional

from ..jira_service import JiraService
from ..widgets import DurationEntry, install_invalid_entry_style


class TodayLogView(ttk.Frame):
    """近 7 天日志视图。

    依赖 service 已连接。username/display_name 从 service 的 test_connection() 拿。
    """

    def __init__(self, master, service: Optional[JiraService], **kw):
        super().__init__(master, padding=8, **kw)
        self.service = service
        self._logs: List[Dict[str, Any]] = []
        self._iid_to_log: Dict[str, Dict[str, Any]] = {}

        self._build_widgets()

    def set_service(self, service: JiraService):
        self.service = service

    # ---------- UI 构建 ----------

    def _build_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="近 7 天工作日志").pack(side="left")
        ttk.Button(top, text="刷新", command=self.refresh).pack(side="right", padx=2)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        cols = ("started", "issue", "summary", "time", "comment")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("started", text="开始时间")
        self._tree.heading("issue", text="Issue")
        self._tree.heading("summary", text="摘要")
        self._tree.heading("time", text="耗时")
        self._tree.heading("comment", text="描述")
        self._tree.column("started", width=160, anchor="w")
        self._tree.column("issue", width=110, anchor="w")
        self._tree.column("summary", width=300, anchor="w")
        self._tree.column("time", width=80, anchor="e")
        self._tree.column("comment", width=400, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self._btn_edit = ttk.Button(bottom, text="编辑", command=self._on_edit, state="disabled")
        self._btn_edit.pack(side="right", padx=2)
        self._btn_delete = ttk.Button(bottom, text="删除", command=self._on_delete, state="disabled")
        self._btn_delete.pack(side="right", padx=2)

        self._status_label = ttk.Label(bottom, text="")
        self._status_label.pack(side="left")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    # ---------- 状态 ----------

    def _set_status(self, text: str, error: bool = False):
        self._status_label.configure(
            text=text,
            foreground=("#cc0000" if error else "#444444"),
        )

    def _on_select(self, _evt=None):
        sel = self._tree.selection()
        enabled = ("normal" if sel else "disabled")
        self._btn_edit.configure(state=enabled)
        self._btn_delete.configure(state=enabled)

    # ---------- 数据 ----------

    def refresh(self):
        if not self.service:
            self._set_status("未连接")
            return
        # 取当前用户
        try:
            info = self.service.connection.test_connection()
        except Exception as e:
            self._set_status(f"✗ 取用户失败：{e}", error=True)
            return
        username = info.get("user", "")
        if not username:
            self._set_status("无法从连接信息获取用户名")
            return

        self._set_status("加载中…")

        def worker():
            try:
                logs = self.service.get_recent_worklogs(username, display_name=username, days=7)
                self.after(0, lambda: self._on_refresh_done(logs, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_refresh_done(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(self, logs, error):
        if error:
            self._set_status(f"✗ {error}", error=True)
            return
        self._logs = logs or []
        self._tree.delete(*self._tree.get_children())
        self._iid_to_log.clear()
        for wl in self._logs:
            iid = self._tree.insert(
                "", "end",
                values=(
                    _fmt_started(wl.get("started", "")),
                    wl.get("issue_key", ""),
                    wl.get("summary", ""),
                    wl.get("time_spent", ""),
                    (wl.get("comment", "") or "")[:120],
                ),
            )
            self._iid_to_log[iid] = wl
        total = sum((wl.get("time_spent_seconds") or 0) for wl in self._logs)
        hours = total // 3600
        minutes = (total % 3600) // 60
        self._set_status(f"✓ {len(self._logs)} 条 · 合计 {hours}h {minutes}m")

    # ---------- 编辑 ----------

    def _on_edit(self):
        sel = self._tree.selection()
        if not sel:
            return
        wl = self._iid_to_log.get(sel[0])
        if not wl:
            return
        EditWorklogDialog(self, wl, self.service, on_saved=self.refresh)

    # ---------- 删除 ----------

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        wl = self._iid_to_log.get(sel[0])
        if not wl:
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除 {wl.get('issue_key')} 的日志 {wl.get('time_spent')}？\n"
            f"描述：{wl.get('comment') or '（无）'}",
        ):
            return

        issue_key = wl["issue_key"]
        worklog_id = wl["id"]

        def worker():
            try:
                self.service.delete_worklog(issue_key, str(worklog_id))
                self.after(0, lambda: self._on_delete_done(None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_delete_done(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_done(self, error):
        if error:
            messagebox.showerror("删除失败", str(error))
            return
        self.refresh()


# ============================================================
# 编辑对话框
# ============================================================

class EditWorklogDialog(tk.Toplevel):
    """编辑单条 worklog 的模态对话框。"""

    def __init__(self, parent, worklog: Dict[str, Any], service: JiraService, on_saved=None):
        super().__init__(parent)
        self.title(f"编辑 {worklog.get('issue_key')} - {worklog.get('time_spent','')}")
        self.transient(parent)
        self.grab_set()
        self.worklog = worklog
        self.service = service
        self.on_saved = on_saved

        install_invalid_entry_style(self)

        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        self._var_time = tk.StringVar(value=worklog.get("time_spent", ""))
        self._var_started = tk.StringVar(value=_fmt_started_for_edit(worklog.get("started", "")))
        self._var_comment_var = tk.StringVar()

        row = 0
        ttk.Label(body, text="耗时").grid(row=row, column=0, sticky="w", pady=4)
        self._duration_entry = DurationEntry(body, textvariable=self._var_time, width=15)
        self._duration_entry.grid(row=row, column=1, sticky="w", pady=4)

        row += 1
        ttk.Label(body, text="开始时间").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self._var_started, width=20).grid(row=row, column=1, sticky="w", pady=4)

        row += 1
        ttk.Label(body, text="描述").grid(row=row, column=0, sticky="nw", pady=4)
        self._txt_comment = tk.Text(body, height=6, width=50)
        self._txt_comment.insert("1.0", worklog.get("comment", "") or "")
        self._txt_comment.grid(row=row, column=1, sticky="ew", pady=4)

        row += 1
        btn_bar = ttk.Frame(body)
        btn_bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btn_bar, text="取消", command=self.destroy).pack(side="right", padx=2)
        ttk.Button(btn_bar, text="保存", command=self._on_save).pack(side="right", padx=2)

        self._status_label = ttk.Label(body, text="")
        self._status_label.grid(row=row + 1, column=0, columnspan=2, sticky="w")

        body.columnconfigure(1, weight=1)

    def _parse_started(self) -> Optional[datetime]:
        s = self._var_started.get().strip()
        if not s:
            return None
        # 兼容 "2026-07-01 09:00" 与 "2026-07-01T09:00:00.000+0800" 两种
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                return dt
            except ValueError:
                continue
        raise ValueError(f"无法解析时间：'{s}'")

    def _on_save(self):
        new_time = self._duration_entry.get()
        if not new_time:
            messagebox.showwarning("耗时为空", "请填写耗时。", parent=self)
            return
        try:
            new_started = self._parse_started()
        except ValueError as e:
            messagebox.showerror("时间格式错误", str(e), parent=self)
            return
        new_comment = self._txt_comment.get("1.0", "end").strip()

        issue_key = self.worklog["issue_key"]
        worklog_id = str(self.worklog["id"])

        def worker():
            try:
                self.service.update_worklog(
                    issue_key=issue_key,
                    worklog_id=worklog_id,
                    time_spent=new_time,
                    started=new_started,
                    comment=new_comment,
                )
                self.after(0, lambda: self._on_save_done(None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_save_done(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_done(self, error):
        if error:
            messagebox.showerror("保存失败", str(error), parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


# ============================================================
# 工具函数
# ============================================================

def _fmt_started(s: str) -> str:
    """把 JIRA 格式 '2026-07-01T09:00:00.000+0800' 压成 '2026-07-01 09:00' 显示。"""
    if not s:
        return ""
    try:
        # 截掉毫秒和时区
        return s[:16].replace("T", " ")
    except Exception:
        return s


def _fmt_started_for_edit(s: str) -> str:
    """编辑对话框默认显示的本地时间字符串。"""
    if not s:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    return s[:16].replace("T", " ")