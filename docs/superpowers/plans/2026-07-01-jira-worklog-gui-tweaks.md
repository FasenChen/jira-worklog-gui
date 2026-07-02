# JIRA 工作日志登记 GUI 调整 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已实现的 `tools/jira_worklog_gui/` 上做 6 项调整：固定 URL、取消 Token 登录、Issue 浏览器改名为任务汇总并拆三段、耗时加快捷按钮累加、移除剩余估算选项。

**Architecture:** 沿用现有 MVC 风格（View → JiraService → JiraConnection → jira 库）。本轮只动 View 层和服务层的少量配置，不动 `src/jira` 库。

**Tech Stack:** Python 3.8+ / Tkinter (标准库) / unittest.mock / pytest。

**Spec:** `docs/superpowers/specs/2026-07-01-jira-worklog-gui-tweaks-design.md`

---

## Task 1: duration_entry 增加 format_seconds_to_jira 和 accumulate_duration

**Files:**
- Modify: `tools/jira_worklog_gui/widgets/duration_entry.py`
- Test: `tests/test_duration.py`

- [ ] **Step 1: 追加测试用例到 tests/test_duration.py**

在文件末尾追加两个新测试类：

```python
# ============================================================
# format_seconds_to_jira
# ============================================================

class TestFormatSecondsToJira:
    def test_zero(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(0) == "0s"

    def test_only_seconds(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(30) == "30s"

    def test_only_minutes(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(60) == "1m"

    def test_only_hours(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(3600) == "1h"

    def test_hours_and_minutes(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(5400) == "1h 30m"

    def test_24h(self):
        from tools.jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(86400) == "24h"


# ============================================================
# accumulate_duration
# ============================================================

class TestAccumulateDuration:
    def test_empty_plus_1h(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("", 3600) == "1h"

    def test_1h30m_plus_30min(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("1h 30m", 1800) == "2h"

    def test_invalid_raises_value_error(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        with pytest.raises(ValueError):
            accumulate_duration("xyz", 3600)

    def test_30s_plus_1h(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("30s", 3600) == "1h 30s"

    def test_8h_plus_8h(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("8h", 8 * 3600) == "16h"

    def test_whitespace_stripped(self):
        from tools.jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("  1h  ", 1800) == "1h 30m"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -m pytest tests/test_duration.py::TestFormatSecondsToJira tests/test_duration.py::TestAccumulateDuration -v`
Expected: 全部 FAIL（ImportError: cannot import name 'format_seconds_to_jira'）

- [ ] **Step 3: 在 duration_entry.py 实现两个新函数**

在 `parse_duration` 函数之后追加：

```python
def format_seconds_to_jira(total_seconds: int) -> str:
    """把总秒数格式化为 jira 字符串（如 '1h 30m'）。

    规则：
        - 0 秒 → "0s"
        - 只含秒（< 60）→ "30s"
        - 整小时无零头 → "1h" / "24h"
        - 否则 "Xh Ym" 或 "Xm Ys"
    """
    if total_seconds <= 0:
        return "0s"
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours == 0 and minutes == 0:
        return f"{seconds}s"
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not minutes and hours and seconds:
        parts.append(f"{seconds}s")
    elif not hours and seconds and not minutes:
        pass  # 已在上方处理
    return " ".join(parts)


def accumulate_duration(current: str, add_seconds: int) -> str:
    """把 current 解析为秒，加上 add_seconds，返回 jira 字符串。

    Raises:
        ValueError: current 非空且无法解析时。
    """
    if current and current.strip():
        secs, _ = parse_duration(current)
        if secs is None:
            raise ValueError(f"无法解析耗时：'{current}'")
        new_total = secs + add_seconds
    else:
        new_total = add_seconds
    return format_seconds_to_jira(new_total)
```

- [ ] **Step 4: 重新跑测试，确认全过**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -m pytest tests/test_duration.py -v`
Expected: 全部 PASS（之前 29 个 + 新增 12 个 = 41 个）

- [ ] **Step 5: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/widgets/duration_entry.py tests/test_duration.py
git commit -m "feat(duration): add format_seconds_to_jira and accumulate_duration"
```

---

## Task 2: config_store 移除 URL/Token，加 HARDCODED_JIRA_URL

