"""JIRA API 封装库（vendor 裁剪版）。

仅暴露本项目实际用到的符号；上游 IP_Jira_Mnager 的 .entity 等模块未 vendor，
故对应符号（BaseIssue / IssueFactory / WorkLog / Epic / CertificationManageTask 等）
在此不可用。

vendor 源：D:\\Code\\IP_Jira_Mnager（HEAD commit 0d04bdf, 2026-07-02，断联模式）
"""

__version__ = "1.0.0"

from .connection import (
    JiraConnection,
    JiraConnectionError,
    JiraAuthError,
    JiraRequestError,
)

from .utils import (
    get_field_value,
    get_attr_value,
    format_date,
    match_user_by_name,
    calculate_total_hours,
    group_worklogs_by_user,
    parse_jira_datetime,
    parse_issue_core,
    parse_timetracking,
)

__all__ = [
    # 连接
    "JiraConnection",
    "JiraConnectionError",
    "JiraAuthError",
    "JiraRequestError",
    # 工具函数
    "get_field_value",
    "get_attr_value",
    "format_date",
    "match_user_by_name",
    "calculate_total_hours",
    "group_worklogs_by_user",
    "parse_jira_datetime",
    "parse_issue_core",
    "parse_timetracking",
]