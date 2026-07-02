# JIRA 工作日志登记 GUI 调整设计

日期：2026-07-01
状态：已批准（用户 2026-07-01 确认）
目标：在已有 `tools/jira_worklog_gui/` 基础上做 6 项调整。

## 背景

上一轮已实现 GUI 工具的初始版本（4 Tab：凭据配置 / Issue 浏览器 / 快速登记 / 当天日志；凭据存到 `~/.jira_worklog_gui/config.json`；JQL+树形浏览；add/update/delete worklog）。

本轮调整主要是**简化配置 + 贴合真实工作流**：
- 公司 JIRA URL 固定，无需用户填写
- 用户只用密码登录，API Token 是 Cloud 用的，自托管不需要
- Issue 浏览器改名"任务汇总"并按 3 个场景分块（我的 / IPPUB / 自定义）
- 快速登记加几个常用时长快捷按钮（更顺手的连续操作）
- 移除"调整估算" UI（永远 leave，避免误改 issue 估算）

## 调整清单

| # | 需求 | 决策 |
|---|---|---|
| 1 | 固定 JIRA URL | 硬编码 `https://idisplayvision.com/jira/`，删除 URL 输入框 |
| 2 | 取消 API Token | 删除 Token 输入框 + JiraService 中 token 字段 |
| — | JQL 排除 issue type 用 id 不用中文名（实施中发现） | 该实例 JQL 解析器拒绝 `issuetype != "问题缺陷"`（报"域中没有值"），但 `issuetype NOT IN (10102)` 正常工作。提取 `EXCLUDED_ISSUE_TYPE_IDS` 常量 |
| 3 | Issue 浏览器 → 任务汇总 | Tab 改名 + 内部布局重构成"上下三个堆叠区" |
| 4a | 我的任务（排除缺陷 + 排除子任务 + 排除 IPPUB 项目） | JQL: `assignee = currentUser() AND project NOT IN (IPPUB) AND issuetype NOT IN (10102,10101,10303,10205) AND statusCategory != Done ORDER BY updated DESC` |
| 4b | 我的 IPPUB 任务（排除缺陷 + 排除子任务） | JQL: `project = "IPPUB" AND assignee = currentUser() AND issuetype NOT IN (10102,10101,10303,10205) AND statusCategory != Done ORDER BY updated DESC` |
| 4c | 自定义 JQL | 保留自由文本框 + 查询按钮 |
| 5 | 耗时快捷按钮 | 5 个按钮：30min / 1h / 2h / 4h / 8h，点击累加到现有值 |
| 6 | 取消剩余估算 | 完全删除 UI 选项，底层始终 `adjust_estimate="leave"` |
| 7 | 当天日志改 7 天（补丁） | `get_recent_worklogs(days=7)` 替换 `get_today_worklogs`；Tab 名 `当天日志` → `近 7 天日志` |
| 8 | 排除 IPPUB 在我的任务（补丁） | `EXCLUDED_PROJECTS = ("IPPUB",)`；4a 的 JQL 加 `project NOT IN (IPPUB)` |
| 9 | 排除子任务在两段（补丁） | `EXCLUDED_ISSUE_TYPE_IDS` 扩展为 `(10102, 10101, 10303, 10205)` |
| 10 | 开始时间快捷（补丁） | 顶部日期行（现在 + 近 7 天）+ 时段行（8/9/10/11/14/15/16/17/18 点） |

### 实施期发现

| 编号 | 问题 | 修复 |
|---|---|---|
| D1 | JQL 中文字面量被解析器拒绝 | 改用 issue type id（`EXCLUDED_ISSUE_TYPE_IDS`） |
| D2 | `datetime.fromisoformat` 解析 `+0800` 无冒号格式失败 | 新增 `_parse_jira_datetime` 工具函数，自动插入冒号并兜底 UTC |
| D3 | 任务汇总堆叠后底部统一按钮不在视野内 | 每段加 inline「📝 登记此 issue →」按钮 + 双击触发 + 底部加操作提示标签 |
| D4 | 段内 `_on_pick_clicked` 用 `self._on_issue_selected` 把 `self + issue` 当 2 个参数 | `TaskSummaryView` 用 lambda 包装 `_on_use` |
| D5 | `get_user_worklogs` 二次过滤 `display_name in author` 在 username≠display_name 时返回 0 条 | `get_recent_worklogs` 在 `display_name` 留空时自动从 `test_connection()` 拿 |
| D6 | "重连" button 已连接后仍显示 | `_set_status(connected=True)` 时 `pack_forget()` |
| D7 | `TaskSummaryView` 选中 issue 后不切 Tab | 新增 `on_pick_to_register` 回调（区分"选中"和"登记"两种语义） |

## 架构

### 文件改动清单

**修改（6 个）**：