**Files:**
- Modify: `tools/jira_worklog_gui/config_store.py`

- [ ] **Step 1: 修改 GuiConfig dataclass**

将现有：
```python
@dataclass
class GuiConfig:
    """GUI 工具的完整配置（不含环境变量，因为环境变量优先级更高）。"""
    jira_url: str = ""
    username: str = ""
    password: str = ""
    token: str = ""
    default_jql: str = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
    verify_ssl: bool = True
    last_username: str = ""  # 仅用于 UI 显示
```

替换为：
```python
@dataclass
class GuiConfig:
    """GUI 工具的完整配置。URL 已硬编码到 HARDCODED_JIRA_URL。"""
    username: str = ""
    password: str = ""
    default_jql: str = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
    last_username: str = ""  # 仅用于 UI 显示
```

- [ ] **Step 2: 在文件顶部加常量**

在 `CONFIG_FILE` 之后追加：
```python
# 公司 JIRA 实例固定 URL，不再由用户配置
HARDCODED_JIRA_URL = "https://idisplayvision.com/jira/"
```

- [ ] **Step 3: 修改 _to_gui_config**

将现有：
```python
def _to_gui_config(d: dict) -> GuiConfig:
    """从 dict 安全构造 GuiConfig（容错缺失字段）。"""
    return GuiConfig(
        jira_url=d.get("jira_url", "") or "",
        username=d.get("username", "") or "",
        password=d.get("password", "") or "",
        token=d.get("token", "") or "",
        default_jql=d.get("default_jql") or GuiConfig.default_jql,
        verify_ssl=bool(d.get("verify_ssl", True)),
        last_username=d.get("last_username", "") or "",
    )
```

替换为：
```python
def _to_gui_config(d: dict) -> GuiConfig:
    """从 dict 安全构造 GuiConfig。旧字段 jira_url/token/verify_ssl 静默忽略。"""
    return GuiConfig(
        username=d.get("username", "") or "",
        password=d.get("password", "") or "",
        default_jql=d.get("default_jql") or GuiConfig.default_jql,
        last_username=d.get("last_username", "") or "",
    )
```

- [ ] **Step 4: 修改 load_config**

将现有：
```python
def load_config() -> GuiConfig:
    file_cfg: dict = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            file_cfg = {}
    base = _to_gui_config(file_cfg)

    # 环境变量覆盖
    base.jira_url = os.getenv("JIRA_URL") or base.jira_url
    base.username = os.getenv("JIRA_USERNAME") or base.username
    base.password = os.getenv("JIRA_PASSWORD") or base.password
    base.token = os.getenv("JIRA_TOKEN") or base.token
    if base.username:
        base.last_username = base.username
    return base
```

替换为：
```python
def load_config() -> GuiConfig:
    file_cfg: dict = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            file_cfg = {}
    base = _to_gui_config(file_cfg)

    # 环境变量仅覆盖用户名/密码（URL 已硬编码）
    base.username = os.getenv("JIRA_USERNAME") or base.username
    base.password = os.getenv("JIRA_PASSWORD") or base.password
    if base.username:
        base.last_username = base.username
    return base
```

- [ ] **Step 5: 修改 is_valid**

将现有：
```python
def is_valid(self) -> bool:
    """基本检查：URL 必须非空，且 password 或 token 至少有一个。"""
    if not self.jira_url:
        return False
    return bool(self.password) or bool(self.token)
```

替换为：
```python
def is_valid(self) -> bool:
    """基本检查：用户名 + 密码都必须有。"""
    return bool(self.username) and bool(self.password)
```

- [ ] **Step 6: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/config_store.py
git commit -m "refactor(config): hardcode JIRA URL, remove token auth"
```

---

## Task 3: jira_service 删除 token 字段，加 JQL 常量

**Files:**
- Modify: `tools/jira_worklog_gui/jira_service.py`

- [ ] **Step 1: 在文件顶部加 JQL 常量**

在 `from src.jira.query import ...` 之后、`def parse_issue_summary` 之前追加：
```python
# 任务汇总预设 JQL（设计文档定义）
MY_TASKS_JQL = (
    'assignee = currentUser() '
    'AND issuetype != "问题缺陷" '
    'AND issuetype != "Bug" '
    'AND statusCategory != Done '
    'ORDER BY updated DESC'
)

