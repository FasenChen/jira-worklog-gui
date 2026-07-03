# AI 协作上下文

> **目的**：让后续重新开对话的 AI agent（或开发者）能快速理解本项目的来龙去脉、关键决策、未完成事项，避免每次从零开始摸索。
>
> **写给谁看**：(1) 未来与该项目协作的 AI agent；(2) 接手维护的开发者。

---

## 1. 项目一句话

**JIRA 工作日志登记 GUI 工具**，Python 3.8+ / Tkinter，硬编码公司 JIRA `https://idisplayvision.com/jira/`，仅密码登录。从 `IP_Jira_Mnager` 仓库独立而来，4 个 Tab（凭据配置 / 任务汇总 / 快速登记 / 近 7 天日志）。

详细功能见 `README.md`。

---

## 2. 项目沿革（重要）

本项目从 `IP_Jira_Mnager` 仓库的 `tools/jira_worklog_gui/` 子目录独立而来。**重要**：完整 commit 历史保留在仓库里（22 个 commit，从最早 `feat(duration): add format_seconds_to_jira` 到最新 `chore: restructure to src/ layout`），任何代码细节都能 `git log` 追溯。

| 时间 | 阶段 | 关键事件 |
|---|---|---|
| 2026-05/06 | v0.x | 库侧：`src/jira` 加 worklog 写能力（add/update/delete），突破"只读库"约束。GUI 端：`tools/jira_worklog_gui` 雏形 |
| 2026-07-01 | v1 (完整实现) | 4 Tab 框架、树形 issue 浏览器、add_worklog 工作流 |
| 2026-07-01 | v2 (需求调整) | 6 项调整：硬编码 URL、取消 Token、任务汇总三段、耗时快捷按钮累加、删除剩余估算 |
| 2026-07-01 | v2 后续补丁 | 7 个 bug fix + 需求（重连按钮隐藏、Tab 切换、JQL id 替代中文名、datetime 解析、display_name 兜底、当天改 7 天、开始时间快捷） |
| 2026-07-02 | 独立仓库 | 用 `git subtree split` 迁出到 https://github.com/FasenChen/jira-worklog-gui，重组为 `src/jira_worklog_gui/` 标准布局 |
| 2026-07-03 | v3 (vendor) | 上游 `IP_Jira_Mnager` 库的 `JiraConnection` + 查询函数全部 vendor 到 `_vendor/`，去掉 `pyproject.toml` 的 Git 依赖，断联模式 |

### 关键决策记录（这些是反复讨论后定下的，避免 AI 重提）

1. **URL 硬编码 `https://idisplayvision.com/jira/`** —— 公司环境固定，UI 不暴露
2. **仅密码登录，不支持 API Token** —— 自托管 JIRA 不用 Token
3. **JQL 用 issue type id 而非中文名** —— 该实例的 JQL 解析器拒绝 `issuetype != "问题缺陷"`（报"域中没有值"），但 `issuetype NOT IN (10102)` 正常工作
4. **EXCLUDED_ISSUE_TYPE_IDS = (10102, 10101, 10303, 10205)** —— 问题缺陷 + 3 种子任务
5. **EXCLUDED_PROJECTS = ("IPPUB",)** —— 任务汇总两段互斥：IPPUB 任务只在 IPPUB 段看
6. **datetime 解析用 `_parse_jira_datetime()`** —— `fromisoformat` 不接受无冒号 `+0800`，工具函数自动补冒号并兜底 UTC
7. **get_recent_worklogs 自动从 test_connection 拿 display_name** —— username `fasen1.chen` ≠ author `陈发森SCE`，调用方不该关心

完整设计/计划文档：
- `docs/superpowers/specs/2026-07-01-jira-worklog-gui-tweaks-design.md`（v2 设计）
- `docs/superpowers/plans/2026-07-01-jira-worklog-gui-tweaks.md`（v2 实施计划）

---

## 3. 架构

