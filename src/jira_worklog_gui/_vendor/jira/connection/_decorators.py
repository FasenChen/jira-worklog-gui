"""
JIRA-specific require_connection decorator.
Re-exports from common with JiraConnectionError preset.
"""
from ...common.decorators import require_connection as _require_connection
from .exceptions import JiraConnectionError

require_connection = _require_connection(JiraConnectionError, "未连接到JIRA服务器")