IPPUB_JQL = (
    'project = "IPPUB" '
    'AND issuetype != "问题缺陷" '
    'AND issuetype != "Bug" '
    'ORDER BY updated DESC'
)
```

- [ ] **Step 2: 修改 connect() 删 token、改 URL**

将现有：
```python
def connect(self) -> Dict[str, Any]:
    """建立连接。返回 test_connection() 的结果 dict。"""
    kwargs = {
        "url": self._config.get("jira_url"),
        "username": self._config.get("username"),
        "password": self._config.get("password"),
        "token": self._config.get("token"),
        "verify_ssl": self._config.get("verify_ssl", True),
    }
    kwargs = {k: v for k, v in kwargs.items() if v not in (None, "")}
    self._conn = JiraConnection(**kwargs).connect()
    return self._conn.test_connection()
```

替换为：
```python
def connect(self) -> Dict[str, Any]:
    """建立连接。返回 test_connection() 的结果 dict。URL 硬编码。"""
    from .config_store import HARDCODED_JIRA_URL
    self._conn = JiraConnection(
        url=HARDCODED_JIRA_URL,
        username=self._config.get("username"),
        password=self._config.get("password"),
    ).connect()
    return self._conn.test_connection()
```

- [ ] **Step 3: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/jira_service.py
git commit -m "refactor(service): hardcode URL, drop token, add JQL constants"
```

---

## Task 4: 测试 jira_service 的 JQL 常量 + connect 改密码

**Files:**
- Modify: `tests/test_jira_service.py`

- [ ] **Step 1: 在 TestParseIssueSummary 之前追加 TestJqlConstants**

```python
class TestJqlConstants:
    def test_my_tasks_jql_includes_assignee_and_excludes_bugs(self):
        from tools.jira_worklog_gui.jira_service import MY_TASKS_JQL
        assert isinstance(MY_TASKS_JQL, str)
        assert "assignee = currentUser()" in MY_TASKS_JQL
        assert '"问题缺陷"' in MY_TASKS_JQL
        assert '"Bug"' in MY_TASKS_JQL
        assert "statusCategory != Done" in MY_TASKS_JQL
        assert "ORDER BY updated DESC" in MY_TASKS_JQL

    def test_ippub_jql_includes_project_and_excludes_bugs(self):
        from tools.jira_worklog_gui.jira_service import IPPUB_JQL
        assert isinstance(IPPUB_JQL, str)
        assert 'project = "IPPUB"' in IPPUB_JQL
        assert '"问题缺陷"' in IPPUB_JQL
        assert '"Bug"' in IPPUB_JQL
        assert "ORDER BY updated DESC" in IPPUB_JQL
        # 我的任务专属条件不应出现
        assert "currentUser()" not in IPPUB_JQL
```

- [ ] **Step 2: 改 test_connect_strips_empty_kwargs → test_connect_uses_password**

将：
```python
@patch("tools.jira_worklog_gui.jira_service.JiraConnection")
def test_connect_strips_empty_kwargs(self, mock_conn_cls):
    """不传空字符串字段给 JiraConnection。"""
    _make_mock_connection(mock_conn_cls)
    svc = JiraService({"jira_url": "https://x", "username": "u", "password": "p", "token": ""})
    svc.connect()
    kwargs = mock_conn_cls.call_args.kwargs
    assert "token" not in kwargs  # 空字符串应被剔除
```

替换为：
```python
@patch("tools.jira_worklog_gui.jira_service.JiraConnection")
def test_connect_uses_hardcoded_url(self, mock_conn_cls):
    """connect() 使用 HARDCODED_JIRA_URL，不读 config 里的 jira_url。"""
    from tools.jira_worklog_gui.config_store import HARDCODED_JIRA_URL
    _make_mock_connection(mock_conn_cls)
    svc = JiraService({"username": "u", "password": "p"})
    svc.connect()
    kwargs = mock_conn_cls.call_args.kwargs
    assert kwargs["url"] == HARDCODED_JIRA_URL
    assert kwargs["username"] == "u"
    assert kwargs["password"] == "p"
    assert "token" not in kwargs
```

- [ ] **Step 3: 修复已有 connect 测试**

