# Vendor 上游 IP_Jira_Mnager 库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把上游 `IP_Jira_Mnager` 仓库本项目实际用到的源码（~1100 行）完整复制进本仓 `src/jira_worklog_gui/_vendor/`，去除 `pyproject.toml` 的 Git 依赖，让 `pip install -e .` 后不再需要上游仓存在。

**Architecture:** Vendor 目录作为 `_vendor` 私有子包（带下划线表明"内部依赖"）。原 `from src.jira.connection.client import JiraConnection` 的导入路径失效，改为 `from .._vendor.jira.connection.client import JiraConnection`。vendor 内部的相对 import（`from ..utils import get_field_value`）保持不变，因为相对 import 不依赖包名。`pyproject.toml` 移除 `ip-jira-manager` Git 依赖，保留 `jira>=3.5.0`（vendor 内部仍 import 底层 jira 库）。

**Tech Stack:** Python 3.8+ / Tkinter / 第三方库 jira (vendor 内调) / Pytest

---

## 文件结构

**新增（vendor 目录，13 个文件）：**

```
src/jira_worklog_gui/_vendor/
├── __init__.py                          # 空，标识子包
├── common/
│   ├── __init__.py                      # 空
│   └── decorators.py                    # require_connection 工厂
└── jira/
    ├── __init__.py                      # 复制 IP_Jira_Mnager/src/jira/__init__.py
    ├── utils.py                         # get_field_value + parse_jira_datetime
    ├── connection/
    │   ├── __init__.py                  # 复制（仅暴露异常类）
    │   ├── client.py                    # JiraConnection 主类
    │   ├── exceptions.py                # 3 个异常类
    │   ├── _decorators.py               # 已用 JiraConnectionError 预设
    │   ├── _issue_ops.py                # _IssueOpsMixin
    │   ├── _metadata.py                 # _MetadataMixin
    │   ├── _plugin.py                   # _PluginMixin
    │   └── _worklog_write.py            # _WorklogWriteMixin
    └── query/
        ├── __init__.py                  # 复制（只导出本项目用到的：search_all_issues + get_user_worklogs）
        ├── search.py                    # search_all_issues
        └── user_activity.py             # get_user_worklogs
```

**修改：**

- `pyproject.toml:11-14` — 删 `ip-jira-manager` Git 依赖
- `src/jira_worklog_gui/jira_service.py:21-80` — 删 `_bootstrap_ip_jira_manager_src()` 整个函数（72-79 行）；改 import 路径
- `src/jira_worklog_gui/__init__.py` — 顶层包初始化（如有变化需保持兼容）
- `README.md:5-15` — 启动步骤移除"先装底层库"
- `AGENTS.md` — 移除上游仓相关段落，新增 vendor 架构说明
- `docs/AGENT_CONTEXT.md` — §2 项目沿革补充"v3: vendor 化"；§3 架构图更新；§9 删除"与上游仓库的关系"

**测试：**

- `tests/test_vendor_smoke.py` — 新增：验证 vendor 包 import + JiraConnection 类存在 + 不依赖 sys.path hack
- 现有 `tests/test_jira_service.py`、`tests/test_duration.py` — 不变（只 mock 不调真 JIRA）

---

## 已知关键事实（用于所有任务）

1. **vendor 源码全部来自**：`D:\Code\IP_Jira_Mnager`（Git 仓 main 分支，最新 commit 2026-07-01）
2. **本项目实际 import 的上游符号**（来自 `jira_service.py:74-80`）：
   - `src.jira.connection.client.JiraConnection`
   - `src.jira.connection.exceptions.{JiraConnectionError, JiraAuthError, JiraRequestError}`
   - `src.jira.query.search_all_issues`
   - `src.jira.query.user_activity.get_user_worklogs`
3. **vendor 内部相对 import 保持不变**：`from ..utils import ...` 在 vendor 目录里依然指向 `src/jira_worklog_gui/_vendor/jira/utils.py`，不需要改
4. **`src.common.decorators` 只有 1 个函数**（`require_connection`），被 `_decorators.py` 用 `from ...common.decorators import require_connection` 引用
5. **`src/jira/query/__init__.py` 完整复制后会失败**——它 `from .status_query import ...` 等引入了本项目用不到的模块（status_query、workload、hierarchy、planned_vs_actual）。**必须在 vendor 时裁剪 `__init__.py`**，只导出 `search_all_issues` + `get_user_worklogs`
6. **`user_activity.py` 第 47 行调 `conn.search_issues_raw`** — 这是 `_IssueOpsMixin` 提供的方法，必须 vendor 该 mixin

---

## Task 1: vendor 目录骨架 + common.decorators

**Files:**
- Create: `src/jira_worklog_gui/_vendor/__init__.py`
- Create: `src/jira_worklog_gui/_vendor/common/__init__.py`
- Create: `src/jira_worklog_gui/_vendor/common/decorators.py`

