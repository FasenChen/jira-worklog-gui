# JIRA 工作日志登记 GUI

一个基于 Python 标准库 Tkinter 的桌面小工具，用来在自托管 JIRA 实例上方便地登记 / 编辑 / 删除 worklog。

## 启动

```bash
# 1. 装依赖（项目已有）
pip install -e .

# 2. 启动 GUI
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

需要 Python 3.8+（项目本身要求）。GUI 不引入任何第三方库（tkinter 是 Python 自带）。

依赖：`jira>=3.5.0`（PyPI）。上游 `IP_Jira_Mnager` 仓库的 JIRA 连接库已 vendor 到 `src/jira_worklog_gui/_vendor/`，**无需再单独 clone 上游仓库**。

## 功能

四个 Tab：

1. **凭据配置** — 填写 JIRA URL / 用户名 / 密码（或 API Token） / 默认 JQL。
   第一次启动会自动跳到此 Tab。
2. **任务汇总** — 三段堆叠：
   - 📌 **我的非 IPPUB 任务**（未完成、排除缺陷和子任务）自动按 JQL `assignee = currentUser() AND project NOT IN (IPPUB) AND issuetype NOT IN (10102,10101,10303,10205) AND statusCategory != Done` 查询
   - 🏷️ **我的 IPPUB 任务**（排除缺陷和子任务）自动按 JQL `project = "IPPUB" AND assignee = currentUser() AND issuetype NOT IN (10102,10101,10303,10205) AND statusCategory != Done` 查询
   - 🔍 **自定义 JQL** 自由输入并查询
   每段独立 Treeview、独立刷新按钮。选中任一段的叶子后：
   - 段内顶部「📝 登记此 issue →」按钮启用
   - **双击该 issue** 同样触发登记（最便捷）
   - 底部统一「用此 issue 登记 →」按钮启用（任一段选中都可触发，会切到「快速登记」Tab）

   **排除的 issue type id**（共享常量 `EXCLUDED_ISSUE_TYPE_IDS`）：
   - 10102 = 问题缺陷
   - 10101 = 子任务
   - 10303 = 项目子任务
   - 10205 = 测试执行子任务

   JQL 用 id 而非中文名，是因为该实例的 JQL 解析器拒绝 `issuetype != "问题缺陷"` 这类中文字面量。
3. **快速登记** — 填写耗时 / 开始时间 / 描述，一键 add_worklog。
   - 耗时格式：`1h30m` / `90m` / `1.5h` / `5400s` / `2d` / `1w`，单位必填（d=8h，w=5d）
   - 耗时右侧有 5 个快捷按钮 `+30min` / `+1h` / `+2h` / `+4h` / `+8h`，点击累加到当前耗时
   - **开始时间**：手输 + 两行快捷
     - 日期行：「现在」+ 近 7 天快捷（今天/1天前/.../6天前）
     - 时段行：8/9/10/11/14/15/16/17/18 点快捷（跳过午休）
     - 「现在」按钮保留原 HH:MM；其他日期按钮时间归 00:00 方便接着选时段
   - 「登记并继续」可保留当前 issue 连续登记多条
4. **近 7 天日志** — 最近 7 天所有 worklog 列表，支持编辑（弹模态框）和删除。
   - 实现：`JiraService.get_recent_worklogs(username, days=7)`，按本地时区 `00:00` 切 7 天窗口
   - `display_name` 留空时自动从 `test_connection()` 拿，避免 username/display name 不匹配导致 0 条

顶栏绿/红圆点显示连接状态，「重连」按钮可重新建立连接。

## 配置存储

- 位置：`~/.jira_worklog_gui/config.json`（Windows：`C:\Users\<你>\.jira_worklog_gui\config.json`）
- **URL 硬编码**：`https://idisplayvision.com/jira/`（写在 `config_store.HARDCODED_JIRA_URL`，UI 不暴露）
- 优先级：**环境变量 `JIRA_USERNAME/PASSWORD` > JSON 配置文件**
- 不写入 git：用户目录下，**永远不会被本项目仓库追踪**
- 明文存储（密码/token）：和 `config.py` 的现状一致。如果担心可用 `keyring` 等方案后续替换。

## 架构与扩展点

```
src/jira_worklog_gui/
├── __main__.py            # python -m jira_worklog_gui 入口
├── app.py                 # 主窗口（4 Tab Notebook）+ App._on_issue_picked 切 Tab
├── config_store.py        # 凭据 JSON 读写 + HARDCODED_JIRA_URL 常量
├── jira_service.py        # JiraConnection 薄封装 + 业务方法 + EXCLUDED_ISSUE_TYPE_IDS / JQL 常量
├── _vendor/               # 上游 IP_Jira_Mnager 库的 vendor 副本（断联模式，视为第三方）
│   ├── common/decorators.py
│   └── jira/
│       ├── utils.py
│       ├── connection/    # JiraConnection + 5 mixin + 异常类
│       └── query/         # search_all_issues + get_user_worklogs
├── views/                 # 4 个 Tab
│   ├── credentials_view.py
│   ├── task_summary.py
│   ├── log_entry.py
│   └── today_log.py
└── widgets/
    └── duration_entry.py  # 耗时输入 + 校验
```

新增 worklog 操作（add/update/delete）的链路：

```
GUI (views/log_entry.py)
  └─ JiraService.add_worklog(...)                      [src/jira_worklog_gui/jira_service.py]
       └─ JiraConnection.add_worklog(...)              [src/jira_worklog_gui/_vendor/jira/connection/_worklog_write.py]
            └─ jira.JIRA(...).add_worklog(...)         [底层 jira PyPI 库]
```

要增加新功能（比如「按周报表」），照着 `jira_service.py` 的模式加方法即可，无需触碰 GUI 控件。

## 关于 vendor

自 v0.3.0 起，上游 `IP_Jira_Mnager` 仓库本项目实际用到的 `JiraConnection` + 查询函数代码已**完整 vendor** 到 `src/jira_worklog_gui/_vendor/` 下，断联模式：

- 不再依赖 `pip install -e ./IP_Jira_Mnager`
- vendor 内的 `JiraConnection.add_worklog` / `update_worklog` / `delete_worklog` 等写操作直接可用
- 其他资源（issue / comment / transition / attachment 等）仍只读
- vendor 视同第三方库——本项目代码不应修改它
- 未来上游更新需手动复制并解决冲突，详见 `docs/superpowers/plans/2026-07-03-vendor-upstream-jira-lib.md`

## 测试

```bash
# 全量 unit 套件（不依赖真 JIRA，~0.2s 跑完）
pytest -m unit -v

# vendor 烟雾测试（验证 _vendor/ 导入链）
pytest tests/test_vendor_smoke.py -v
```

当前 77 个用例全部通过（71 业务测试 + 6 vendor 烟雾测试）。

GUI 本身是交互式的，未做自动化 GUI 测试。手动 smoke test：启动后填写用户名+密码 → 点「连接」 → 切到「任务汇总」选个 issue → 在「快速登记」用快捷按钮填耗时和开始时间 → 提交 → 在「近 7 天日志」Tab 看到记录。

## 已知限制

- 仅支持 worklog 写操作；修改 issue 字段、添加 comment、转 status 等未提供 GUI
- 当天日志改为近 7 天（`days=7`），按本地时区 00:00 切 7 天窗口
- 一次性最多加载 200 个 issue（`search_issues` 的默认值），如需更多请在 `jira_service.py` 调整
- 不做国际化（中文界面）
- 没打包成 exe，需要 Python 环境（后续可加 PyInstaller）