第一个 connect 测试：
```python
@patch("tools.jira_worklog_gui.jira_service.JiraConnection")
def test_connect(self, mock_conn_cls):
    mock_conn = _make_mock_connection(mock_conn_cls)
    mock_conn.test_connection.return_value = {"user": "alice", "server_title": "Test"}

    svc = JiraService({"jira_url": "https://x", "username": "u", "password": "p"})
    info = svc.connect()

    assert info["user"] == "alice"
    mock_conn_cls.assert_called_once()
    kwargs = mock_conn_cls.call_args.kwargs
    assert kwargs["url"] == "https://x"
    assert kwargs["username"] == "u"
    assert kwargs["password"] == "p"
    assert svc.is_connected is True
```

改为：
```python
@patch("tools.jira_worklog_gui.jira_service.JiraConnection")
def test_connect(self, mock_conn_cls):
    mock_conn = _make_mock_connection(mock_conn_cls)
    mock_conn.test_connection.return_value = {"user": "alice", "server_title": "Test"}

    svc = JiraService({"username": "u", "password": "p"})
    info = svc.connect()

    assert info["user"] == "alice"
    mock_conn_cls.assert_called_once()
    kwargs = mock_conn_cls.call_args.kwargs
    # URL 现在来自 HARDCODED_JIRA_URL，不再来自 config dict
    from tools.jira_worklog_gui.config_store import HARDCODED_JIRA_URL
    assert kwargs["url"] == HARDCODED_JIRA_URL
    assert kwargs["username"] == "u"
    assert kwargs["password"] == "p"
    assert svc.is_connected is True
```

- [ ] **Step 4: 跑测试确认全过**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -m pytest tests/test_jira_service.py -v`
Expected: 全部 PASS（13 个旧 + 2 个新 = 15 个）

- [ ] **Step 5: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tests/test_jira_service.py
git commit -m "test(service): cover JQL constants and hardcoded URL"
```

---

## Task 5: credentials_view 删 URL/Token 输入行 + 测试按钮

**Files:**
- Modify: `tools/jira_worklog_gui/views/credentials_view.py`

- [ ] **Step 1: 删 `_var_url` `_var_token` `_var_ssl`，新增只读 URL 显示**

替换整个 `__init__` 中的变量初始化块：

```python
self._cfg = load_config()

self._var_user = tk.StringVar(value=self._cfg.last_username or self._cfg.username)
self._var_pwd = tk.StringVar(value=self._cfg.password)
self._var_jql = tk.StringVar(value=self._cfg.default_jql)

self._build_widgets()
self._set_status("未连接", error=True)
```

- [ ] **Step 2: 重写 `_build_widgets`**

将整个 `_build_widgets` 方法替换为：

```python
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
```

- [ ] **Step 3: 删除 _on_test 方法**

整个删除 `_on_test` 方法（不再提供"测试连接"按钮）。

- [ ] **Step 4: 修改 _collect**

将：
```python
def _collect(self) -> GuiConfig:
    return GuiConfig(
        jira_url=self._var_url.get().strip(),
        username=self._var_user.get().strip(),
        password=self._var_pwd.get(),
        token=self._var_token.get(),
        default_jql=self._var_jql.get().strip() or GuiConfig.default_jql,
        verify_ssl=self._var_ssl.get(),
        last_username=self._var_user.get().strip(),
    )
```

替换为：
```python
def _collect(self) -> GuiConfig:
    return GuiConfig(
        username=self._var_user.get().strip(),
        password=self._var_pwd.get(),
        default_jql=self._var_jql.get().strip() or GuiConfig.default_jql,
        last_username=self._var_user.get().strip(),
    )
```

- [ ] **Step 5: 修改 _on_connect 里的 service dict**

在两处 `_cfg_to_dict(cfg)` 调用之前，需要保证 `_cfg_to_dict` 函数也匹配新的 GuiConfig 字段。检查 `views/credentials_view.py` 文件顶部的 `_cfg_to_dict`：

```python
def _cfg_to_dict(cfg: GuiConfig) -> dict:
    return {
        "jira_url": cfg.jira_url,
        "username": cfg.username,
        "password": cfg.password,
        "token": cfg.token,
        "verify_ssl": cfg.verify_ssl,
    }
```

