# JIRA 工作日志登记 GUI

一个基于 Python 标准库 Tkinter 的桌面小工具，用来在自托管 JIRA 实例上方便地登记 / 编辑 / 删除 worklog。

## 启动

在项目根目录（`D:\Code\IP_Jira_Mnager`）：

```bash
# 1. 装依赖（项目已有）
pip install -e .

# 2. 启动 GUI
python -m tools.jira_worklog_gui
```

需要 Python 3.8+（项目本身要求）。GUI 不引入任何第三方库（tkinter 是 Python 自带）。

## 功能

四个 Tab：

1. **凭据配置** — 填写 JIRA URL / 用户名 / 密码（或 API Token） / 默认 JQL。
   第一次启动会自动跳到此 Tab。
2. **任务汇总** — 三段堆叠：
   - 📌 **我的任务**（未完成、排除缺陷）自动按 JQL `assignee = currentUser() AND issuetype != "问题缺陷" AND issuetype != "Bug" AND statusCategory != Done` 查询
   - 🏷️ **IPPUB 任务** 自动按 JQL `project = "IPPUB" AND issuetype != "问题缺陷" AND issuetype != "Bug"` 查询
   - 🔍 **自定义 JQL** 自由输入并查询
   每段独立 Treeview、独立刷新按钮。选中任一段的叶子后，底部「用此 issue 登记 →」按钮启用。
3. **快速登记** — 填写耗时 / 开始时间 / 描述，一键 add_worklog。
   - 耗时格式：`1h30m` / `90m` / `1.5h` / `5400s` / `2d` / `1w`，单位必填（d=8h，w=5d）
   - 「登记并继续」可保留当前 issue 连续登记多条
4. **当天日志** — 当天所有 worklog 列表，支持编辑（弹模态框）和删除。

顶栏绿/红圆点显示连接状态，「重连」按钮可重新建立连接。

## 配置存储

- 位置：`~/.jira_worklog_gui/config.json`（Windows：`C:\Users\<你>\.jira_worklog_gui\config.json`）
- **URL 硬编码**：`https://idisplayvision.com/jira/`（写在 `config_store.HARDCODED_JIRA_URL`，UI 不暴露）
- 优先级：**环境变量 `JIRA_USERNAME/PASSWORD` > JSON 配置文件**
- 不写入 git：用户目录下，**永远不会被本项目仓库追踪**
- 明文存储（密码/token）：和 `config.py` 的现状一致。如果担心可用 `keyring` 等方案后续替换。

## 架构与扩展点

```
tools/jira_worklog_gui/
├── __main__.py             # 入口
├── app.py                  # 主窗口（4 Tab Notebook）
├── config_store.py         # JSON 凭据读写
├── jira_service.py         # JiraConnection 薄封装 + 业务方法
├── views/                  # 4 个 Tab Frame
│   ├── credentials_view.py
│   ├── task_summary.py
│   ├── log_entry.py
│   └── today_log.py
└── widgets/
    └── duration_entry.py   # 耗时输入 + 校验
```

新增 worklog 操作（add/update/delete）的链路：

```
GUI (views/log_entry.py)
  └─ JiraService.add_worklog(...)                [tools/jira_worklog_gui/jira_service.py]
       └─ JiraConnection.add_worklog(...)         [src/jira/connection/_worklog_write.py]
            └─ jira.JIRA(...).add_worklog(...)    [底层 jira 库]
```

要增加新功能（比如「按周报表」），照着 `jira_service.py` 的模式加方法即可，无需触碰 GUI 控件。

## 库扩展说明

为了让 GUI 能写入 worklog，本项目原本**只读**的 `src/jira` 库做了有意的架构突破：

- 新增 `src/jira/connection/_worklog_write.py`（`_WorklogWriteMixin`）
- 挂到 `JiraConnection` 上：`class JiraConnection(..., _WorklogWriteMixin)`
- 暴露 3 个方法：`add_worklog` / `update_worklog` / `delete_worklog`
- **其他资源（issue、comment、transition、attachment 等）仍只读**，没有任何回归

详见 `tests/test_worklog_write.py`（11 个 mock 单元测试覆盖所有写路径与异常映射）。

## 测试

```bash
# 库扩展测试
python -m pytest tests/test_worklog_write.py -v

# GUI 工具测试（不依赖真 JIRA）
python -m pytest tests/test_jira_service.py tests/test_duration.py -v

# 全量 unit 套件
python -m pytest tests/test_utils.py tests/test_entity.py tests/test_connection.py tests/test_query.py tests/test_confluence.py tests/test_duration.py tests/test_jira_service.py tests/test_worklog_write.py
```

当前 244 个用例全部通过。

GUI 本身是交互式的，未做自动化 GUI 测试。手动 smoke test：启动后填写用户名+密码 → 点「连接」 → 切到「任务汇总」选个 issue → 在「快速登记」提交 → 在「当天日志」Tab 看到记录。

## 已知限制

- 仅支持 worklog 写操作；修改 issue 字段、添加 comment、转 status 等未提供 GUI
- 当天日志的"当天"按本地时区（系统时区）的 `00:00-23:59` 计算
- 一次性最多加载 200 个 issue（`search_issues` 的默认值），如需更多请在 `jira_service.py` 调整
- 不做国际化（中文界面）
- 没打包成 exe，需要 Python 环境（后续可加 PyInstaller）