"""凭据配置 Tab。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ..config_store import GuiConfig, load_config, save_config, config_path
from ..jira_service import JiraService


def _cfg_to_dict(cfg: GuiConfig) -> dict:
    return {
        "username": cfg.username,
        "password": cfg.password,
    }


class CredentialsView(ttk.Frame):
    """凭据配置视图。

    事件回调（由 app.py 注入）：
        on_connected(service: JiraService): 连接成功后调用
    """

    def __init__(self, master, on_connected=None, **kw):
        super().__init__(master, padding=12, **kw)
        self.on_connected = on_connected
        self._cfg = load_config()

        self._var_user = tk.StringVar(value=self._cfg.last_username or self._cfg.username)
        self._var_pwd = tk.StringVar(value=self._cfg.password)
        self._var_jql = tk.StringVar(value=self._cfg.default_jql)

        self._build_widgets()
        self._set_status("未连接", error=True)

    # ---------- UI 构建 ----------

    def _build_widgets(self):
        from ..config_store import HARDCODED_JIRA_URL

        row = 0
        # 服务器 URL 只读展示
        ttk.Label(self, text="服务器").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Label(self, text=HARDCODED_JIRA_URL, foreground="#0050b0").grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Label(self, text="用户名").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self._var_user, width=30).grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Label(self, text="密码").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self._var_pwd, width=40, show="•").grid(
            row=row, column=1, sticky="w", pady=4
        )

        row += 1
        ttk.Label(self, text="默认 JQL").grid(row=row, column=0, sticky="nw", pady=4)
        ttk.Entry(self, textvariable=self._var_jql, width=80).grid(
            row=row, column=1, sticky="ew", pady=4
        )

        row += 1
        btn_bar = ttk.Frame(self)
        btn_bar.grid(row=row, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Button(btn_bar, text="保存配置", command=self._on_save).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="连接", command=self._on_connect).pack(side="left", padx=2)

        row += 1
        self._status_label = ttk.Label(self, text="")
        self._status_label.grid(row=row, column=0, columnspan=2, sticky="w")

        row += 1
        ttk.Label(
            self, text=f"配置文件：{config_path()}", foreground="#888"
        ).grid(row=row, column=0, columnspan=2, sticky="w")

        self.columnconfigure(1, weight=1)

    # ---------- 状态 ----------

    def _set_status(self, text: str, error: bool = False):
        self._status_label.configure(
            text=text,
            foreground=("#cc0000" if error else "#008800"),
        )

    def _collect(self) -> GuiConfig:
        return GuiConfig(
            username=self._var_user.get().strip(),
            password=self._var_pwd.get(),
            default_jql=self._var_jql.get().strip() or GuiConfig.default_jql,
            last_username=self._var_user.get().strip(),
        )

    # ---------- 按钮事件 ----------

    def _on_save(self):
        cfg = self._collect()
        try:
            save_config(cfg)
            self._set_status("✓ 配置已保存")
        except OSError as e:
            messagebox.showerror("保存失败", str(e))

    def _on_connect(self):
        """异步连接，避免阻塞 UI。"""
        cfg = self._collect()
        if not cfg.is_valid():
            messagebox.showwarning("配置不完整", "请填写用户名与密码。")
            return
        # 先保存
        try:
            save_config(cfg)
        except OSError as e:
            messagebox.showwarning("保存失败", str(e))
            return

        self._set_status("连接中…")
        self._set_buttons_enabled(False)

        def worker():
            try:
                svc = JiraService(_cfg_to_dict(cfg))
                info = svc.connect()
                self.after(0, lambda: self._on_connect_done(svc, info, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_connect_done(None, None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connect_done(self, service, info, error):
        self._set_buttons_enabled(True)
        if error:
            self._set_status(f"✗ {error}", error=True)
            messagebox.showerror("连接失败", str(error))
            return
        user = info.get("user", "?")
        self._set_status(f"✓ 已连接：{user} @ {info.get('server_title','')}")
        if self.on_connected:
            self.on_connected(service)

    def _set_buttons_enabled(self, enabled: bool):
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                for btn in child.winfo_children():
                    if isinstance(btn, ttk.Button):
                        try:
                            btn.configure(state=("normal" if enabled else "disabled"))
                        except tk.TclError:
                            pass