替换为：
```python
def _cfg_to_dict(cfg: GuiConfig) -> dict:
    return {
        "username": cfg.username,
        "password": cfg.password,
    }
```

- [ ] **Step 6: 跑 GUI smoke test**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -c "import sys; sys.path.insert(0, '.'); import tkinter as tk; root = tk.Tk(); root.withdraw(); from tools.jira_worklog_gui.views.credentials_view import CredentialsView; v = CredentialsView(root); v.pack(); root.destroy(); print('OK')"`
Expected: `OK`

- [ ] **Step 7: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/views/credentials_view.py
git commit -m "feat(credentials): drop URL/Token inputs, hardcoded server"
```

---

## Task 6: 重命名 issue_picker.py 为 task_summary.py，类名同步

**Files:**
- Rename: `tools/jira_worklog_gui/views/issue_picker.py` → `tools/jira_worklog_gui/views/task_summary.py`
- Modify: `tools/jira_worklog_gui/views/__init__.py`

- [ ] **Step 1: git mv 重命名**

```bash
cd "D:/Code/IP_Jira_Mnager" && git mv tools/jira_worklog_gui/views/issue_picker.py tools/jira_worklog_gui/views/task_summary.py
```

- [ ] **Step 2: 修改新文件内的类名**

在 `tools/jira_worklog_gui/views/task_summary.py` 中：
- 将 `class IssuePickerView` 改为 `class TaskSummaryView`
- 将 `EPIC_TYPES = {"Epic"}` 之后的 docstring 改为「任务汇总：三段堆叠」
- 保留所有现有的内部逻辑

- [ ] **Step 3: 更新 views/__init__.py**

将现有：
```python
from .credentials_view import CredentialsView
from .issue_picker import IssuePickerView
from .log_entry import LogEntryView
from .today_log import TodayLogView

__all__ = ["CredentialsView", "IssuePickerView", "LogEntryView", "TodayLogView"]
```

替换为：
```python
from .credentials_view import CredentialsView
from .task_summary import TaskSummaryView
from .log_entry import LogEntryView
from .today_log import TodayLogView

__all__ = ["CredentialsView", "TaskSummaryView", "LogEntryView", "TodayLogView"]
```

- [ ] **Step 4: smoke test**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -c "import sys; sys.path.insert(0, '.'); import tkinter as tk; root = tk.Tk(); root.withdraw(); from tools.jira_worklog_gui.views import TaskSummaryView; v = TaskSummaryView(root, service=None); v.pack(); root.destroy(); print('OK')"`
Expected: `OK`

- [ ] **Step 5: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/views/
git commit -m "refactor(views): rename IssuePickerView -> TaskSummaryView"
```

---

## Task 7: TaskSummaryView 改造为三段堆叠布局

**Files:**
- Modify: `tools/jira_worklog_gui/views/task_summary.py`（完整重写）

- [ ] **Step 1: 替换整个文件**

完整覆盖 `tools/jira_worklog_gui/views/task_summary.py`，新内容：