### 包结构

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
├── tests/
│   ├── test_jira_service.py       # JiraService 业务方法测试
│   ├── test_duration.py           # 耗时输入 + 校验
│   └── test_vendor_smoke.py       # vendor 包导入链烟雾测试
├── docs/                          # 设计/计划/AI 上下文
├── pyproject.toml                 # 依赖 jira>=3.5.0（vendor 替代原 Git 依赖）
├── AGENTS.md                      # 给开发者看的项目说明
└── README.md                      # 给用户看的使用说明
```

### 依赖关系

```
jira-worklog-gui (本仓)
    ↓ pip install (Git 依赖)
IP_Jira_Mnager (Gitee 仓)
    └─ src/jira/connection/client.py  (JiraConnection)
    └─ src/jira/query/                (search_all_issues, get_user_worklogs)
```

安装方式（**v3 起单步安装**）：

```bash
git clone https://github.com/FasenChen/jira-worklog-gui.git
pip install -e ./jira-worklog-gui
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

依赖：`jira>=3.5.0`（PyPI）。上游 `IP_Jira_Mnager` 仓库的连接库已 vendor 到本仓 `_vendor/`，不再需要额外 clone。

### GUI 内部数据流

```
main()
  └─ App() (tk.Tk)
       ├─ 加载 ~/.jira_worklog_gui/config.json
       ├─ CredentialsView (凭据 Tab)
       │   └─ 用户点"连接" → JiraService.connect() → JiraConnection(HARDCODED_JIRA_URL, user, pwd)
       ├─ TaskSummaryView (任务汇总 Tab)
       │   ├─ _SummarySection × 3（每段独立线程查询）
       │   ├─ MY_TASKS_JQL / IPPUB_JQL（见 jira_service.py）
       │   └─ 选中叶子 → on_pick_to_register → App._on_issue_picked → 切到 LogEntryView
       ├─ LogEntryView (快速登记 Tab)
       │   ├─ 耗时：手输 + +30min/+1h/+2h/+4h/+8h 快捷（累加）
       │   ├─ 开始时间：手输 + 「现在」+ 近 7 天日期 + 8/9/10/11/14/15/16/17/18 时段
       │   └─ 提交：service.add_worklog(issue_key, time_spent, started, comment)
       └─ TodayLogView (近 7 天日志 Tab)
           └─ service.get_recent_worklogs(username, days=7) → 表格 + 编辑/删除按钮
```

### 关键线程模型

- **所有 JIRA 调用**走 `threading.Thread(target=worker, daemon=True).start()` + `self.after(0, ...)` 派回 UI 线程
- **TaskSummaryView 每段**有并发查询保护（`_query_token` 自增 + 过期结果丢弃）
- **关闭应用**时 worker 是 daemon，不阻塞进程退出

---

## 4. 已知坑（避免重蹈覆辙）

| 坑 | 原因 | 修法 |
|---|---|---|
| `can't compare offset-naive and offset-aware datetimes` | JIRA Server 返回 `+0800`（无冒号），`fromisoformat` 默默返回 naive | `_parse_jira_datetime()` 自动补冒号 + 兜底 UTC（`jira_service.py`） |
| JQL `issuetype != "问题缺陷"` 报 400 | 该实例 JQL 解析器不识别中文 type name | 用 id（`issuetype NOT IN (10102)`），见 `EXCLUDED_ISSUE_TYPE_IDS` |
| get_user_worklogs 返回 0 条 | `display_name in author` 二次过滤永远 False | `get_recent_worklogs` 在 `display_name` 留空时自动从 `test_connection()` 拿 |
| 任务汇总底部统一按钮"看不见" | 三段堆叠后按钮在最下方 | 每段加 inline「📝 登记此 issue →」按钮 + 双击触发 |
| 段内按钮回调 "takes 1 positional argument but 2 were given" | 直接传 `self._on_use` 当回调，self + issue = 2 个参数 | 用 `lambda issue: self._on_use()` 包装 |
| 重连按钮在已连接后仍显示 | 硬编码 pack | `_set_status(connected=True)` 时 `pack_forget()` |
| `test_picker` 选中 issue 不切 Tab | 混淆了"选中"和"登记"两种语义 | 拆为 `on_issue_selected`（更新本地）+ `on_pick_to_register`（切 Tab） |
| `find -name "*.py" -exec sed -i 's|from \.\.|from .|g'` | 误判：`from ..widgets` 在 `views/` 里其实指向 package 自身 | **不要**做这个 sed |