- [ ] **Step 1: 创建空 vendor 标识文件**

Create `src/jira_worklog_gui/_vendor/__init__.py`:
```python
"""内部 vendor 依赖：完整复制自上游 IP_Jira_Mnager 仓库。

此目录存放本项目实际用到的上游库代码。
代码来源：D:\\Code\\IP_Jira_Mnager（commit 2026-07-01）

不要修改 vendor 内的代码——如需改动请明确标注并在注释里说明原因。
未来如需同步上游，需要手动复制并解决冲突（本项目选择断联模式）。
"""
```

- [ ] **Step 2: 创建 vendor/common 子包**

Create `src/jira_worklog_gui/_vendor/common/__init__.py`:
```python
"""common 子包占位。"""
```

Create `src/jira_worklog_gui/_vendor/common/decorators.py`（**逐字复制**自 `D:\Code\IP_Jira_Mnager\src\common\decorators.py`）:
```python
"""
Shared decorators for connection management.
"""
from functools import wraps


def require_connection(error_class, message="未连接到服务器"):
    """Factory: returns a decorator that checks self.is_connected."""

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.is_connected:
                raise error_class(message)
            return method(self, *args, **kwargs)

        return wrapper

    return decorator
```

- [ ] **Step 3: 验证 vendor 子包可 import**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.common.decorators import require_connection
print('require_connection OK:', require_connection)
"
```
Expected: `require_connection OK: <function require_connection at 0x...>`

- [ ] **Step 4: Commit**

```bash
git add src/jira_worklog_gui/_vendor/__init__.py src/jira_worklog_gui/_vendor/common/
git commit -m "feat(vendor): scaffold _vendor/ + copy common.decorators"
```

---

## Task 2: vendor jira/utils.py + jira 包 init

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/__init__.py`
- Create: `src/jira_worklog_gui/_vendor/jira/utils.py`

- [ ] **Step 1: 复制 jira 包 init**

从 `D:\Code\IP_Jira_Mnager\src\jira\__init__.py` 复制整文件到 `src/jira_worklog_gui/_vendor/jira/__init__.py`。该文件 82 行，只声明 docstring + 可能有的模块级 import。

先读取源文件：
```bash
cd D:/Code/IP_Jira_Mnager && cat src/jira/__init__.py
```

将完整内容粘贴到 `src/jira_worklog_gui/_vendor/jira/__init__.py`，**不做任何修改**。

- [ ] **Step 2: 复制 utils.py**

从 `D:\Code\IP_Jira_Mnager\src\jira\utils.py` 复制整文件（255 行）到 `src/jira_worklog_gui/_vendor/jira/utils.py`，**不做任何修改**。

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/utils.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/utils.py
```

- [ ] **Step 3: 验证 utils 函数可 import**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.utils import get_field_value, parse_jira_datetime
print('utils OK:', get_field_value, parse_jira_datetime)
"
```
Expected: `utils OK: <function get_field_value at 0x...> <function parse_jira_datetime at 0x...>`

- [ ] **Step 4: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/__init__.py src/jira_worklog_gui/_vendor/jira/utils.py
git commit -m "feat(vendor): copy jira/__init__.py + jira/utils.py"
```

---

## Task 3: vendor jira/connection/exceptions.py

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/connection/__init__.py`
- Create: `src/jira_worklog_gui/_vendor/jira/connection/exceptions.py`

- [ ] **Step 1: 创建 connection 子包 init**

Create `src/jira_worklog_gui/_vendor/jira/connection/__init__.py`:
```python
"""jira.connection 子包：JiraConnection 主类 + 异常类 + 5 个 mixin。"""
from .exceptions import JiraConnectionError, JiraAuthError, JiraRequestError

__all__ = ['JiraConnectionError', 'JiraAuthError', 'JiraRequestError', 'JiraConnection']
```

（先放 `JiraConnection` 在 __all__ 里，但实际 import 留到 client.py 装好后——Task 7 之后再调整。此处先只导入异常，避免循环 import。）

- [ ] **Step 2: 复制 exceptions.py**

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/connection/exceptions.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/connection/exceptions.py
```

- [ ] **Step 3: 验证异常类**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.connection.exceptions import JiraConnectionError, JiraAuthError, JiraRequestError
print('exceptions OK:', JiraConnectionError, JiraAuthError, JiraRequestError)
"
```
Expected: 三个类对象打印出来。

- [ ] **Step 4: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/connection/__init__.py src/jira_worklog_gui/_vendor/jira/connection/exceptions.py
git commit -m "feat(vendor): copy jira.connection.exceptions"
```

---

## Task 4: vendor jira/connection/_decorators.py

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/connection/_decorators.py`