```python
"""任务汇总 Tab：3 段堆叠（我的任务 / IPPUB / 自定义 JQL）。"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
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
                 **kw):
        super().__init__(master, text=title, padding=8, **kw)
        self.service = service
        self._on_issue_selected = on_issue_selected
        self._hierarchy: Dict[str, Any] = {"epics": [], "orphans": []}
        self._tree_iid_to_issue: Dict[str, Dict[str, Any]] = {}

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        if preset_jql is not None:
            self._jql_text = None
            ttk.Button(top, text="刷新", command=self._on_query).pack(side="right", padx=2)
            self._auto_query_jql = preset_jql
        else:
            self._jql_text = tk.StringVar()
            ttk.Entry(top, textvariable=self._jql_text).pack(side="left", fill="x", expand=True, padx=2)
            ttk.Button(top, text="查询", command=self._on_query).pack(side="right", padx=2)
            self._auto_query_jql = None

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
        if not self.service:
            self._set_status("未连接", error=True)
            return
        jql = self._auto_query_jql or (self._jql_text.get().strip() if self._jql_text else "")
        if not jql:
            self._set_status("JQL 为空", error=True)
            return
        self._set_status("查询中…")

        def worker():
            try:
                data = self.service.search_issues_hierarchical(jql)
                self.after(0, lambda: self._on_query_done(data, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_query_done(None, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_query_done(self, data, error):
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
        if self._on_issue_selected:
            issue = self.get_selected_issue()
            if issue:
                self._on_issue_selected(issue)


class TaskSummaryView(ttk.Frame):
    """任务汇总：三段堆叠（我的任务 / IPPUB / 自定义 JQL）。"""

    def __init__(self, master, service: Optional[JiraService],
                 on_issue_selected: Optional[Callable[[Dict[str, Any]], None]] = None,
                 **kw):
        super().__init__(master, padding=8, **kw)
        self._service = service
        self._on_issue_selected = on_issue_selected
        self._selected_issue: Optional[Dict[str, Any]] = None

        self._section_my = _SummarySection(
            self, "📌 分配给我的任务（未完成，排除缺陷）",
            service=service, preset_jql=MY_TASKS_JQL,
            on_issue_selected=self._on_internal_select,
        )
        self._section_my.pack(fill="both", expand=True, pady=(0, 6))

        self._section_ipub = _SummarySection(
            self, "🏷️ IPPUB 项目任务（排除缺陷）",
            service=service, preset_jql=IPPUB_JQL,
            on_issue_selected=self._on_internal_select,
        )
        self._section_ipub.pack(fill="both", expand=True, pady=(0, 6))

        self._section_custom = _SummarySection(
            self, "🔍 自定义 JQL",
            service=service, preset_jql=None,
            on_issue_selected=self._on_internal_select,
        )
        self._section_custom.pack(fill="both", expand=True, pady=(0, 6))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x")
        self._status_label = ttk.Label(bottom, text="")
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
        self._btn_use.configure(state="normal")
        self._status_label.configure(text=f"已选 {issue.get('key','')} — {issue.get('summary','')}")

    def _on_use(self):
        if not self._selected_issue or not self._on_issue_selected:
            return
        self._on_issue_selected(self._selected_issue)
```

- [ ] **Step 2: smoke test**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -c "import sys; sys.path.insert(0, '.'); import tkinter as tk; root = tk.Tk(); root.withdraw(); from tools.jira_worklog_gui.views import TaskSummaryView; v = TaskSummaryView(root, service=None, on_issue_selected=lambda x: print('picked:', x.get('key'))); v.pack(); root.destroy(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/views/task_summary.py
git commit -m "feat(summary): three stacked sections (mine / IPPUB / custom JQL)"
```

---

## Task 8: log_entry 删除剩余估算 + 加快捷按钮

**Files:**
- Modify: `tools/jira_worklog_gui/views/log_entry.py`

- [ ] **Step 1: 删 `_var_adjust` 初始化**

在 `__init__` 中：
```python
self._var_started = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
self._var_adjust = tk.StringVar(value="leave")
```

替换为：
```python
self._var_started = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
# adjust_estimate 永远是 leave，不再让 UI 选择
```

- [ ] **Step 2: 在 imports 区域加 accumulate_duration 导入**

在 `from ..widgets import DurationEntry` 后追加：
```python
from ..widgets import DurationEntry, accumulate_duration
```

- [ ] **Step 3: 重构耗时行布局（加 5 按钮）**

找到耗时行：
```python
dur_frame = ttk.Frame(self)
dur_frame.grid(row=row, column=1, sticky="w", pady=4)
self._duration_entry = DurationEntry(dur_frame, textvariable=self._var_duration, width=15)
self._duration_entry.pack(side="left")
ttk.Label(dur_frame, text="支持 1h30m / 90m / 1.5h / 5400s / 2d",
          foreground="#888").pack(side="left", padx=8)
```

替换为：
```python
dur_frame = ttk.Frame(self)
dur_frame.grid(row=row, column=1, sticky="w", pady=4)
self._duration_entry = DurationEntry(dur_frame, textvariable=self._var_duration, width=15)
self._duration_entry.pack(side="left")
for label, secs in [("+30min", 30 * 60), ("+1h", 3600), ("+2h", 2 * 3600),
                    ("+4h", 4 * 3600), ("+8h", 8 * 3600)]:
    ttk.Button(dur_frame, text=label, width=6,
               command=lambda s=secs: self._on_quick_duration(s)).pack(side="left", padx=2)