1. `tools/jira_worklog_gui/config_store.py`
   - `GuiConfig` 移除 `jira_url` 字段
   - 新增模块常量 `HARDCODED_JIRA_URL = "https://idisplayvision.com/jira/"`
   - `load_config()` 不再读 URL；旧 JSON 残留的 `jira_url` 字段静默忽略
   - `is_valid()` 改为只检查 username + password

2. `tools/jira_worklog_gui/views/credentials_view.py`
   - 删除 URL 输入行（含 Label + Entry）
   - 删除 Token 输入行（含 Label + Entry + 提示语）
   - 删除 `_var_url` / `_var_token` / `_var_ssl`（不再需要 SSL 选项，因为已经确定环境）
   - 顶栏加一行只读文本：`服务器：HARDCODED_JIRA_URL`（让用户知道连的是哪里）
   - 删除"测试连接"按钮（保留「保存配置」「连接」）

3. `tools/jira_worklog_gui/jira_service.py`
   - 删除 `token` 字段（`connect()` 不再透传 token）
   - 新增模块常量：
     ```python
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
   - `connect()` 直接用 `HARDCODED_JIRA_URL`

4. `tools/jira_worklog_gui/views/issue_picker.py` → **重命名** 为 `tools/jira_worklog_gui/views/task_summary.py`
   - 类名 `IssuePickerView` → `TaskSummaryView`
   - 内部布局改成 3 段堆叠（见"组件 - 任务汇总"）
   - 每段独立 JQL、独立按钮、独立 Treeview、独立状态条
   - 每段独立查询（互不阻塞）

5. `tools/jira_worklog_gui/views/log_entry.py`
   - 删除"剩余估算"单选组（含 `_var_adjust`、3 个 Radiobutton、对应数据收集/提交逻辑）
   - 耗时行右侧加 5 个 `ttk.Button`：`+30min` / `+1h` / `+2h` / `+4h` / `+8h`
   - 按钮回调：把当前 DurationEntry 解析为秒 → 加上按钮值 → 重新格式化为 jira 字符串 → 回填输入框
   - 非法输入处理：弹 `messagebox.showwarning`，不动输入框
   - 底层 `add_worklog` 永远传 `adjust_estimate="leave"`（删除该参数在 UI 层的收集）

6. `tools/jira_worklog_gui/app.py`
   - import 改成 `from .views import TaskSummaryView`
   - Tab 名 `"② Issue 浏览器"` → `"② 任务汇总"`
   - `self.picker_view` → `self.task_summary_view`
   - 所有回调入口同步改名
   - `set_default_jql` 等调用同步

**修改（1 个测试文件）**：

7. `tests/test_jira_service.py`
   - 新增 `TestJqlConstants`：断言 `MY_TASKS_JQL` / `IPPUB_JQL` 是字符串、含关键关键词（`assignee = currentUser`、`project = "IPPUB"`）
   - 更新 `test_connect_strips_empty_kwargs` → `test_connect_uses_password`：验证 url 是 `HARDCODED_JIRA_URL`，不传 token

8. `tests/test_duration.py`（追加，不新建文件）
   - `DurationEntry` 没有"累加"API，需要为快捷按钮加一个工具函数 `accumulate_duration(current: str, add_seconds: int) -> str`
   - 至少 8 个用例：空 + 1h / 1h30m + 30min / xyz + 1h（非法） / 30s + 1h / 8h + 8h / 累加后正好 24h 等

## 组件

### 任务汇总（TaskSummaryView）布局

```
┌────────────────────────────────────────────────────────┐
│ 📌 分配给我的任务（未完成，排除缺陷）               [刷新]│
│ 状态：✓ 找到 5 个 Epic，12 个子任务                    │
│ ┌──────────────────────────────────────────────────┐    │
│ │ 树形列表（同当前样式）                          │    │
│ └──────────────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────┤
│ 🏷️ IPPUB 项目任务（排除缺陷）                    [刷新]│
│ 状态：✓ 找到 2 个 Epic，6 个子任务                     │
│ ┌──────────────────────────────────────────────────┐    │
│ │ 树形列表                                        │    │
│ └──────────────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────┤
│ 🔍 自定义 JQL                                       [查询]│
│ JQL: [_______________________________________________]  │
│ 状态：                                                │
│ ┌──────────────────────────────────────────────────┐    │
│ │ 树形列表                                        │    │
│ └──────────────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────┤
│                              [用此 issue 登记 →]       │
└────────────────────────────────────────────────────────┘
```

实现要点：
- 外层用 `ttk.Frame` 三段，每段用 `ttk.LabelFrame` 圈起来
- 每段独立 `ttk.Treeview`（避免冲突）
- 每段查询走 `ThreadPoolExecutor`，互不阻塞
- 选中任何一段的叶子后，整窗口底部的"用此 issue 登记 →"按钮启用（统一入口；不放每段独立按钮，避免冗余）

### 耗时快捷按钮（累加）

```
耗时  [ 1h 30m ]  [+30min] [+1h] [+2h] [+4h] [+8h]
```

按钮回调伪代码：
```python
def _on_quick_duration(self, add_seconds: int):
    current_text = self._var_duration.get().strip()
    if current_text:
        current_secs = parse_duration(current_text)
        if current_secs is None:
            messagebox.showwarning("输入有误", f"当前耗时 '{current_text}' 无法解析，请先修正。")
            return
    else:
        current_secs = 0
    new_secs = current_secs + add_seconds
    self._var_duration.set(format_seconds_to_jira(new_secs))
    # 触发焦点失焦事件以刷新边框样式
    self._duration_entry._refresh_style()
