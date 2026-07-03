"""
Worklog 写入 Mixin
提供 worklog 的登记（add）、更新（update）、删除（delete）操作。

新增于 v0.x：项目从纯只读库向读写库演进的第一个写操作。
默认 adjustEstimate="leave"，即登记工时后不修改 issue 的剩余估算。
若需要联动调整估算，可显式传入 adjust_estimate="auto" / "new"。

底层依赖 `jira` 库的 `_client.add_worklog(...)`：
- `timeSpent` 是人类可读字符串（"1h 30m"），由 jira 库转秒
- `started` 需为带 tzinfo 的 datetime 对象，否则底层会硬编码 +0000（视为 UTC）
"""
from datetime import datetime
from typing import Any, Dict, Optional

from ._decorators import require_connection
from .exceptions import JiraRequestError

try:
    from jira.exceptions import JIRAError
except ImportError:
    JIRAError = Exception


class _WorklogWriteMixin:
    """worklog 写入操作（add / update / delete）"""

    # ---------- add ----------

    @require_connection
    def add_worklog(
        self,
        issue_key: str,
        time_spent: str,
        started: Optional[datetime] = None,
        comment: str = "",
        adjust_estimate: str = "leave",
        new_estimate: Optional[str] = None,
        reduce_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """登记一条 worklog。

        Args:
            issue_key: issue key，例如 'PARCER-308'
            time_spent: 耗时字符串，jira 库支持的格式（'1h 30m' / '90m' / '2d'）
            started: 开始时间（推荐带 tzinfo 的 datetime）；None 表示服务器当前时间
            comment: 工作描述
            adjust_estimate: 'leave' / 'auto' / 'new'，默认 'leave'
            new_estimate: 当 adjust_estimate='new' 时的新估算值
            reduce_by: 当 adjust_estimate='manual' 时的减少量

        Returns:
            dict: {id, author, time_spent, time_spent_seconds, started, comment}

        Raises:
            JiraRequestError: JIRA 错误（issue 不存在、权限不足、参数非法等）
        """
        try:
            wl = self._client.add_worklog(
                issue=issue_key,
                timeSpent=time_spent,
                started=started,
                comment=comment or None,
                adjustEstimate=adjust_estimate,
                newEstimate=new_estimate,
                reduceBy=reduce_by,
            )
            return self._worklog_to_dict(wl)
        except JIRAError as e:
            raise JiraRequestError(
                f"登记 worklog 失败 (HTTP {getattr(e, 'status_code', '?')}): {e.text}"
            ) from e

    # ---------- update ----------

    @require_connection
    def update_worklog(
        self,
        issue_key: str,
        worklog_id: str,
        time_spent: Optional[str] = None,
        started: Optional[datetime] = None,
        comment: Optional[str] = None,
        adjust_estimate: str = "leave",
        new_estimate: Optional[str] = None,
        reduce_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新已有 worklog。

        所有可更新字段都可为 None，None 表示不修改该字段。
        （仅传 comment 不传 time_spent 即可只改描述。）

        Args:
            issue_key: issue key
            worklog_id: 要更新的 worklog id（字符串）
            其他参数：与 add_worklog 相同含义

        Returns:
            dict: 更新后的 worklog

        Raises:
            JiraRequestError
        """
        try:
            # 先取回 Worklog 资源对象（jira 库无 update_worklog 顶层方法）
            wl = self._client.worklog(issue_key, worklog_id)
            # Resource.update 通过 **kwargs 把字段塞进 JSON body
            update_kwargs: Dict[str, Any] = {}
            if time_spent is not None:
                update_kwargs["timeSpent"] = time_spent
            if started is not None:
                update_kwargs["started"] = started
            if comment is not None:
                update_kwargs["comment"] = comment
            if adjust_estimate is not None:
                update_kwargs["adjustEstimate"] = adjust_estimate
            if new_estimate is not None:
                update_kwargs["newEstimate"] = new_estimate
            if reduce_by is not None:
                update_kwargs["reduceBy"] = reduce_by

            if hasattr(wl, "update"):
                wl.update(**update_kwargs)
            else:
                # 兜底：直接 PUT 到 self.self
                import json as _json
                url = getattr(wl, "self", None)
                if not url:
                    raise JiraRequestError("无法定位 worklog 的 self URL，无法更新")
                self._client._session.put(url, data=_json.dumps(update_kwargs))
            # 重新拉取一次以获取最新内容
            wl = self._client.worklog(issue_key, worklog_id)
            return self._worklog_to_dict(wl)
        except JIRAError as e:
            raise JiraRequestError(
                f"更新 worklog 失败 (HTTP {getattr(e, 'status_code', '?')}): {e.text}"
            ) from e

    # ---------- delete ----------

    @require_connection
    def delete_worklog(
        self,
        issue_key: str,
        worklog_id: str,
        adjust_estimate: str = "leave",
        new_estimate: Optional[str] = None,
        increase_by: Optional[str] = None,
    ) -> bool:
        """删除一条 worklog。

        Args:
            issue_key: issue key
            worklog_id: 要删除的 worklog id
            adjust_estimate: 删除后剩余估算的调整策略（默认 leave）
            new_estimate / increase_by: 视 adjust_estimate 而定

        Returns:
            bool: True 表示删除成功

        Raises:
            JiraRequestError
        """
        try:
            wl = self._client.worklog(issue_key, worklog_id)
            delete_kwargs: Dict[str, Any] = {}
            if adjust_estimate is not None:
                delete_kwargs["adjustEstimate"] = adjust_estimate
            if new_estimate is not None:
                delete_kwargs["newEstimate"] = new_estimate
            if increase_by is not None:
                delete_kwargs["increaseBy"] = increase_by
            if hasattr(wl, "delete"):
                wl.delete(**delete_kwargs)
                return True
            # 兜底
            import json as _json
            url = getattr(wl, "self", None)
            if not url:
                raise JiraRequestError("无法定位 worklog 的 self URL，无法删除")
            self._client._session.delete(url, params=delete_kwargs or None)
            return True
        except JIRAError as e:
            raise JiraRequestError(
                f"删除 worklog 失败 (HTTP {getattr(e, 'status_code', '?')}): {e.text}"
            ) from e

    # ---------- helpers ----------

    @staticmethod
    def _worklog_to_dict(wl: Any) -> Dict[str, Any]:
        """把 jira 库的 Worklog 资源对象拍平为 dict，对齐 get_worklog() 的输出格式。"""
        author = getattr(wl, "author", None)
        if isinstance(author, dict):
            author_name = author.get("displayName") or author.get("name")
        else:
            author_name = getattr(author, "displayName", None) or getattr(author, "name", None)
        return {
            "id": getattr(wl, "id", None),
            "author": author_name,
            "time_spent": getattr(wl, "timeSpent", None),
            "time_spent_seconds": getattr(wl, "timeSpentSeconds", None),
            "started": getattr(wl, "started", None),
            "comment": getattr(wl, "comment", None),
        }