- [ ] **Step 1: 复制 _decorators.py（注意改 import）**

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/connection/_decorators.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/connection/_decorators.py
```

**修改 import**：源文件用 `from ...common.decorators import require_connection as _require_connection`（指向上游 `src/common/`）。vendor 后 `...common.decorators` 实际指向 `src/jira_worklog_gui/_vendor/common/decorators`，相对 import 路径不变——**不需要改**。

但相对 import 生效要求 `_vendor/common/` 是 Python 可发现的包。由于我们已经创建了 `src/jira_worklog_gui/_vendor/__init__.py` 和 `src/jira_worklog_gui/_vendor/common/__init__.py`，`_vendor` 已经是 package，`_vendor.common.decorators` 可解析。从 `_vendor.jira.connection._decorators` 出发，`...common.decorators` 解析为 `_vendor.common.decorators` ✓。

- [ ] **Step 2: 验证 require_connection 工厂**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.connection._decorators import require_connection
from jira_worklog_gui._vendor.jira.connection.exceptions import JiraConnectionError
decorator = require_connection(JiraConnectionError, 'test msg')
print('decorator factory OK:', decorator)
"
```
Expected: `decorator factory OK: <function require_connection.<locals>.decorator at 0x...>`

- [ ] **Step 3: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/connection/_decorators.py
git commit -m "feat(vendor): copy jira.connection._decorators"
```

---

## Task 5: vendor 4 个 mixin

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/connection/_issue_ops.py`
- Create: `src/jira_worklog_gui/_vendor/jira/connection/_metadata.py`
- Create: `src/jira_worklog_gui/_vendor/jira/connection/_plugin.py`
- Create: `src/jira_worklog_gui/_vendor/jira/connection/_worklog_write.py`

- [ ] **Step 1: 复制 4 个 mixin 文件**

```bash
SRC=D:/Code/IP_Jira_Mnager/src/jira/connection
DST=D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/connection
cp $SRC/_issue_ops.py $DST/_issue_ops.py
cp $SRC/_metadata.py $DST/_metadata.py
cp $SRC/_plugin.py $DST/_plugin.py
cp $SRC/_worklog_write.py $DST/_worklog_write.py
```

**不改 import**：每个 mixin 的 `from ._decorators import require_connection` / `from .exceptions import ...` 在 vendor 里依然指向 vendor 内的同目录文件 ✓。`_worklog_write.py` 第 20 行 `from jira.exceptions import JIRAError` 是底层 jira 库（PyPI 包），不动 ✓。

- [ ] **Step 2: 验证 4 个 mixin 语法 OK**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.connection._issue_ops import _IssueOpsMixin
from jira_worklog_gui._vendor.jira.connection._metadata import _MetadataMixin
from jira_worklog_gui._vendor.jira.connection._plugin import _PluginMixin
from jira_worklog_gui._vendor.jira.connection._worklog_write import _WorklogWriteMixin
print('4 mixins OK:', _IssueOpsMixin, _MetadataMixin, _PluginMixin, _WorklogWriteMixin)
"
```
Expected: 四个类对象打印出来。

- [ ] **Step 3: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/connection/_issue_ops.py \
        src/jira_worklog_gui/_vendor/jira/connection/_metadata.py \
        src/jira_worklog_gui/_vendor/jira/connection/_plugin.py \
        src/jira_worklog_gui/_vendor/jira/connection/_worklog_write.py
git commit -m "feat(vendor): copy 4 connection mixins"
```

---

## Task 6: vendor jira/connection/client.py (JiraConnection 主类)

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/connection/client.py`

- [ ] **Step 1: 复制 client.py**

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/connection/client.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/connection/client.py
```

**不改 import**：`from ..utils import get_field_value` 在 vendor 里指向 `_vendor/jira/utils.py` ✓。`from ._decorators import require_connection` 等指向 vendor 同目录 ✓。`from jira import JIRA` 指向 PyPI 包 ✓。

- [ ] **Step 2: 验证 JiraConnection 类**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.connection.client import JiraConnection
print('JiraConnection OK:', JiraConnection)
print('MRO:', [c.__name__ for c in JiraConnection.__mro__])
"
```
Expected: `JiraConnection OK: <class ...>` + MRO 包含 `_IssueOpsMixin, _MetadataMixin, _PluginMixin, _WorklogWriteMixin, object`。

- [ ] **Step 3: 更新 connection/__init__.py 让 JiraConnection 可导入**

编辑 `src/jira_worklog_gui/_vendor/jira/connection/__init__.py`，改为：
```python
"""jira.connection 子包：JiraConnection 主类 + 异常类 + 5 个 mixin。"""
from .exceptions import JiraConnectionError, JiraAuthError, JiraRequestError
from .client import JiraConnection

