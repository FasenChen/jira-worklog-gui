"""
Issue 操作 Mixin
提供 issue 相关的查询方法：获取 issue、搜索、评论、活动日志、工时、附件、状态转换、所有字段
"""
from typing import Dict, Any, List, Optional
from ._decorators import require_connection
from .exceptions import JiraRequestError


class _IssueOpsMixin:
    """Issue 操作相关方法的 Mixin"""

    @require_connection
    def get_issue(self, issue_key: str, fields: List[str] = None) -> Dict[str, Any]:
        """
        获取任务详情

        Args:
            issue_key: 任务key
            fields: 指定返回的字段

        Returns:
            Dict: 任务详情
        """
        try:
            issue = self._client.issue(issue_key, fields=fields)
            return self._parse_issue(issue)
        except Exception as e:
            raise JiraRequestError(f"获取任务失败: {e}")

    @require_connection
    def search_issues(
        self,
        jql: Optional[str] = None,
        max_results: int = 50,
        start_at: int = 0,
        fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        搜索任务

        Args:
            jql: JQL查询语句
            max_results: 最大返回数量
            start_at: 起始位置
            fields: 指定返回的字段

        Returns:
            Dict: 搜索结果
        """
        try:
            search_options = {
                'maxResults': max_results,
                'startAt': start_at
            }
            if fields:
                search_options['fields'] = fields

            result = self._client.search_issues(jql or '', **search_options)

            return {
                'total': result.total,
                'issues': [self._parse_issue(i) for i in result],
                'max_results': max_results,
                'start_at': start_at
            }
        except Exception as e:
            raise JiraRequestError(f"搜索任务失败: {e}")

    @require_connection
    def search_issues_raw(
        self,
        jql: Optional[str] = None,
        max_results: int = 50,
        start_at: int = 0,
        fields: List[str] = None
    ) -> List[Any]:
        """
        搜索任务 - 返回原始JIRA对象

        Args:
            jql: JQL查询语句
            max_results: 最大返回数量
            start_at: 起始位置
            fields: 指定返回的字段列表，None 表示返回所有字段

        Returns:
            List: 原始JIRA Issue对象列表
        """
        try:
            search_options = {
                'maxResults': max_results,
                'startAt': start_at
            }
            if fields:
                search_options['fields'] = fields

            result = self._client.search_issues(jql or '', **search_options)
            return list(result)
        except Exception as e:
            raise JiraRequestError(f"搜索任务失败: {e}")

    @require_connection
    def get_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """获取任务可用的状态转换"""
        try:
            transitions = self._client.transitions(issue_key)
            return [
                {
                    'id': t['id'],
                    'name': t['name'],
                    'to': t['to']['name']
                }
                for t in transitions
            ]
        except Exception as e:
            raise JiraRequestError(f"获取状态转换失败: {e}")

    @require_connection
    def get_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """获取任务评论"""
        try:
            comments = self._client.comments(issue_key)
            return [
                {
                    'id': c.id,
                    'body': c.body,
                    'author': c.author.displayName if c.author else None,
                    'created': c.created,
                    'updated': c.updated
                }
                for c in comments
            ]
        except Exception as e:
            raise JiraRequestError(f"获取评论失败: {e}")

    @require_connection
    def get_audit_log(self, issue_key: str) -> List[Dict[str, Any]]:
        """
        获取任务的活动日志（变更历史）

        包括：状态变更、经办人变更、评论等
        """
        try:
            # 使用 issue 方法获取包含 changelog 的数据
            issue = self._client.issue(issue_key, expand='changelog')
            raw_data = issue.raw

            audit_logs = []

            # 处理创建记录
            if raw_data.get('fields'):
                created = raw_data.get('fields', {}).get('created')
                creator = raw_data.get('fields', {}).get('creator')
                if creator:
                    creator_name = creator.get('displayName') if isinstance(creator, dict) else None
                    if creator_name:
                        audit_logs.append({
                            'type': 'created',
                            'author': creator_name,
                            'created': created,
                            'field': None,
                            'from_value': None,
                            'to_value': None,
                            'body': f'{creator_name} 创建问题'
                        })

            # 处理变更记录
            changelog = raw_data.get('changelog', {}).get('histories', [])
            for history in changelog:
                author = history.get('author', {})
                author_name = author.get('displayName') if isinstance(author, dict) else None
                created = history.get('created')

                for item in history.get('items', []):
                    field = item.get('field')
                    from_string = item.get('fromString', '')
                    to_string = item.get('toString', '')

                    # 格式化变更描述
                    if field == 'status':
                        action = '进行了状态变更'
                        body = f'{author_name} {action}: {from_string} → {to_string}'
                    elif field == 'assignee':
                        action = '更改了经办人'
                        body = f'{author_name} {action}: {from_string} → {to_string}'
                    elif field == 'priority':
                        action = '更改了优先级'
                        body = f'{author_name} {action}: {from_string} → {to_string}'
                    elif field == 'resolution':
                        action = '更改了解决方案'
                        body = f'{author_name} {action}: {from_string} → {to_string}'
                    else:
                        action = f'更改了 {field}'
                        body = f'{author_name} {action}: {from_string} → {to_string}'

                    audit_logs.append({
                        'type': 'change',
                        'author': author_name,
                        'created': created,
                        'field': field,
                        'from_value': from_string,
                        'to_value': to_string,
                        'body': body
                    })

            return audit_logs

        except Exception as e:
            raise JiraRequestError(f"获取活动日志失败: {e}")

    @require_connection
    def get_worklog(self, issue_key: str) -> List[Dict[str, Any]]:
        """获取任务工作日志"""
        try:
            # 使用 raw 属性获取原始数据
            issue = self._client.issue(issue_key, fields='worklog')
            worklogs = issue.raw.get('fields', {}).get('worklog', {}).get('worklogs', [])
            return [
                {
                    'id': w.get('id'),
                    'author': w.get('author', {}).get('displayName'),
                    'time_spent': w.get('timeSpent'),
                    'time_spent_seconds': w.get('timeSpentSeconds'),
                    'started': w.get('started'),
                    'comment': w.get('comment')
                }
                for w in worklogs
            ]
        except Exception as e:
            raise JiraRequestError(f"获取工作日志失败: {e}")

    @require_connection
    def get_attachments(self, issue_key: str) -> List[Dict[str, Any]]:
        """获取任务附件"""
        try:
            issue = self._client.issue(issue_key)
            attachments = issue.raw.get('fields', {}).get('attachment', [])
            return [
                {
                    'id': a.get('id'),
                    'filename': a.get('filename'),
                    'size': a.get('size'),
                    'author': a.get('author', {}).get('displayName'),
                    'created': a.get('created'),
                    'mime_type': a.get('mimeType'),
                    'content': a.get('content')
                }
                for a in attachments
            ]
        except Exception as e:
            raise JiraRequestError(f"获取附件失败: {e}")

    @require_connection
    def get_issue_all_fields(self, issue_key: str) -> Dict[str, Any]:
        """
        获取任务的所有字段（包括自定义字段）

        用于调试：查看 Jira API 返回的所有可用字段

        Args:
            issue_key: 任务 key

        Returns:
            Dict: 包含所有字段的任务数据
        """
        try:
            # 获取不带任何字段限制的 issue
            issue = self._client.issue(issue_key)
            raw_data = issue.raw

            # 提取所有字段名
            fields = raw_data.get('fields', {})
            field_names = list(fields.keys())

            return {
                'key': issue_key,
                'field_names': field_names,
                'fields': fields
            }

        except Exception as e:
            raise JiraRequestError(f"获取任务所有字段失败: {e}")
