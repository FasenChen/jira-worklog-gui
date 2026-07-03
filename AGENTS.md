# AGENTS.md

> 给未来 AI agent / 接手开发者的速查表。详细背景、设计决策、坑点见 `docs/AGENT_CONTEXT.md`（**先读**）。

## 项目概述

JIRA 工作日志登记 GUI 工具（Python 3.8+，Tkinter）。从 `IP_Jira_Mnager` 仓库的 `tools/jira_worklog_gui/` 子目录用 `git subtree split` 独立而来。**不要**改这个仓依赖的上游 `IP_Jira_Mnager` 库代码——库代码在另一个仓库。

- 主仓库：https://github.com/FasenChen/jira-worklog-gui
- 上游依赖：https://gitee.com/chongfengshi/IP_Jira_Mnager（Git 依赖，pyproject.toml 里钉死）

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

## 测试

```bash
# 全量 unit（不依赖真 JIRA，~0.2s 跑完）
pytest -m unit -v

# 头部烟雾（确认 4 Tab 能构建）
python -c "
import sys; sys.path.insert(0, 'src')
import tkinter as tk; root = tk.Tk(); root.withdraw()
from jira_worklog_gui.app import App
app = App()
print('Tab 数:', app.nb.index('end'))
app.destroy()
"
```

**没有 GUI 自动化测试**。手动 smoke test 流程见 `docs/AGENT_CONTEXT.md` §6。

## 项目结构

```
src/jira_worklog_gui/
├── __main__.py            # python -m jira_worklog_gui 入口
├── app.py                 # 主窗口（4 Tab Notebook）+ App._on_issue_picked 切 Tab
├── config_store.py        # 凭据 JSON 读写 + HARDCODED_JIRA_URL 常量
├── jira_service.py        # JiraConnection 薄封装 + 业务方法 + EXCLUDED_ISSUE_TYPE_IDS / JQL 常量
├── _vendor/               # 上游 IP_Jira_Mnager 库的 vendor 副本（断联模式，视为第三方）
│   ├── common/decorators.py
│   └── jira/
│       ├── utils.py       # get_field_value + parse_jira_datetime 等
│       ├── connection/    # JiraConnection + 5 mixin + 异常类
│       └── query/         # search_all_issues + get_user_worklogs
├── views/
│   ├── credentials_view.py # ① 凭据配置 Tab
│   ├── task_summary.py    # ② 任务汇总（三段：我的非 IPPUB / 我的 IPPUB / 自定义 JQL）
│   ├── log_entry.py       # ③ 快速登记（含耗时快捷 + 开始时间快捷）
│   └── today_log.py       # ④ 近 7 天日志（编辑/删除 worklog）
└── widgets/
    └── duration_entry.py  # 耗时输入 + 校验
tests/                     # unit 套件，无 integration
docs/
├── AGENT_CONTEXT.md       # AI 协作上下文（先读！）
└── superpowers/{specs,plans}/
```

## 架构边界（重要）

- **不要**改 `jira_service.py` 之外的 GUI 文件去直接调底层 `jira.JIRA(...)`——所有 JIRA 调用必须经 `JiraService`
- **`_vendor/` 内的代码视同第三方库**——vendor 是断联模式（不再从 `D:\Code\IP_Jira_Mnager` 自动同步），改 vendor 内的代码 = 改底层库，本项目**不应该**改它
- **不要** `from tools.jira_worklog_gui import ...`——早期路径已废弃
- 新增 worklog 操作链：`view → JiraService.* → _vendor.JiraConnection.* → jira lib (PyPI)`
- 视图层之间**不互相 import**；跨 Tab 通信走 `App._on_issue_picked`（LogEntryView 接收 issue）

## 关键常量 / 业务规则

- **URL 硬编码**：`config_store.HARDCODED_JIRA_URL = "https://idisplayvision.com/jira/"`（UI 不暴露）
- **仅密码登录**，不支持 API Token（自托管 JIRA）
- **凭据优先级**：环境变量 `JIRA_USERNAME`/`JIRA_PASSWORD` > `~/.jira_worklog_gui/config.json`
- **凭据存储**：明文 JSON in `~/.jira_worklog_gui/config.json`（Windows: `C:\Users\<user>\.jira_worklog_gui\config.json`），不进 git
- **`EXCLUDED_ISSUE_TYPE_IDS = (10102, 10101, 10303, 10205)`**（问题缺陷 + 3 种子任务）——JQL 用 id 而非中文名，因为该实例的 JQL 解析器拒绝 `issuetype != "问题缺陷"` 这类中文字面量
- **耗时单位必填**：`1h30m` / `90m` / `1.5h` / `5400s` / `2d` / `1w`（d=8h, w=5d）
- **开始时间快捷**：日期行（今天/1-6 天前）+ 时段行（8/9/10/11/14/15/16/17/18 点，跳过午休）
- **`get_recent_worklogs` 默认 `days=7`**，按本地时区 00:00 切窗口
- **`search_issues` 默认 200 条**，如需更多去 `jira_service.py` 调

## 已知坑（避坑用）

完整版见 `docs/AGENT_CONTEXT.md` §4。重点：

| 坑 | 修法 |
|---|---|
| JIRA 返回 `+0800` 无冒号 → `fromisoformat` 返回 naive | 用 `_parse_jira_datetime()` 工具函数（已实现） |
| `display_name in author` 二次过滤永远 0 条 | `get_recent_worklogs` 自动从 `test_connection()` 拿 display_name |
| 段内按钮回调 `takes 1 positional argument but 2 were given` | 用 `lambda issue: self._on_use()` 包装，别直接传 `self._on_use` |
| `from ..widgets` 在 `views/` 里指向 package 自身 | **不要**做 `sed 's|from \.\.|from .|g'` |
| 所有 JIRA 调用必须走 `threading.Thread(daemon=True).start()` + `self.after(0, ...)` 派回 UI 线程 | Tk 不是线程安全的 |
| `TaskSummaryView` 每段有并发查询保护（`_query_token` 自增） | 旧查询返回要丢弃，别直接刷新 UI |

## 协作约定

- 修改前先读：`docs/AGENT_CONTEXT.md` → `README.md` → `docs/superpowers/specs/2026-07-01-jira-worklog-gui-tweaks-design.md`
- TDD 优先：先写测试 → 看 fail → 实现 → 看 pass
- 提交粒度：每个 Task 一个 commit，`type(scope): subject` 格式
- 复杂需求走 superpowers 工作流：brainstorming → writing-plans → subagent-driven-development
- 新需求来了先 brainstorm，不要直接动手

## 服务器

URL：`https://idisplayvision.com/jira/`（硬编码在 `config_store.HARDCODED_JIRA_URL`）
仅密码登录，无 API Token，无 verify_ssl 选项。