__all__ = ['JiraConnectionError', 'JiraAuthError', 'JiraRequestError', 'JiraConnection']
```

验证：
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.connection import JiraConnection, JiraConnectionError
print('full connection OK:', JiraConnection, JiraConnectionError)
"
```
Expected: 两个类对象。

- [ ] **Step 4: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/connection/client.py src/jira_worklog_gui/_vendor/jira/connection/__init__.py
git commit -m "feat(vendor): copy JiraConnection client + expose via __init__"
```

---

## Task 7: vendor jira/query/ (裁剪版)

**Files:**
- Create: `src/jira_worklog_gui/_vendor/jira/query/__init__.py`
- Create: `src/jira_worklog_gui/_vendor/jira/query/search.py`
- Create: `src/jira_worklog_gui/_vendor/jira/query/user_activity.py`

- [ ] **Step 1: 复制 search.py**

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/query/search.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/query/search.py
```

- [ ] **Step 2: 复制 user_activity.py**

```bash
cp D:/Code/IP_Jira_Mnager/src/jira/query/user_activity.py D:/Code/jira-worklog-gui/src/jira_worklog_gui/_vendor/jira/query/user_activity.py
```

**不改 import**：第 18 行 `from ..connection import JiraConnection` 指向 `_vendor/jira/connection` ✓。第 19 行 `from ..utils import parse_jira_datetime` 指向 `_vendor/jira/utils` ✓。

**保留全部函数**（包括 CLI 的 `format_worklog_output` / `save_to_json` / `main`）——虽然本项目只调 `get_user_worklogs`，但裁剪成本 > 收益，且代码量小。

- [ ] **Step 3: 写裁剪版的 query/__init__.py**

**不要直接复制**上游的 `src/jira/query/__init__.py`——它会 import status_query / workload / hierarchy / planned_vs_actual 等本项目未 vendor 的模块，导致 ImportError。

Create `src/jira_worklog_gui/_vendor/jira/query/__init__.py`:
```python
"""jira.query 子包（本项目裁剪版）。

仅暴露本项目实际用到的查询函数：
- search_all_issues：分页 JQL 搜索
- get_user_worklogs：用户工作日志查询

上游 IP_Jira_Mnager 的 status_query / workload / hierarchy / planned_vs_actual
等模块未 vendor，因本项目不依赖它们。
"""
from .search import search_all_issues
from .user_activity import get_user_worklogs

__all__ = ['search_all_issues', 'get_user_worklogs']
```

- [ ] **Step 4: 验证 query 子包**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
from jira_worklog_gui._vendor.jira.query import search_all_issues, get_user_worklogs
print('query OK:', search_all_issues, get_user_worklogs)
"
```
Expected: 两个函数对象。

- [ ] **Step 5: Commit**

```bash
git add src/jira_worklog_gui/_vendor/jira/query/
git commit -m "feat(vendor): copy jira.query (search + user_activity, trimmed)"
```

---

## Task 8: 写 vendor 烟雾测试

**Files:**
- Create: `tests/test_vendor_smoke.py`

- [ ] **Step 1: 写测试文件**

Create `tests/test_vendor_smoke.py`:
```python
"""Vendor 烟雾测试：验证 _vendor 子包导入完整、不依赖 sys.path hack。

不依赖真 JIRA 服务器——只验证 import 链路与类签名。
"""
import pytest


def test_vendor_common_decorators_importable():
    from jira_worklog_gui._vendor.common.decorators import require_connection
    assert callable(require_connection)


def test_vendor_jira_utils_importable():
    from jira_worklog_gui._vendor.jira.utils import get_field_value, parse_jira_datetime
    assert callable(get_field_value)
    assert callable(parse_jira_datetime)


def test_vendor_jira_connection_exceptions_importable():
    from jira_worklog_gui._vendor.jira.connection.exceptions import (
        JiraConnectionError, JiraAuthError, JiraRequestError,
    )
    assert issubclass(JiraConnectionError, Exception)
    assert issubclass(JiraAuthError, Exception)
    assert issubclass(JiraRequestError, Exception)


def test_vendor_jira_connection_jira_connection_importable():
    from jira_worklog_gui._vendor.jira.connection import JiraConnection
    # JiraConnection 是 mixin 组合类
    mro_names = [c.__name__ for c in JiraConnection.__mro__]
    assert "_IssueOpsMixin" in mro_names
    assert "_MetadataMixin" in mro_names
    assert "_PluginMixin" in mro_names
    assert "_WorklogWriteMixin" in mro_names


def test_vendor_jira_query_importable():
    from jira_worklog_gui._vendor.jira.query import search_all_issues, get_user_worklogs
    assert callable(search_all_issues)
    assert callable(get_user_worklogs)