---

## 5. 协作约定（AI Agent 工作流）

未来修改/优化本项目时，建议遵循 superpowers 工作流：

1. **Brainstorming**（复杂需求时）：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
2. **Writing-plans**：基于 spec 产出 `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
3. **Subagent-driven-development**（推荐）：每个 Task 一个 subagent + 两阶段 review
4. **TDD 优先**：先写测试 → 看 fail → 实现 → 看 pass → commit
5. **frequent commits**：每个 Task 一个独立 commit，message 用 `type(scope): subject` 格式

AI agent 第一次接活时，建议读：
- `AGENTS.md`（项目说明）
- `README.md`（功能描述）
- `docs/AGENT_CONTEXT.md`（**本文档**，项目历史 + 关键决策）
- `docs/superpowers/specs/2026-07-01-jira-worklog-gui-tweaks-design.md`（核心设计）

---

## 6. 测试

```bash
# 全量
pytest -m unit -v
# 当前 71 tests，0.2s 跑完（不依赖真 JIRA）

# 头部烟雾
python -c "
import sys; sys.path.insert(0, 'src')
import tkinter as tk; root = tk.Tk(); root.withdraw()
from jira_worklog_gui.app import App
app = App()
print('Tab 数:', app.nb.index('end'))
app.destroy()
"
```

### 手动 smoke test 流程

1. 启动 `jira-worklog-gui` → 凭据 Tab 出现
2. 填用户名 + 密码 → 点「连接」→ 状态栏显示 `已连接：fasen1.chen`
3. 切到「任务汇总」→ 三段都自动查询：
   - 我的非 IPPUB 任务：应见认证测试任务（VODCER-167、VODCER-154 等），不应见子任务
   - 我的 IPPUB 任务：应见 IPPUB 项目下你自己的任务（少则 0-5 条）
4. 选中一个 issue → 点 inline「📝 登记此 issue →」→ 切到「快速登记」
5. 填耗时 `1h` → 选日期「今」→ 选时段「9 点」→ 填描述 → 点「登记」
6. 切到「近 7 天日志」→ 看到刚加的日志在列表顶部

---

## 7. 文档索引

| 文件 | 内容 |
|---|---|
| `README.md` | 用户向（功能 + 启动 + 测试） |
| `AGENTS.md` | 开发者向（项目结构 + 启动 + 测试） |
| `docs/AGENT_CONTEXT.md` | **本文档**（AI 协作上下文） |
| `docs/superpowers/specs/2026-07-01-jira-worklog-gui-tweaks-design.md` | v2 需求 + 设计 spec |
| `docs/superpowers/plans/2026-07-01-jira-worklog-gui-tweaks.md` | v2 实施计划（含每个 Task 的代码） |

---

## 8. 已知改进方向（未实施，留给未来）

- [ ] 打包成 exe（PyInstaller）
- [ ] 多用户/多配置文件支持
- [ ] macOS / Linux 适配（当前只测了 Windows）
- [ ] PyQt 重写（Tk 在某些 DPI 下字体模糊）
- [ ] 自定义 JQL 段加保存常用 JQL 的下拉
- [ ] 任务汇总加"只看我的"复选框
- [ ] 日志编辑对话框加 markdown 预览

这些只是想到没做的，**不是承诺要做**。未来新需求来了再 brainstorm。

---

## 9. 上游 IP_Jira_Mnager 仓库（已断联）

自 v3 (2026-07-03) 起，本仓已**完整 vendor** 上游库代码到 `src/jira_worklog_gui/_vendor/`，**不再依赖** `pip install -e ./IP_Jira_Mnager`。

**断联含义：**
- 上游 `IP_Jira_Mnager` 仓库后续任何 commit 不会自动生效
- 需要新功能时，在 vendor 内部手动复制上游代码并解决冲突
- 上游若改了 issue type id，需要手动同步到 vendor + 更新本仓 `EXCLUDED_ISSUE_TYPE_IDS`

**vendor 边界：**
- vendor 目录**视同第三方库**——本项目代码不应修改它
- vendor 仍依赖 PyPI `jira` 库（通过 `from jira import JIRA` 调底层）

---

最后更新：2026-07-03（v3 vendor 完成）