```

- [ ] **Step 4: 删除"剩余估算"行**

找到：
```python
# 调整估算
row += 1
ttk.Label(self, text="剩余估算").grid(row=row, column=0, sticky="w", pady=4)
adj_frame = ttk.Frame(self)
adj_frame.grid(row=row, column=1, sticky="w", pady=4)
for val, label in [("leave", "不调整（默认）"), ("auto", "自动扣减"), ("new", "设为新值")]:
    ttk.Radiobutton(adj_frame, text=label, variable=self._var_adjust,
                    value=val).pack(side="left", padx=4)
```

整个删除。

- [ ] **Step 5: 加 `_on_quick_duration` 方法**

在 `_parse_started` 方法之前追加：

```python
def _on_quick_duration(self, add_seconds: int):
    """快捷按钮：把 add_seconds 累加到当前输入框。"""
    current = self._var_duration.get().strip()
    try:
        new_text = accumulate_duration(current, add_seconds)
    except ValueError as e:
        messagebox.showwarning("输入有误", f"当前耗时 '{current}' 无法解析，请先修正或清空。")
        return
    self._var_duration.set(new_text)
    self._duration_entry._refresh_style()
```

- [ ] **Step 6: 修改 _submit 去掉 adjust_estimate 参数**

将现有：
```python
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
```

替换为：
```python
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
```

- [ ] **Step 7: smoke test**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -c "import sys; sys.path.insert(0, '.'); import tkinter as tk; root = tk.Tk(); root.withdraw(); from tools.jira_worklog_gui.views import LogEntryView; v = LogEntryView(root, service=None); v.pack(); v.set_issue({'key':'X-1','summary':'test'}); root.destroy(); print('OK')"`
Expected: `OK`

- [ ] **Step 8: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/views/log_entry.py
git commit -m "feat(log-entry): add quick duration buttons, drop estimate adjust"
```

---

## Task 9: app.py 同步改名 + 验证整体启动

**Files:**
- Modify: `tools/jira_worklog_gui/app.py`

- [ ] **Step 1: 改 imports**

找到：
```python
from .views import CredentialsView, IssuePickerView, LogEntryView, TodayLogView
```

替换为：
```python
from .views import CredentialsView, TaskSummaryView, LogEntryView, TodayLogView
```

- [ ] **Step 2: 改构造与变量名**

找到：
```python
        self.cred_view = CredentialsView(self.nb, on_connected=self._on_connected)
        self.nb.add(self.cred_view, text="① 凭据配置")

        self.picker_view = IssuePickerView(
            self.nb, service=None, on_issue_selected=self._on_issue_picked
        )
        self.nb.add(self.picker_view, text="② Issue 浏览器")

        self.entry_view = LogEntryView(
            self.nb, service=None, on_log_added=self._refresh_today
        )
        self.nb.add(self.entry_view, text="③ 快速登记")

        self.today_view = TodayLogView(self.nb, service=None)
        self.nb.add(self.today_view, text="④ 当天日志")
```

替换为：
```python
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
        self.nb.add(self.today_view, text="④ 当天日志")
```

- [ ] **Step 3: 改 `_on_connected` 里的 setter**

找到：
```python
        self.picker_view.set_service(service)
        self.picker_view.set_default_jql(self._cfg.default_jql)
        self.entry_view.set_service(service)
        self.today_view.set_service(service)
```

替换为：
```python
        self.task_summary_view.set_service(service)
        self.entry_view.set_service(service)
        self.today_view.set_service(service)
```

- [ ] **Step 4: 整 app 端到端 smoke test**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -c "
import sys; sys.path.insert(0, '.')
from tools.jira_worklog_gui.app import App
app = App()
print('App 启动成功')
print('Tab 数量:', app.nb.index('end'))
for i in range(app.nb.index('end')):
    print(f'  Tab {i}:', app.nb.tab(i, 'text'))
app.destroy()
print('OK')
"`
Expected:
```
App 启动成功
Tab 数量: 4
  Tab 0: ① 凭据配置
  Tab 1: ② 任务汇总
  Tab 2: ③ 快速登记
  Tab 3: ④ 当天日志
OK
```

