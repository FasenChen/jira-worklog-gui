"""
JIRA 连接异常类
"""


class JiraConnectionError(Exception):
    """JIRA连接异常"""
    pass


class JiraAuthError(Exception):
    """JIRA认证异常"""
    pass


class JiraRequestError(Exception):
    """JIRA请求异常"""
    pass