def test_vendor_does_not_depend_on_ip_jira_manager_metadata():
    """Vendor 之后，import jira_worklog_gui 不应触发 ip-jira-manager 包的 dist-info 探测。

    删掉 jira_service.py 里的 _bootstrap_ip_jira_manager_src() 后，这个测试是回归保护。
    """
    # ip-jira-manager 包可能根本未安装；vendor 后不应再依赖
    try:
        import importlib
        importlib.import_module("ip_jira_manager")
        # 如果装了，只检查 jira_worklog_gui._vendor 子模块是否独立可用
        from jira_worklog_gui._vendor.jira.connection import JiraConnection
        assert JiraConnection is not None
    except ImportError:
        # ip-jira-manager 不存在才是理想状态
        from jira_worklog_gui._vendor.jira.connection import JiraConnection
        assert JiraConnection is not None
```

- [ ] **Step 2: 运行测试**

Run:
```bash
cd D:/Code/jira-worklog-gui && pytest tests/test_vendor_smoke.py -v
```
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_vendor_smoke.py
git commit -m "test(vendor): smoke test for _vendor import chain"
```

---

## Task 9: 改 jira_service.py 指向 vendor + 删除 bootstrap 函数

**Files:**
- Modify: `src/jira_worklog_gui/jira_service.py:21-80`

- [ ] **Step 1: 删除 `_bootstrap_ip_jira_manager_src()` 函数**

打开 `src/jira_worklog_gui/jira_service.py`，删除 **第 1-72 行**（从 `"""..."""` docstring 起，到 `_bootstrap_ip_jira_manager_src()` 函数结束 + `_bootstrap_ip_jira_manager_src()` 调用行）。新文件从原第 73 行（空行）开始 —— 实际上更干净的做法是 **保留 docstring + 删掉整个函数 + 调用**，并重写 import 段。

新的 `jira_service.py` 第 1-25 行如下：

```python
"""JiraConnection 的薄封装，给 GUI 层使用。

设计原则：
- 不在 import 时建立连接（懒加载），让 GUI 启动不依赖网络
- 所有方法要么返回数据，要么抛 JiraConnectionError / JiraAuthError / JiraRequestError，
  让调用方负责错误提示
- 解析 JIRA 原始 Issue 对象为简单 dict，便于 Treeview 渲染

依赖说明：
- JiraConnection 等上游库代码已 vendor 到本仓 _vendor/jira/ 下
  （断联模式，未来不自动同步 D:\\Code\\IP_Jira_Mnager）
- 仍依赖 PyPI 的 `jira` 库（vendor 内部通过 `from jira import JIRA` 调底层）
"""
from __future__ import annotations

import re
import sys  # noqa: F401  保留兼容性（被删的 bootstrap 也用过 sys）
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
```

（保留 `sys` import 是为了避免其他模块 import 失败——其实没有别处引用，可以一并删。删掉它：）

**修正**：从 import 块里 **删除** `import sys` 和 `from pathlib import Path`（这俩只原 bootstrap 函数用过，删函数后无用）。最终 import 块：

```python
from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
```

- [ ] **Step 2: 改 4 个 import 指向 vendor**

修改原 `jira_service.py` 第 74-80 行（删除 bootstrap 后位置变为第 8-13 行附近）：

**原：**
```python
from src.jira.connection.client import JiraConnection  # noqa: E402
from src.jira.connection.exceptions import (  # noqa: E402
    JiraConnectionError,
    JiraAuthError,
    JiraRequestError,
)
from src.jira.query import search_all_issues, get_user_worklogs  # noqa: E402
```

**改为：**
```python
from ._vendor.jira.connection import (  # noqa: E402
    JiraConnection,
    JiraConnectionError,
    JiraAuthError,
    JiraRequestError,
)
from ._vendor.jira.query import search_all_issues, get_user_worklogs  # noqa: E402
```

- [ ] **Step 3: 运行现有测试，确认无回归**

Run:
```bash
cd D:/Code/jira-worklog-gui && pytest tests/ -v
```
Expected: 77 tests passed (71 现有 + 6 新增 vendor smoke)。如果没有 = 71 没动就 OK。

