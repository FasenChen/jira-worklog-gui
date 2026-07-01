"""任务汇总 Tab：3 段堆叠（我的任务 / IPPUB / 自定义 JQL）。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional

from ..jira_service import JiraService


class TaskSummaryView(ttk.Frame):
    """任务汇总：三段堆叠。"""

    EPIC_TYPES = {"Epic"}

    def __init__(self, master, service: Optional[JiraService], on_issue_selected=None, **kw):
        super().__init__(master, padding=8, **kw)
        self.service = service
        self.on_issue_selected = on_issue_selected
        self._hierarchy: Dict[str, Any] = {"epics": [], "orphans": []}
        self._tree_iid_to_issue: Dict[str, Dict[str, Any]] = {}

        self._var_jql = tk.StringVar(value="")
        self._build_widgets()

    def set_service(self, service: JiraService):
        self.service = service
        self._btn_query.configure(state="normal")

    def set_default_jql(self, jql: str):
        if not self._var_jql.get():
            self._var_jql.set(jql)

    # ---------- UI 构建 ----------

    def _build_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="JQL:").pack(side="left")
        ttk.Entry(top, textvariable=self._var_jql).pack(side="left", fill="x", expand=True, padx=4)
        self._btn_query = ttk.Button(top, text="查询", command=self._on_query, state="disabled")
        self._btn_query.pack(side="left", padx=2)
        ttk.Button(top, text="清空", command=self._clear_tree).pack(side="left", padx=2)

        # 树形
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        cols = ("type", "status", "key", "summary")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings", selectmode="browse")
        self._tree.heading("#0", text="层级")
        self._tree.heading("type", text="类型")
        self._tree.heading("status", text="状态")
        self._tree.heading("key", text="Key")
        self._tree.heading("summary", text="摘要")
        self._tree.column("#0", width=140, minwidth=80)
        self._tree.column("type", width=120, minwidth=80, anchor="w")
        self._tree.column("status", width=110, minwidth=80, anchor="w")
        self._tree.column("key", width=130, minwidth=80, anchor="w")
        self._tree.column("summary", width=600, minwidth=200, anchor="w")
        self._tree.tag_configure("epic", background="#e8f0fe", font=("", 9, "bold"))
        self._tree.tag_configure("orphan", background="#fff7e6")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self._btn_use = ttk.Button(bottom, text="用此 issue 登记 →", command=self._on_use, state="disabled")
        self._btn_use.pack(side="right")
        self._status_label = ttk.Label(bottom, text="")
        self._status_label.pack(side="left")

    # ---------- 操作 ----------

    def _set_status(self, text: str, error: bool = False):
        self._status_label.configure(
            text=text,
            foreground=("#cc0000" if error else "#444444"),
        )

    def _clear_tree(self):
        self._tree.delete(*self._tree.get_children())
        self._tree_iid_to_issue.clear()
        self._hierarchy = {"epics": [], "orphans": []}
        self._btn_use.configure(state="disabled")

    def _on_query(self):
        if not self.service:
            messagebox.showwarning("未连接", "请先在「凭据」Tab 连接 JIRA。")
            return
        jql = self._var_jql.get().strip()
        if not jql:
            messagebox.showwarning("JQL 为空", "请输入 JQL 查询语句。")
            return
        self._btn_query.configure(state="disabled")
        self._set_status("查询中…")

        def worker():
            try:
                data = self.service.search_issues_hierarchical(jql)
                self.after(0, lambda: self._on_query_done(data, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_query_done(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_query_done(self, data, error):
        self._btn_query.configure(state="normal")
        if error:
            self._set_status(f"✗ {error}", error=True)
            messagebox.showerror("查询失败", str(error))
            return
        self._clear_tree()
        self._hierarchy = data
        # 渲染
        for epic in data.get("epics", []):
            self._add_epic(epic)
        for orphan in data.get("orphans", []):
            self._add_orphan(orphan)
        total_children = sum(len(e["children"]) for e in data.get("epics", []))
        n_epics = len(data.get("epics", []))
        n_orphans = len(data.get("orphans", []))
        self._set_status(f"✓ 找到 {n_epics} 个 Epic，{total_children} 个子任务，{n_orphans} 个游离 issue")

    def _add_epic(self, epic: Dict[str, Any]):
        iid = self._tree.insert(
            "", "end",
            text=f"📁 {epic['key']}",
            values=("", epic.get("status", ""), epic["key"], epic.get("summary", "")),
            tags=("epic",),
        )
        self._tree_iid_to_issue[iid] = epic
        for child in epic.get("children", []):
            self._add_child(iid, child)

    def _add_child(self, parent_iid: str, child: Dict[str, Any]):
        iid = self._tree.insert(
            parent_iid, "end",
            text="",
            values=(child.get("issue_type", ""), child.get("status", ""),
                    child.get("key", ""), child.get("summary", "")),
        )
        self._tree_iid_to_issue[iid] = child

    def _add_orphan(self, issue: Dict[str, Any]):
        iid = self._tree.insert(
            "", "end",
            text=f"📄 {issue.get('issue_type','?')}",
            values=(issue.get("issue_type", ""), issue.get("status", ""),
                    issue.get("key", ""), issue.get("summary", "")),
            tags=("orphan",),
        )
        self._tree_iid_to_issue[iid] = issue

    def _on_select(self, _evt=None):
        sel = self._tree.selection()
        if not sel:
            self._btn_use.configure(state="disabled")
            return
        issue = self._tree_iid_to_issue.get(sel[0])
        if not issue:
            self._btn_use.configure(state="disabled")
            return
        # Epic 节点不允许直接登记（应选其子任务）
        if issue.get("issue_type") in self.EPIC_TYPES or "children" in issue:
            self._btn_use.configure(state="disabled")
        else:
            self._btn_use.configure(state="normal")

    def _on_use(self):
        sel = self._tree.selection()
        if not sel:
            return
        issue = self._tree_iid_to_issue.get(sel[0])
        if not issue or self.on_issue_selected is None:
            return
        if issue.get("issue_type") in self.EPIC_TYPES or "children" in issue:
            messagebox.showinfo("请选叶子节点", "Epic 不能直接登记，请选其下的任务/子任务。")
            return
        self.on_issue_selected(issue)