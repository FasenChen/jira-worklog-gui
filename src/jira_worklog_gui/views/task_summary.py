"""任务汇总 Tab：3 段堆叠（我的任务 / IPPUB / 自定义 JQL）。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from ..jira_service import JiraService, MY_TASKS_JQL, IPPUB_JQL


class _SummarySection(ttk.LabelFrame):
    """任务汇总中的一段：标题栏 + 树形 + 状态条 + 独立查询按钮。

    支持两种模式：
        preset_jql: 提供预设 JQL，构造时自动查询；带 "刷新" 按钮
        custom: 用户在输入框填 JQL，点 "查询" 按钮
    """

    EPIC_TYPES = {"Epic"}

    def __init__(self, master, title: str, service: Optional[JiraService],
                 preset_jql: Optional[str] = None,
                 on_issue_selected: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_pick_to_register: Optional[Callable[[Dict[str, Any]], None]] = None,
                 **kw):
        super().__init__(master, text=title, padding=8, **kw)
        self.service = service
        # on_issue_selected: 选中回调（仅更新状态，不切 Tab）
        # on_pick_to_register: 登记回调（点 inline 按钮 / 双击触发，应切到快速登记 Tab）
        self._on_issue_selected = on_issue_selected
        self._on_pick_to_register = on_pick_to_register
        self._hierarchy: Dict[str, Any] = {"epics": [], "orphans": []}
        self._tree_iid_to_issue: Dict[str, Dict[str, Any]] = {}

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        if preset_jql is not None:
            self._jql_text = None
            self._btn_query = ttk.Button(top, text="刷新", command=self._on_query)
            self._btn_query.pack(side="right", padx=2)
            self._auto_query_jql = preset_jql
        else:
            self._jql_text = tk.StringVar()
            ttk.Entry(top, textvariable=self._jql_text).pack(side="left", fill="x", expand=True, padx=2)
            self._btn_query = ttk.Button(top, text="查询", command=self._on_query)
            self._btn_query.pack(side="right", padx=2)
            self._auto_query_jql = None
        # 每段独立的"登记此 issue"按钮（inline 可见；选叶子后才可用）
        self._btn_pick = ttk.Button(top, text="📝 登记此 issue →", command=self._on_pick_clicked, state="disabled")
        self._btn_pick.pack(side="right", padx=2)
        # 并发查询保护：每次点击 _on_query 自增 token，回调里只接受最新 token
        self._query_token = 0
        self._query_in_flight = False

        cols = ("type", "status", "key", "summary")
        self._tree = ttk.Treeview(self, columns=cols, show="tree headings", selectmode="browse")
        self._tree.heading("#0", text="层级")
        self._tree.heading("type", text="类型")
        self._tree.heading("status", text="状态")
        self._tree.heading("key", text="Key")
        self._tree.heading("summary", text="摘要")
        self._tree.column("#0", width=120, minwidth=80)
        self._tree.column("type", width=110, minwidth=80)
        self._tree.column("status", width=100, minwidth=80)
        self._tree.column("key", width=130, minwidth=80)
        self._tree.column("summary", width=400, minwidth=200)
        self._tree.tag_configure("epic", background="#e8f0fe", font=("", 9, "bold"))
        self._tree.tag_configure("orphan", background="#fff7e6")

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, pady=(4, 0))
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_label = ttk.Label(self, text="")
        self._status_label.pack(anchor="w", pady=(2, 0))

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        # 双击叶子节点直接登记（最便捷的操作）
        self._tree.bind("<Double-1>", self._on_pick_clicked)

    # ---------- 公开 ----------

    def set_service(self, service: JiraService):
        self.service = service
        if self._auto_query_jql:
            self._on_query()

    def get_selected_issue(self) -> Optional[Dict[str, Any]]:
        sel = self._tree.selection()
        if not sel:
            return None
        issue = self._tree_iid_to_issue.get(sel[0])
        if not issue or issue.get("issue_type") in self.EPIC_TYPES or "children" in issue:
            return None
        return issue

    # ---------- 内部 ----------

    def _set_status(self, text: str, error: bool = False):
        self._status_label.configure(
            text=text,
            foreground=("#cc0000" if error else "#444444"),
        )

    def _clear_tree(self):
        self._tree.delete(*self._tree.get_children())
        self._tree_iid_to_issue.clear()
        self._hierarchy = {"epics": [], "orphans": []}

    def _on_query(self):
        if self._query_in_flight:
            return  # 防止快速重复点击造成数据竞态
        if not self.service:
            self._set_status("未连接", error=True)
            return
        jql = self._auto_query_jql or (self._jql_text.get().strip() if self._jql_text else "")
        if not jql:
            self._set_status("JQL 为空", error=True)
            return
        self._query_in_flight = True
        self._query_token += 1
        token = self._query_token
        try:
            self._btn_query.configure(state="disabled")
        except tk.TclError:
            pass
        self._set_status("查询中…")

        def worker():
            try:
                data = self.service.search_issues_hierarchical(jql)
                self.after(0, lambda: self._on_query_done(token, data, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_query_done(token, None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_query_done(self, token, data, error):
        # 只接受最新 token 的结果，丢弃过期回调
        if token != self._query_token:
            return
        self._query_in_flight = False
        try:
            self._btn_query.configure(state="normal")
        except tk.TclError:
            pass  # 控件已销毁（应用关闭中）
        try:
            if error:
                self._set_status(f"✗ {error}", error=True)
                return
            self._clear_tree()
            self._hierarchy = data
            for epic in data.get("epics", []):
                self._add_epic(epic)
            for orphan in data.get("orphans", []):
                self._add_orphan(orphan)
            total_children = sum(len(e["children"]) for e in data.get("epics", []))
            n_epics = len(data.get("epics", []))
            n_orphans = len(data.get("orphans", []))
            self._set_status(
                f"✓ {n_epics} 个 Epic · {total_children} 个子任务 · {n_orphans} 个游离"
            )
        except tk.TclError:
            pass  # widget 已在回调中途被销毁

    def _add_epic(self, epic):
        iid = self._tree.insert(
            "", "end",
            text=f"📁 {epic['key']}",
            values=("", epic.get("status", ""), epic["key"], epic.get("summary", "")),
            tags=("epic",),
        )
        self._tree_iid_to_issue[iid] = epic
        for child in epic.get("children", []):
            self._add_child(iid, child)

    def _add_child(self, parent_iid, child):
        iid = self._tree.insert(
            parent_iid, "end",
            text="",
            values=(child.get("issue_type", ""), child.get("status", ""),
                    child.get("key", ""), child.get("summary", "")),
        )
        self._tree_iid_to_issue[iid] = child

    def _add_orphan(self, issue):
        iid = self._tree.insert(
            "", "end",
            text=f"📄 {issue.get('issue_type', '?')}",
            values=(issue.get("issue_type", ""), issue.get("status", ""),
                    issue.get("key", ""), issue.get("summary", "")),
            tags=("orphan",),
        )
        self._tree_iid_to_issue[iid] = issue

    def _on_select(self, _evt=None):
        issue = self.get_selected_issue()
        # 启用/禁用本段 inline 按钮
        try:
            self._btn_pick.configure(state=("normal" if issue else "disabled"))
        except tk.TclError:
            pass
        # 通知上层（TaskSummaryView 维护"统一底部按钮"状态）
        if self._on_issue_selected and issue:
            self._on_issue_selected(issue)

    def _on_pick_clicked(self, _evt=None):
        """双击或点击 inline 按钮：把当前选中的叶子 issue 真正冒泡到 App 切 Tab。"""
        issue = self.get_selected_issue()
        if issue and self._on_pick_to_register:
            self._on_pick_to_register(issue)


class TaskSummaryView(ttk.Frame):
    """任务汇总：三段堆叠（我的任务 / IPPUB / 自定义 JQL）。"""

    def __init__(self, master, service: Optional[JiraService],
                 on_issue_selected: Optional[Callable[[Dict[str, Any]], None]] = None,
                 **kw):
        super().__init__(master, padding=8, **kw)
        self._service = service
        self._on_issue_selected = on_issue_selected
        self._selected_issue: Optional[Dict[str, Any]] = None

        # 包装一层 lambda 把 self + issue 正确传过去
        # （直接传 self._on_use 会让 Python 当成 unbound method 调用，缺 self 时报
        # "takes 1 positional argument but 2 were given"）
        def pick_handler(issue):
            self._on_use()

        self._section_my = _SummarySection(
            self, "📌 我的非 IPPUB 任务（未完成，排除缺陷和子任务）",
            service=service, preset_jql=MY_TASKS_JQL,
            on_issue_selected=self._on_internal_select,
            on_pick_to_register=pick_handler,
        )
        self._section_my.pack(fill="both", expand=True, pady=(0, 6))

        self._section_ipub = _SummarySection(
            self, "🏷️ 我的 IPPUB 任务（排除缺陷）",
            service=service, preset_jql=IPPUB_JQL,
            on_issue_selected=self._on_internal_select,
            on_pick_to_register=pick_handler,
        )
        self._section_ipub.pack(fill="both", expand=True, pady=(0, 6))

        self._section_custom = _SummarySection(
            self, "🔍 自定义 JQL",
            service=service, preset_jql=None,
            on_issue_selected=self._on_internal_select,
            on_pick_to_register=pick_handler,
        )
        self._section_custom.pack(fill="both", expand=True, pady=(0, 6))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        # 操作提示（让用户知道"在哪点"）
        ttk.Label(bottom, text="💡 选中叶子 issue 后，可点段内「📝 登记此 issue →」按钮、或双击该 issue、或点下方「用此 issue 登记 →」：",
                  foreground="#666").pack(side="left", padx=(0, 8))
        self._status_label = ttk.Label(bottom, text="（未选）", foreground="#888")
        self._status_label.pack(side="left")
        self._btn_use = ttk.Button(bottom, text="用此 issue 登记 →",
                                   command=self._on_use, state="disabled")
        self._btn_use.pack(side="right")

    def set_service(self, service: JiraService):
        self._service = service
        self._section_my.set_service(service)
        self._section_ipub.set_service(service)
        self._section_custom.set_service(service)

    def _on_internal_select(self, issue: Dict[str, Any]):
        self._selected_issue = issue
        try:
            self._btn_use.configure(state="normal")
        except tk.TclError:
            pass
        self._status_label.configure(
            text=f"已选 {issue.get('key','')} — {issue.get('summary','')}",
            foreground="#0050b0",
        )

    def _on_use(self):
        """底部统一按钮 / 段内 inline 按钮 / 双击 issue 都走这里。
        把选中的 issue 真正冒泡给 App（切到快速登记 Tab）。
        """
        if not self._selected_issue or not self._on_issue_selected:
            return
        self._on_issue_selected(self._selected_issue)