- [ ] **Step 4: 跑 App 烟雾测试**

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
import sys; sys.path.insert(0, 'src')
import tkinter as tk; root = tk.Tk(); root.withdraw()
from jira_worklog_gui.app import App
app = App()
print('Tab 数:', app.nb.index('end'))
app.destroy()
"
```
Expected: `Tab 数: 4`

- [ ] **Step 5: Commit**

```bash
git add src/jira_worklog_gui/jira_service.py
git commit -m "refactor(jira_service): drop IP_Jira_Mnager bootstrap, import from _vendor"
```

---

## Task 10: 改 pyproject.toml 移除 Git 依赖

**Files:**
- Modify: `pyproject.toml:11-14`

- [ ] **Step 1: 编辑 dependencies**

打开 `pyproject.toml`，**第 12 行** 删掉 `"ip-jira-manager @ git+https://gitee.com/chongfengshi/IP_Jira_Mnager.git@main",`

**原：**
```toml
dependencies = [
    "ip-jira-manager @ git+https://gitee.com/chongfengshi/IP_Jira_Mnager.git@main",
    "jira>=3.5.0",
]
```

**改为：**
```toml
dependencies = [
    "jira>=3.5.0",
]
```

- [ ] **Step 2: 验证 `pip install -e .` 在全新环境能装**

不需要真的卸载重装，**只验证 toml 解析 + 依赖列表可被 setuptools 识别**：

Run:
```bash
cd D:/Code/jira-worklog-gui && python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    cfg = tomllib.load(f)
print('deps:', cfg['project']['dependencies'])
assert 'jira>=3.5.0' in cfg['project']['dependencies']
assert not any('ip-jira-manager' in d for d in cfg['project']['dependencies'])
print('pyproject.toml OK')
"
```
Expected: `deps: ['jira>=3.5.0']` + `pyproject.toml OK`

（Python 3.11+ 才内置 tomllib；如果是 3.8-3.10 用 `tomli`：）

```bash
cd D:/Code/jira-worklog-gui && python -c "
import sys
if sys.version_info >= (3, 11):
    import tomllib as toml
else:
    import tomli as toml
with open('pyproject.toml', 'rb') as f:
    cfg = toml.load(f)
print('deps:', cfg['project']['dependencies'])
assert 'jira>=3.5.0' in cfg['project']['dependencies']
assert not any('ip-jira-manager' in d for d in cfg['project']['dependencies'])
print('pyproject.toml OK')
"
```

- [ ] **Step 3: 跑全量测试做最终验证**

Run:
```bash
cd D:/Code/jira-worklog-gui && pytest -m unit -v
```
Expected: 77 tests passed in ~0.4s.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): drop ip-jira-manager Git dep (now vendored)"
```

---

## Task 11: 更新 README.md 启动步骤

**Files:**
- Modify: `README.md:5-15`

- [ ] **Step 1: 改启动步骤**

**原 README.md 第 7-15 行：**
```markdown
## 启动

在项目根目录（`D:\Code\IP_Jira_Mnager`）：

```bash
# 1. 装依赖（项目已有）
pip install -e .

# 2. 启动 GUI
python -m tools.jira_worklog_gui
```
```

**改为：**
```markdown
## 启动

```bash
# 1. 装依赖（项目已有）
pip install -e .

# 2. 启动 GUI
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

依赖：`jira>=3.5.0`（PyPI）。上游 `IP_Jira_Mnager` 仓库的 JIRA 连接库已 vendor 到 `src/jira_worklog_gui/_vendor/`，**无需再单独 clone 上游仓库**。
```

- [ ] **Step 2: 验证 README 渲染无误**

打开 `README.md` 看一下，确认 code block 闭合、链接未断。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): drop upstream clone step, note vendored lib"
```

---

## Task 12: 更新 AGENTS.md 架构边界段

**Files:**
- Modify: `AGENTS.md` (架构边界段)

- [ ] **Step 1: 改"架构边界"小节**

打开 `AGENTS.md`，**找到"架构边界（重要）"小节**，**原内容：**
```markdown
## 架构边界（重要）

- **不要**改 `jira_service.py` 之外的 GUI 文件去直接调底层 `jira.JIRA(...)`——所有 JIRA 调用必须经 `JiraService`
- **不要**改这个仓的上游 `IP_Jira_Mnager` 库代码（在另一个仓库）。如需 `JiraConnection` 新方法，去那个仓库改
- **不要** `from tools.jira_worklog_gui import ...`——早期路径已废弃
- 新增 worklog 操作链：`view → JiraService.* → JiraConnection.* (上游库) → jira lib`
- 视图层之间**不互相 import**；跨 Tab 通信走 `App._on_issue_picked`（LogEntryView 接收 issue）
```

**改为：**
```markdown
## 架构边界（重要）

- **不要**改 `jira_service.py` 之外的 GUI 文件去直接调底层 `jira.JIRA(...)`——所有 JIRA 调用必须经 `JiraService`
- **`_vendor/` 内的代码视同第三方库**——vendor 是断联模式（不再从 `D:\Code\IP_Jira_Mnager` 自动同步），改 vendor 内的代码 = 改底层库，本项目**不应该**改它
- **不要** `from tools.jira_worklog_gui import ...`——早期路径已废弃
- 新增 worklog 操作链：`view → JiraService.* → _vendor.JiraConnection.* → jira lib (PyPI)`
- 视图层之间**不互相 import**；跨 Tab 通信走 `App._on_issue_picked`（LogEntryView 接收 issue）
```

- [ ] **Step 2: 删除"启动"小节里的上游步骤**

