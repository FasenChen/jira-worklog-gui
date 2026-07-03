"""
元数据查询 Mixin
提供 JIRA 元数据查询方法：项目、任务类型、状态、优先级、关联类型、组件、版本、角色、用户、用户组
"""
from typing import Dict, Any, List, Optional
from ._decorators import require_connection
from .exceptions import JiraRequestError


class _MetadataMixin:
    """元数据查询相关方法的 Mixin"""

    @require_connection
    def get_projects(self) -> List[Dict[str, Any]]:
        """获取所有项目"""
        try:
            projects = self._client.projects()
            return [self._parse_project(p) for p in projects]
        except Exception as e:
            raise JiraRequestError(f"获取项目失败: {e}")

    @require_connection
    def get_project(self, project_key: str) -> Dict[str, Any]:
        """获取项目详情"""
        try:
            project = self._client.project(project_key)
            return self._parse_project(project)
        except Exception as e:
            raise JiraRequestError(f"获取项目失败: {e}")

    @require_connection
    def get_issue_types(self) -> List[Dict[str, Any]]:
        """获取所有任务类型"""
        try:
            types = self._client.issue_types()
            return [
                {
                    'id': t.id,
                    'name': t.name,
                    'description': t.description,
                    'subtask': t.subtask
                }
                for t in types
            ]
        except Exception as e:
            raise JiraRequestError(f"获取任务类型失败: {e}")

    @require_connection
    def get_statuses(self) -> List[Dict[str, Any]]:
        """获取所有状态"""
        try:
            statuses = self._client.statuses()
            return [
                {
                    'id': s.id,
                    'name': s.name,
                    'description': s.description
                }
                for s in statuses
            ]
        except Exception as e:
            raise JiraRequestError(f"获取状态列表失败: {e}")

    @require_connection
    def get_priorities(self) -> List[Dict[str, Any]]:
        """获取所有优先级"""
        try:
            priorities = self._client.priorities()
            return [
                {
                    'id': p.id,
                    'name': p.name,
                    'description': p.description
                }
                for p in priorities
            ]
        except Exception as e:
            raise JiraRequestError(f"获取优先级列表失败: {e}")

    @require_connection
    def get_issue_link_types(self) -> List[Dict[str, Any]]:
        """获取任务关联类型"""
        try:
            link_types = self._client.issue_link_types()
            return [
                {
                    'id': lt.id,
                    'name': lt.name,
                    'inward': lt.inward,
                    'outward': lt.outward
                }
                for lt in link_types
            ]
        except Exception as e:
            raise JiraRequestError(f"获取关联类型失败: {e}")

    @require_connection
    def get_project_components(self, project_key: str) -> List[Dict[str, Any]]:
        """获取项目组件"""
        try:
            project = self._client.project(project_key)
            components = project.get_components()
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'description': c.description
                }
                for c in components
            ]
        except Exception as e:
            raise JiraRequestError(f"获取项目组件失败: {e}")

    @require_connection
    def get_project_versions(self, project_key: str) -> List[Dict[str, Any]]:
        """获取项目版本"""
        try:
            project = self._client.project(project_key)
            versions = project.get_versions()
            return [
                {
                    'id': str(getattr(v, 'id', '')),
                    'name': str(getattr(v, 'name', '')),
                    'description': str(getattr(v, 'description', '')),
                    'released': getattr(v, 'released', False),
                    'release_date': str(getattr(v, 'releaseDate', '')),
                    'start_date': str(getattr(v, 'startDate', '')),
                }
                for v in versions
            ]
        except Exception as e:
            raise JiraRequestError(f"获取项目版本失败: {e}")

    @require_connection
    def get_project_roles(self, project_key: str) -> Dict[str, Any]:
        """获取项目角色"""
        try:
            project = self._client.project(project_key)
            roles = project.get_roles()
            return roles
        except Exception as e:
            raise JiraRequestError(f"获取项目角色失败: {e}")

    @require_connection
    def search_users(self, query: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """搜索用户"""
        try:
            users = self._client.search_users(query, maxResults=max_results)
            return [
                {
                    'account_id': getattr(u, 'accountId', None),
                    'name': getattr(u, 'name', None),
                    'display_name': getattr(u, 'displayName', None),
                    'email': getattr(u, 'emailAddress', None),
                    'active': getattr(u, 'active', None)
                }
                for u in users
            ]
        except Exception as e:
            raise JiraRequestError(f"搜索用户失败: {e}")

    @require_connection
    def get_all_groups(self) -> List[Dict[str, Any]]:
        """获取所有用户组"""
        try:
            groups = self._client.groups()
            return [
                {
                    'name': g.get('name'),
                    'group_id': g.get('groupId')
                }
                for g in groups
            ]
        except Exception as e:
            raise JiraRequestError(f"获取用户组失败: {e}")
