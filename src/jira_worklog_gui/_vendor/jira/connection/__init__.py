"""jira.connection 子包：JiraConnection 主类 + 异常类 + 5 个 mixin。"""
from .exceptions import JiraConnectionError, JiraAuthError, JiraRequestError
from .client import JiraConnection

__all__ = ['JiraConnectionError', 'JiraAuthError', 'JiraRequestError', 'JiraConnection']