**原 AGENTS.md "启动"小节：**
```markdown
## 启动

```bash
# 1. 先装底层库（开发模式，必须先装）
git clone https://gitee.com/chongfengshi/IP_Jira_Mnager.git
pip install -e ./IP_Jira_Mnager

# 2. 装 GUI
pip install -e .

# 3. 运行
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

无任何第三方 GUI 依赖（tkinter 是标准库）。
```

**改为：**
```markdown
## 启动

```bash
pip install -e .
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

无任何第三方 GUI 依赖（tkinter 是标准库）。上游 JIRA 连接库已 vendor 进 `_vendor/`，无需再 clone 外部仓库。
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): update architecture boundaries for vendored lib"
```

---

## Task 13: 更新 docs/AGENT_CONTEXT.md

**Files:**
- Modify: `docs/AGENT_CONTEXT.md` (3 处：§2 沿革表、§3 架构图、§9 关系)

- [ ] **Step 1: 在 §2 沿革表里加 v3 行**

**原 §2 表格最后一行**：
```markdown
| 2026-07-02 | 独立仓库 | 用 `git subtree split` 迁出到 https://github.com/FasenChen/jira-worklog-gui，重组为 `src/jira_worklog_gui/` 标准布局 |
```

**在后面追加一行：**
```markdown
| 2026-07-03 | v3 (vendor) | 上游 `IP_Jira_Mnager` 库的 `JiraConnection` + 查询函数全部 vendor 到 `_vendor/`，去掉 `pyproject.toml` 的 Git 依赖，断联模式 |
```

- [ ] **Step 2: 在 §3 包结构图里加 _vendor 子树**

**原 §3 包结构图**：
```
jira-worklog-gui/                  # 仓库根
├── src/jira_worklog_gui/          # 顶层 Python 包
│   ├── __init__.py
│   ├── __main__.py                # python -m jira_worklog_gui
│   ├── app.py                     # 主窗口（4 Tab Notebook）
│   ├── config_store.py            # 凭据 JSON 读写（用户目录 ~/.jira_worklog_gui/）
│   ├── jira_service.py            # JiraConnection 薄封装 + JQL 常量
│   ├── views/                     # 4 个 Tab
│   │   ├── credentials_view.py    # ① 凭据配置
│   │   ├── task_summary.py        # ② 任务汇总（三段：我的非 IPPUB / 我的 IPPUB / 自定义 JQL）
│   │   ├── log_entry.py           # ③ 快速登记
│   │   └── today_log.py           # ④ 近 7 天日志
│   └── widgets/
│       └── duration_entry.py      # 耗时输入 + 校验
```

**改为：**
```
jira-worklog-gui/                  # 仓库根
├── src/jira_worklog_gui/          # 顶层 Python 包
│   ├── __init__.py
│   ├── __main__.py                # python -m jira_worklog_gui
│   ├── app.py                     # 主窗口（4 Tab Notebook）
│   ├── config_store.py            # 凭据 JSON 读写（用户目录 ~/.jira_worklog_gui/）
│   ├── jira_service.py            # JiraConnection 薄封装 + JQL 常量
│   ├── _vendor/                   # 上游 IP_Jira_Mnager 库代码（vendor，断联模式）
│   │   ├── common/decorators.py   # require_connection 工厂
│   │   └── jira/
│   │       ├── utils.py           # get_field_value + parse_jira_datetime
│   │       ├── connection/        # JiraConnection 主类 + 5 mixin + 异常
│   │       └── query/             # search_all_issues + get_user_worklogs
│   ├── views/                     # 4 个 Tab
│   │   ├── credentials_view.py    # ① 凭据配置
│   │   ├── task_summary.py        # ② 任务汇总（三段：我的非 IPPUB / 我的 IPPUB / 自定义 JQL）
│   │   ├── log_entry.py           # ③ 快速登记
│   │   └── today_log.py           # ④ 近 7 天日志
│   └── widgets/
│       └── duration_entry.py      # 耗时输入 + 校验
```

- [ ] **Step 3: 改 §3 安装方式块**

**原 §3 安装方式块：**
```
### 安装方式（**重要**：这是用户首次启动的步骤）：

```bash
# 1. 先装底层库（开发模式）
git clone https://gitee.com/chongfengshi/IP_Jira_Mnager.git
pip install -e ./IP_Jira_Mnager

# 2. 装 GUI
git clone https://github.com/FasenChen/jira-worklog-gui.git
pip install -e ./jira-worklog-gui

# 3. 启动
jira-worklog-gui
# 或
python -m jira_worklog_gui
```
```

**改为：**
```
### 安装方式（v3 起单步安装）

```bash
git clone https://github.com/FasenChen/jira-worklog-gui.git
pip install -e ./jira-worklog-gui
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

