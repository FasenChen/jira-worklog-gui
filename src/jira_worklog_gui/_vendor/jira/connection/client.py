"""
JIRA 连接核心模块
提供与JIRA API建立连接、发送请求及读取数据的功能

读 / 写说明：
- 默认仅提供读取功能
- 自 v0.x 起，worklog 相关操作扩展为可写（add / update / delete），
  用于驱动 tools/jira_worklog_gui 等工具。其他资源仍只读。
"""

import os
from typing import Dict, Any, List, Optional
from ..utils import get_field_value
from .exceptions import JiraConnectionError, JiraAuthError, JiraRequestError
from ._decorators import require_connection
from ._issue_ops import _IssueOpsMixin
from ._metadata import _MetadataMixin
from ._plugin import _PluginMixin
from ._worklog_write import _WorklogWriteMixin

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    JIRA = None
    JIRAError = Exception

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    requests = None
    HTTPBasicAuth = None


class JiraConnection(
    _IssueOpsMixin,
    _MetadataMixin,
    _PluginMixin,
    _WorklogWriteMixin,
):
    """
    JIRA连接管理类

    提供与JIRA系统的稳定、安全通信能力，支持：
    - 用户名密码认证
    - API Token认证
    - 默认仅提供读取功能；worklog 操作（add/update/delete）已开放为可写
    """

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """
        初始化JIRA连接

        Args:
            url: JIRA服务器URL
            username: 用户名
            password: 密码
            token: API Token（用于云端JIRA）
            timeout: 请求超时时间（秒）
            verify_ssl: 是否验证SSL证书
        """
        self.url = url or os.getenv('JIRA_URL')
        self.username = username or os.getenv('JIRA_USERNAME')
        self.password = password or os.getenv('JIRA_PASSWORD')
        self.token = token or os.getenv('JIRA_TOKEN')
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self._client = None
        self._connected = False

    def connect(self) -> 'JiraConnection':
        """
        建立与JIRA服务器的连接

        Returns:
            JiraConnection: 返回自身，支持链式调用

        Raises:
            JiraConnectionError: 连接失败
            JiraAuthError: 认证失败
        """
        if JIRA is None:
            raise JiraConnectionError("请安装jira库: pip install jira")

        try:
            options = {
                'server': self.url,
                'timeout': self.timeout
            }

            if self.token:
                self._client = JIRA(
                    options=options,
                    token_auth=self.token
                )
            else:
                self._client = JIRA(
                    options=options,
                    basic_auth=(self.username, self.password)
                )

            self._client.session()
            self._connected = True

            return self

        except JIRAError as e:
            if e.status_code == 401:
                raise JiraAuthError(f"认证失败: {str(e)}")
            raise JiraConnectionError(f"连接JIRA失败: {str(e)}")
        except Exception as e:
            raise JiraConnectionError(f"连接JIRA失败: {str(e)}")

    def disconnect(self):
        """断开与JIRA服务器的连接"""
        if self._client:
            self._client = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self._client is not None

    def test_connection(self) -> Dict[str, Any]:
        """
        测试连接状态

        Returns:
            Dict: 连接状态信息
        """
        if not self.is_connected:
            return {
                'connected': False,
                'message': '未连接到JIRA服务器'
            }

        try:
            server_info = self._client.server_info()
            myself = self._client.myself()

            return {
                'connected': True,
                'server_version': server_info.get('version'),
                'server_title': server_info.get('serverTitle'),
                'base_url': server_info.get('baseUrl'),
                'user': myself.get('displayName'),
                'user_email': myself.get('emailAddress')
            }
        except Exception as e:
            return {
                'connected': False,
                'message': str(e)
            }

    def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """
        发送GET请求（仅读取）

        Args:
            endpoint: API端点
            params: URL参数

        Returns:
            Dict: 响应数据
        """
        if not self.is_connected:
            raise JiraConnectionError("未连接到JIRA服务器")

        if requests is None:
            raise JiraConnectionError("请安装requests库: pip install requests")

        try:
            url = f"{self.url}/rest/api/3/{endpoint}"

            auth = None
            if not self.token:
                auth = HTTPBasicAuth(self.username, self.password)

            response = requests.get(
                url,
                params=params,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            return response.json() if response.content else {}

        except Exception as e:
            raise JiraRequestError(f"GET请求失败: {e}")

    def _parse_issue(self, issue) -> Dict[str, Any]:
        """解析任务对象"""
        fields = getattr(issue, 'fields', {})

        if not isinstance(fields, dict):
            fields = {}

        return {
            'id': getattr(issue, 'id', None),
            'key': getattr(issue, 'key', None),
            'summary': get_field_value(fields, 'summary'),
            'description': get_field_value(fields, 'description'),
            'issue_type': get_field_value(fields, 'issuetype', 'name'),
            'status': get_field_value(fields, 'status', 'name'),
            'priority': get_field_value(fields, 'priority', 'name'),
            'project': get_field_value(fields, 'project', 'key'),
            'reporter': get_field_value(fields, 'reporter', 'displayName'),
            'assignee': get_field_value(fields, 'assignee', 'displayName'),
            'created': get_field_value(fields, 'created'),
            'updated': get_field_value(fields, 'updated'),
            'due_date': get_field_value(fields, 'duedate'),
            'labels': get_field_value(fields, 'labels') or [],
            'components': [c.get('name') for c in (get_field_value(fields, 'components') or [])],
            'fix_versions': [v.get('name') for v in (get_field_value(fields, 'fixVersions') or [])],
            'parent': get_field_value(fields, 'parent', 'key'),
            'epic_name': get_field_value(fields, 'customfield_10011'),
            'sprint': get_field_value(fields, 'customfield_10020')
        }

    def _parse_project(self, project) -> Dict[str, Any]:
        """解析项目对象"""
        return {
            'id': getattr(project, 'id', None),
            'key': getattr(project, 'key', None),
            'name': getattr(project, 'name', None),
            'project_type': getattr(project, 'projectTypeKey', None),
            'avatar_url': getattr(project, 'avatarUrls', None)
        }
