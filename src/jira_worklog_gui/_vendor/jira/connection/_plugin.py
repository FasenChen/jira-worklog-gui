"""
插件/Servlet 访问 Mixin
提供插件 API、Servlet 数据获取、服务器信息和当前用户查询方法
"""
from typing import Dict, Any, Optional
from .exceptions import JiraConnectionError

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    requests = None
    HTTPBasicAuth = None


class _PluginMixin:
    """插件和 Servlet 访问相关方法的 Mixin"""

    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        if not self.is_connected:
            raise JiraConnectionError("未连接到JIRA服务器")
        return self._client.server_info()

    def get_current_user(self) -> Dict[str, Any]:
        """获取当前登录用户信息"""
        if not self.is_connected:
            raise JiraConnectionError("未连接到JIRA服务器")
        return self._client.myself()

    def get_plugin_data(self, plugin_key: str, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """
        调用插件的 REST API

        Args:
            plugin_key: 插件 key，如 'bloompeak-stf'
            endpoint: API 端点，如 'issue/DTCER-209/status-duration'
            params: URL 参数

        Returns:
            Dict: 插件返回的数据
        """
        if not self.is_connected:
            raise JiraConnectionError("未连接到JIRA服务器")

        if requests is None:
            raise JiraConnectionError("请安装requests库: pip install requests")

        try:
            # 尝试 REST API 格式
            url = f"{self.url}/rest/{plugin_key}/{endpoint}"

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

            # 即使是 404 或其他状态码也返回，用于调试
            return {
                'status_code': response.status_code,
                'url': url,
                'data': response.json() if response.content else {},
                'text': response.text if not response.content else None
            }

        except Exception as e:
            return {
                'status_code': None,
                'url': url if 'url' in locals() else None,
                'error': str(e)
            }

    def get_servlet_data(self, servlet_path: str, params: Dict = None) -> Dict[str, Any]:
        """
        直接调用 Jira Servlet（用于获取插件页面数据）

        Args:
            servlet_path: Servlet 路径，如 'plugins/servlet/bloompeak-stf/mainservlet/st-issue-view'
            params: URL 参数

        Returns:
            Dict: 包含状态码和响应内容
        """
        if not self.is_connected:
            raise JiraConnectionError("未连接到JIRA服务器")

        if requests is None:
            raise JiraConnectionError("请安装requests库: pip install requests")

        try:
            # 确保路径以 / 开头
            if not servlet_path.startswith('/'):
                servlet_path = '/' + servlet_path

            url = f"{self.url}{servlet_path}"

            auth = None
            if not self.token:
                auth = HTTPBasicAuth(self.username, self.password)

            response = requests.get(
                url,
                params=params,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={
                    'Accept': 'application/json, text/html, */*',
                    'User-Agent': 'Mozilla/5.0'
                }
            )

            content_type = response.headers.get('Content-Type', '')

            # 尝试解析 JSON，否则返回文本
            data = None
            text = None
            if 'application/json' in content_type:
                try:
                    data = response.json()
                except:
                    pass

            if data is None:
                text = response.text

            return {
                'status_code': response.status_code,
                'url': url,
                'content_type': content_type,
                'data': data,
                'text': text,
                'text_length': len(response.text) if response.text else 0
            }

        except Exception as e:
            return {
                'status_code': None,
                'url': url if 'url' in locals() else None,
                'error': str(e)
            }