依赖：`jira>=3.5.0`（PyPI）。上游 `IP_Jira_Mnager` 仓库的连接库已 vendor 到本仓 `_vendor/`，不再需要额外 clone。
```

- [ ] **Step 4: 改 §9 "与上游 IP_Jira_Mnager 仓库的关系"**

**原 §9 整节内容**：
```markdown
## 9. 与上游 IP_Jira_Mnager 仓库的关系

- 本仓依赖 IP_Jira_Mnager 的 `src/jira/` 库（Git 依赖）
- 库侧 v0.x 开放了 worklog 写能力（add_worklog 等），本项目用得到
- 库侧任何对 `JiraConnection` / `search_all_issues` / `get_user_worklogs` 的改动，会通过 `pip install` 拉新 commit 后生效
- 库侧如果改了 issue type id（不太可能），本项目要同步更新 `EXCLUDED_ISSUE_TYPE_IDS`
```

**改为：**
```markdown
## 9. 上游 IP_Jira_Mnager 仓库（已断联）

自 v3 (2026-07-03) 起，本仓已**完整 vendor** 上游库代码到 `src/jira_worklog_gui/_vendor/`，**不再依赖** `pip install -e ./IP_Jira_Mnager`。

**断联含义：**
- 上游 `IP_Jira_Mnager` 仓库后续任何 commit 不会自动生效
- 需要新功能时，在 vendor 内部手动复制上游代码并解决冲突
- 上游若修了 issue type id，需要手动同步到 vendor + 更新本仓 `EXCLUDED_ISSUE_TYPE_IDS`

**vendor 边界：**
- vendor 目录**视同第三方库**——本项目代码不应修改它
- vendor 仍依赖 PyPI `jira` 库（通过 `from jira import JIRA` 调底层）
```

- [ ] **Step 5: 改文末"最后更新"日期**

把第 228 行的 `最后更新：2026-07-02（项目独立日）` 改为 `最后更新：2026-07-03（v3 vendor 完成）`

- [ ] **Step 6: Commit**

```bash
git add docs/AGENT_CONTEXT.md
git commit -m "docs(context): record v3 vendor migration in history + architecture"
```

---

## Task 14: 最终验证 + .gitignore 复审

**Files:**
- Verify: 全仓测试
- Modify (optional): `.gitignore`

- [ ] **Step 1: 跑全量测试 + App 烟雾**

Run:
```bash
cd D:/Code/jira-worklog-gui && pytest -m unit -v && python -c "
import sys; sys.path.insert(0, 'src')
import tkinter as tk; root = tk.Tk(); root.withdraw()
from jira_worklog_gui.app import App
app = App()
print('Tab 数:', app.nb.index('end'))
app.destroy()
"
```
Expected: `77 passed` + `Tab 数: 4`

- [ ] **Step 2: 检查 vendor 目录确实未被 .gitignore 排除**

Run:
```bash
cd D:/Code/jira-worklog-gui && cat .gitignore && echo "---" && git check-ignore -v src/jira_worklog_gui/_vendor/ || echo "not ignored"
```
Expected: `.gitignore` 没有 `_vendor` / `src/jira_worklog_gui/_vendor` 相关行 + `not ignored`。

- [ ] **Step 3: 验证 git 状态干净**

Run:
```bash
cd D:/Code/jira-worklog-gui && git status
```
Expected: working tree clean（所有 vendor 文件已 commit）。

- [ ] **Step 4: 列出本次新增的所有 commit**

Run:
```bash
cd D:/Code/jira-worklog-gui && git log --oneline -15
```
Expected: 看到 ~13 个 vendor 相关的 commit（"feat(vendor): ..." / "refactor(jira_service): ..." / "chore(deps): ..." / "docs: ..."）。

---

## Self-Review 笔记（写完计划后自检）

- ✅ Spec coverage：13 个任务覆盖了 (1) vendor 13 个文件 (2) 改 1 个 import (3) 删 1 个 bootstrap 函数 (4) 改 pyproject 1 个 dep (5) 改 README + AGENTS + AGENT_CONTEXT (6) 写 6 个烟雾测试 (7) 最终验证
- ✅ Placeholder 扫描：每个 Step 给完整代码或具体命令；无 "TBD" / "add error handling" / "similar to..." / "see other task"
- ✅ Type consistency：所有任务都用 `_vendor.jira.connection.{JiraConnection, JiraConnectionError, JiraAuthError, JiraRequestError}` + `_vendor.jira.query.{search_all_issues, get_user_worklogs}`，与 Task 9 实际 import 匹配
- ✅ DRY：每个 vendor 文件只复制一次（Task 2 / 3 / 4 / 5 / 6 / 7 各负责一组），不改重复代码
- ✅ TDD：Task 8 写测试 → Task 9 才改 import（让 Task 9 跑测试时能验证 vendor 是否完整）
- ✅ Frequent commits：每个 Task 一个独立 commit，message 用 `type(scope): subject`