```

`format_seconds_to_jira` 抽到 `widgets/duration_entry.py` 里作为公共函数（`parse_duration` 的反向操作，复用归一化逻辑）。

## 数据流

### 连接建立
1. 用户在「凭据配置」Tab 输入 username + password
2. 点击"连接" → 异步线程
3. `JiraService.connect()` 用 `HARDCODED_JIRA_URL` + username + password → `JiraConnection.connect()`
4. 成功 → `test_connection()` → 通知 `app.py` 的 `_on_connected`
5. 各 View 的 `set_service(service)` 被调用 → 启用其他 Tab

### 任务汇总查询
1. `TaskSummaryView.__init__` 时第一段（我的任务）和第二段（IPPUB）**自动触发查询**
2. 每段独立 worker 线程 → `JiraService.search_issues_hierarchical(jql)`
3. 结果回填到本段的 Treeview
4. 用户点叶子 → 启用"用此 issue 登记 →"按钮
5. 点击 → `on_issue_selected(issue)` → `app.py._on_issue_picked` → 切换到「快速登记」Tab

### 快速登记
1. LogEntryView 接收到 issue dict 后预填
2. 用户填耗时（手输或点快捷按钮累加）
3. 用户填开始时间（默认现在）
4. 用户填描述
5. 点"登记" → 异步线程 → `JiraService.add_worklog(issue_key, time_spent, started, comment)`（不再传 adjust_estimate）
6. 成功 → 清表单 + 自动刷新「当天日志」Tab

## 错误处理

| 场景 | 处理 |
|---|---|
| 配置文件残留旧 `jira_url` / `token` | `load_config()` 静默忽略；`GuiConfig` 不再含这些字段 |
| 快捷按钮遇到非法耗时输入 | `messagebox.showwarning` 提示，不修改输入框 |
| 任一段任务汇总查询失败 | 只在该段状态条显示红色错误，其他两段不受影响 |
| 当天/全部 worklog 渲染错误 | 沿用现有 messagebox.showerror |

## 测试

### 单元测试（自动）
- `tests/test_jira_service.py`
  - 新增 `TestJqlConstants`：断言两个 JQL 常量是字符串、关键字段齐全
  - 更新 `test_connect_strips_empty_kwargs` → `test_connect_uses_password`：验证 `HARDCODED_JIRA_URL` 被使用，token 不被透传
- `tests/test_duration.py`（合并追加，不新建文件）
  - 新增 `TestFormatSecondsToJira`：正向格式化（0 / 30s / 60s / 3600s / 5400s / 28800s）
  - 新增 `TestAccumulateDuration`：累加逻辑（空 + 1h、1h30m + 30min、xyz + 1h、24h 等）

### GUI smoke test（手工）
- 启动 GUI → 看三段是否都能加载
- 在耗时里输入 `1h30m` → 点 +30min → 应该是 `2h`
- 在耗时里输入 `xyz` → 点 +1h → 应该弹 warning 且输入框不变

### 回归
现有 230 个用例应保持全部通过。`test_worklog_write.py` / `test_jira_service.py` 旧用例都不涉及被改动的字段，应不受影响。

## 不在范围内

- 不改 `src/jira` 库本身（库扩展已完成）
- 不改配置文件路径
- 不改当天日志 Tab（功能不变）
- 不改当天日志查询逻辑
- 不新增导出/导入功能
- 不做 macOS / Linux 适配（GUI 是 Tkinter，跨平台 OK，但只验证 Windows）

## 风险

| 风险 | 对策 |
|---|---|
| JQL 中文 `issuetype != "问题缺陷"` 在某些 JIRA 版本写法不同 | JQL 字符串字面量原样提交；若用户反馈改用 issuetype NOT IN (...) 也可后续调 |
| 三段堆叠每段独立 Treeview，渲染大量 issue 时卡顿 | 每段 max_results 限制 200（沿用 search_issues 默认值）；如需更多可在配置里调 |
| 累加按钮超出 24h 后 JIRA 是否接受 | JIRA 不限制单条 worklog 时长；不过 UI 可加显示"超过 24h"警告（非阻断） |
| 旧 config.json 残留 URL 字段 | `GuiConfig` dataclass 字段减少，旧字段被静默丢弃；新写入时自然清理 |