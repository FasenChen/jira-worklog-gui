# AGENTS.md

## 项目概述

JIRA 工作日志登记 GUI 工具（Python 3.8+，Tkinter）。从 `IP_Jira_Mnager` 仓库独立出来单独开发。

依赖：
- `IP_Jira_Mnager` 库（Git 依赖，从 Gitee 自动装）
- `jira>=3.5.0`（底层 JIRA 库）

## 启动

```bash
# 1. 装底层库（开发模式）
git clone https://gitee.com/chongfengshi/IP_Jira_Mnager.git
pip install -e ./IP_Jira_Mnager

# 2. 装 GUI
git clone https://gitee.com/chongfengshi/jira-worklog-gui.git
pip install -e ./jira-worklog-gui

# 3. 运行
jira-worklog-gui
# 或
python -m jira_worklog_gui
```

## 测试

```bash
pytest -m unit -v
```

## 项目结构

```
src/jira_worklog_gui/
├── __main__.py        # python -m jira_worklog_gui
├── app.py             # 主窗口（4 Tab Notebook）
├── config_store.py    # 凭据 JSON 读写（用户目录）
├── jira_service.py    # JiraConnection 薄封装
├── views/
└── widgets/
```

## 服务器

URL 硬编码：`https://idisplayvision.com/jira/`
仅支持密码登录（自托管 JIRA 不用 API Token）。