- [ ] **Step 5: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/app.py
git commit -m "refactor(app): rename to TaskSummaryView, update tab label"
```

---

## Task 10: 全量测试 + 更新 README

**Files:**
- Modify: `tools/jira_worklog_gui/README.md`

- [ ] **Step 1: 跑全量 unit 测试**

Run: `cd "D:/Code/IP_Jira_Mnager" && python -m pytest tests/test_utils.py tests/test_entity.py tests/test_connection.py tests/test_query.py tests/test_confluence.py tests/test_duration.py tests/test_jira_service.py tests/test_worklog_write.py`
Expected: 全部 PASS（约 242 个用例：原 230 + duration 新增 12 + service 新增 2）

- [ ] **Step 2: 更新 README "功能" 章节**

找到 README 中：
```
2. **Issue 浏览器** — 输入 JQL 查询，按 Epic → 子任务树形展示。选中叶子节点后点击「用此 issue 登记 →」跳到登记 Tab。
```

替换为：
```
2. **任务汇总** — 三段堆叠：
   - 📌 **我的任务**（未完成、排除缺陷）自动按 JQL `assignee = currentUser() AND issuetype != "问题缺陷" AND issuetype != "Bug" AND statusCategory != Done` 查询
   - 🏷️ **IPPUB 任务** 自动按 JQL `project = "IPPUB" AND issuetype != "问题缺陷" AND issuetype != "Bug"` 查询
   - 🔍 **自定义 JQL** 自由输入并查询
   每段独立 Treeview、独立刷新按钮。选中任一段的叶子后，底部「用此 issue 登记 →」按钮启用。
```

- [ ] **Step 3: 更新 README "配置存储" 章节**

找到：
```
- 位置：`~/.jira_worklog_gui/config.json`
- 优先级：**环境变量 `JIRA_URL/USERNAME/PASSWORD/TOKEN` > JSON 配置文件**
```

替换为：
```
- 位置：`~/.jira_worklog_gui/config.json`
- **URL 硬编码**：`https://idisplayvision.com/jira/`（写在 `config_store.HARDCODED_JIRA_URL`，UI 不暴露）
- 优先级：**环境变量 `JIRA_USERNAME/PASSWORD` > JSON 配置文件**
```

- [ ] **Step 4: 提交**

```bash
cd "D:/Code/IP_Jira_Mnager" && git add tools/jira_worklog_gui/README.md
git commit -m "docs(gui): update README for v2 tweaks"
```

---

## 自审

**1. Spec 覆盖检查**：

| Spec 需求 | 对应 Task |
|---|---|
| 1. URL 硬编码 | Task 2 (config_store) + Task 3 (jira_service connect) + Task 5 (UI 删除输入) |
| 2. 取消 Token | Task 2 (config_store) + Task 3 (jira_service) + Task 5 (UI) |
| 3. Issue 浏览器改名为任务汇总 | Task 6 (rename) + Task 7 (重写) + Task 9 (app.py) |
| 4a. 我的任务 JQL | Task 3 (MY_TASKS_JQL 常量) + Task 7 (段 1 自动加载) |
| 4b. IPPUB JQL | Task 3 (IPPUB_JQL 常量) + Task 7 (段 2 自动加载) |
| 4c. 自定义 JQL | Task 7 (段 3 用户输入) |
| 5. 耗时快捷按钮累加 | Task 1 (accumulate_duration) + Task 8 (UI) |
| 6. 取消剩余估算 | Task 8 (UI 删除 + service 默认 leave) |
| 7. 测试 JQL 常量 | Task 4 (新增 TestJqlConstants) |
| 8. 测试 accumulate_duration | Task 1 (TestAccumulateDuration) |

✅ 全部覆盖。

**2. 占位符扫描**：未发现 `TBD` / `TODO` / "类似 Task N" 等。

**3. 类型一致性**：
- `TaskSummaryView.__init__` 签名（service, on_issue_selected）在 Task 6/7/9 一致
- `JiraService.add_worklog` 不再传 `adjust_estimate`，对应 Task 3 service 删 token、Task 8 删 UI 参数
- `_SummarySection.set_service` 在 Task 7 定义，Task 7 自己使用；无跨任务签名漂移

✅ 一致。