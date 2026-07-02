"""JiraConnection 的薄封装，给 GUI 层使用。

设计原则：
- 不在 import 时建立连接（懒加载），让 GUI 启动不依赖网络
- 所有方法要么返回数据，要么抛 JiraConnectionError / JiraAuthError / JiraRequestError，
  让调用方负责错误提示
- 解析 JIRA 原始 Issue 对象为简单 dict，便于 Treeview 渲染
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 兼容 IP_Jira_Mnager 的 src/ 布局：原仓 _decorators.py 用 from ...common.decorators
# 只有当 IP_Jira_Mnager/src 在 sys.path 时才能 resolve。这里自动探测 IP_Jira_Mnager
# 的 editable 安装路径，把 src 目录加到 sys.path。如果安装方式改了，这段也无害（已
# 在 sys.path 上时加重复项无副作用）。
def _bootstrap_ip_jira_manager_src() -> None:
    try:
        from importlib.metadata import distribution
    except ImportError:
        return
    try:
        dist = distribution("ip-jira-manager")
    except Exception:
        return
    candidates = []
    # 1) editable install: dist-info/direct_url.json 里有 file:// 指向项目根
    try:
        import json
        dist_info_dir = Path(str(dist._path))  # type: ignore[attr-defined]
        direct_url = dist_info_dir / "direct_url.json"
        if direct_url.exists():
            data = json.loads(direct_url.read_text(encoding="utf-8"))
            url = data.get("url", "")
            if url.startswith("file://"):
                # file:///D:/Code/IP_Jira_Mnager -> D:\Code\IP_Jira_Mnager
                from urllib.request import url2pathname
                project_root = Path(url2pathname(url[len("file://"):]))
                candidates.append(project_root / "src")
    except Exception:
        pass
    # 2) 退路：dist-info 的父目录（site-packages）下的 src（普通 install 用）
    try:
        dist_info_dir = Path(str(dist._path))  # type: ignore[attr-defined]
        site_packages = dist_info_dir.parent
        candidates.append(site_packages / "src")
    except Exception:
        pass
    for cand in candidates:
        try:
            # cand 是 src 目录的路径。我们要的是 cand.parent（即 src 所在的项目根），
            # 因为 src/__init__.py 里 from src.jira import ... 要能 resolve。
            project_root = cand.parent
            src_init = cand / "__init__.py"
            jira_init = cand / "jira" / "__init__.py"
            # 检查 src/ 完整性：src/__init__.py + src/jira/__init__.py 是最低要求
            # （src/common 可能在 site-packages install 时没被 setuptools 找到，
            # 但 src/ 整目录在 sys.path 上时，import 仍能通过 IP_Jira_Mnager 仓根的
            # src.common 路径解决；或者通过 src/ 自身作为 namespace package。）
            if src_init.exists() and jira_init.exists():
                if str(project_root) not in sys.path:
                    sys.path.insert(0, str(project_root))
                return
        except OSError:
            continue


_bootstrap_ip_jira_manager_src()

from src.jira.connection.client import JiraConnection  # noqa: E402
from src.jira.connection.exceptions import (  # noqa: E402
    JiraConnectionError,
    JiraAuthError,
    JiraRequestError,
)
from src.jira.query import search_all_issues, get_user_worklogs  # noqa: E402


# 任务汇总预设 JQL（设计文档定义）
#
# 注意：issuetype 排除条件使用 issue type id 而非中文名。
# 该实例的 JQL 解析器不识别中文 type name（报 "issuetype 域中没有'问题缺陷'值"），
# 但 id 在所有 JQL 操作符下都稳定工作。
#
# 排除的 issue type:
#   10102 = 问题缺陷
#   10101 = 子任务
#   10303 = 项目子任务
#   10205 = 测试执行子任务
# 如未来需要排除更多类型，按真实 id 追加即可。
EXCLUDED_ISSUE_TYPE_IDS = (10102, 10101, 10303, 10205)

# 排除项目常量（与 IPPUB 段保持互斥：IPPUB 任务只在 IPPUB 段出现）
EXCLUDED_PROJECTS = ("IPPUB",)

MY_TASKS_JQL = (
    'assignee = currentUser() '
    f'AND project NOT IN ({",".join(EXCLUDED_PROJECTS)}) '
    f'AND issuetype NOT IN ({",".join(str(i) for i in EXCLUDED_ISSUE_TYPE_IDS)}) '
    'AND statusCategory != Done '
    'ORDER BY updated DESC'
)

IPPUB_JQL = (
    'project = "IPPUB" '
    'AND assignee = currentUser() '
    f'AND issuetype NOT IN ({",".join(str(i) for i in EXCLUDED_ISSUE_TYPE_IDS)}) '
    'AND statusCategory != Done '
    'ORDER BY updated DESC'
)


# JIRA 风格的 ISO 8601 时间戳可能带 "+0800" 这种无冒号偏移量；
# Python 3.10- 的 fromisoformat 不接受，必须先把 "+HHMM" 转成 "+HH:MM"。
_TZ_OFFSET_RE = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def _parse_jira_datetime(s: str) -> Optional[datetime]:
    """把 JIRA 风格的 ISO 8601 时间戳解析为带 tzinfo 的 datetime。

    支持：
        "2026-07-01T09:00:00.000+0800"   JIRA Server 默认
        "2026-07-01T09:00:00.000+08:00"  带冒号
        "2026-07-01T09:00:00.000Z"       UTC
        "2026-07-01T09:00:00+0800"       无毫秒
    返回 None 表示无法解析。
    """
    if not s:
        return None
    # 末尾偏移量无冒号 → 插入冒号
    s_norm = _TZ_OFFSET_RE.sub(
        lambda m: m.group(1) if ":" in m.group(1) or m.group(1) == "Z"
        else m.group(1)[:-2] + ":" + m.group(1)[-2:],
        s,
    )
    try:
        dt = datetime.fromisoformat(s_norm)
    except ValueError:
        return None
    # 防御性兜底：naive datetime 视为 UTC（避免与带 tzinfo 的 cutoff 比较时崩溃）
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_issue_summary(issue: Any) -> Dict[str, Any]:
    """把 JIRA 原始 Issue 对象拍平成 dict（GUI 用得到的关键字段）。"""
    f = getattr(issue, "fields", None)
    if f is None:
        # 兜底：极简对象
        return {"key": getattr(issue, "key", "?"), "summary": "", "issue_type": "",
                "status": "", "assignee": "", "parent": None, "epic_link": None}
    parent = getattr(f, "parent", None)
    parent_key = getattr(parent, "key", None) if parent else None
    assignee = getattr(f, "assignee", None)
    assignee_name = (getattr(assignee, "displayName", None) or "") if assignee else ""
    return {
        "key": getattr(issue, "key", ""),
        "summary": getattr(f, "summary", "") or "",
        "issue_type": getattr(getattr(f, "issuetype", None), "name", "") or "",
        "status": getattr(getattr(f, "status", None), "name", "") or "",
        "assignee": assignee_name,
        "parent": parent_key,
        # Epic Link 字段：自托管 JIRA 用 customfield_10107（与项目一致）
        "epic_link": getattr(f, "customfield_10107", None),
    }


class JiraService:
    """GUI 与 JIRA 之间的服务层。"""

    def __init__(self, config: Dict[str, Any]):
        # 不在 __init__ 中连接，方便测试时 mock
        self._config = dict(config)
        self._conn: Optional[JiraConnection] = None

    # ---------- 连接 ----------

    def connect(self) -> Dict[str, Any]:
        """建立连接。返回 test_connection() 的结果 dict。URL 硬编码。"""
        from .config_store import HARDCODED_JIRA_URL
        self._conn = JiraConnection(
            url=HARDCODED_JIRA_URL,
            username=self._config.get("username"),
            password=self._config.get("password"),
        ).connect()
        return self._conn.test_connection()

    def disconnect(self) -> None:
        if self._conn:
            self._conn.disconnect()
            self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and self._conn.is_connected

    @property
    def connection(self) -> JiraConnection:
        if self._conn is None:
            raise JiraConnectionError("尚未连接")
        return self._conn

    # ---------- 查询 ----------

    def search_issues(self, jql: str, max_results: int = 200) -> List[Dict[str, Any]]:
        """按 JQL 查询，返回 issue 摘要 dict 列表。"""
        issues = search_all_issues(self.connection, jql, page_size=max_results)
        return [parse_issue_summary(i) for i in issues]

    def search_issues_hierarchical(self, jql: str) -> Dict[str, Any]:
        """按 JQL 查询后，按 Epic 分组返回层级结构。

        返回 dict：
            epics: [{key, summary, status, children: [issue_dict, ...]}, ...]
            orphans: [issue_dict, ...]  # 没有 Epic Link 也没 parent 的
        """
        items = self.search_issues(jql)
        epic_map: Dict[str, Dict[str, Any]] = {}
        orphans: List[Dict[str, Any]] = []
        for item in items:
            epic_key = item.get("epic_link")
            if epic_key:
                bucket = epic_map.setdefault(epic_key, {"key": epic_key, "summary": "", "children": []})
                bucket["children"].append(item)
            else:
                orphans.append(item)
        # 补全 Epic 自身的 summary（如果 JQL 里搜不到）
        for epic_key in list(epic_map.keys()):
            try:
                epic_obj = self.connection.get_issue(epic_key)
                epic_map[epic_key]["summary"] = epic_obj.get("summary", "")
                epic_map[epic_key]["status"] = epic_obj.get("status", "")
            except JiraRequestError:
                pass
        return {"epics": list(epic_map.values()), "orphans": orphans}

    def get_issue_detail(self, issue_key: str) -> Dict[str, Any]:
        """获取单个 issue 的完整信息（含 summary）。"""
        return self.connection.get_issue(issue_key)

    def get_worklog(self, issue_key: str) -> List[Dict[str, Any]]:
        return self.connection.get_worklog(issue_key)

    # ---------- 当天日志 ----------

    def get_recent_worklogs(self, username: str, display_name: str = "",
                            days: int = 7) -> List[Dict[str, Any]]:
        """获取指定用户最近 N 天的所有工作日志。

        复用 src.jira.query.user_activity.get_user_worklogs 拿到最近 N 天的全部，
        然后按 started >= 今天 - (days-1) 00:00 本地时区 过滤。
        按 started 降序返回。

        如果 display_name 留空，自动从 test_connection() 拿当前用户的显示名。
        """
        if not display_name:
            try:
                info = self.connection.test_connection()
                display_name = info.get("user", "") or username
            except Exception:
                display_name = username
        local_tz = datetime.now().astimezone().tzinfo
        cutoff = datetime.combine(
            datetime.now().date() - timedelta(days=days - 1),
            time.min,
        ).replace(tzinfo=local_tz)
        # 拉最近 days 天，多 1 天余量以防跨时区
        raw = get_user_worklogs(self.connection, username, display_name, days=days + 1)
        recent = []
        for wl in raw:
            started_str = wl.get("started", "")
            if not started_str:
                continue
            try:
                # JIRA 返回格式如 "2026-07-01T09:00:00.000+0800"
                # Python 3.10- 的 fromisoformat 不接受无冒号的 "+0800"，需手动插入冒号
                started_dt = _parse_jira_datetime(started_str)
            except ValueError:
                continue
            if started_dt is None:
                continue
            if started_dt >= cutoff:
                recent.append(wl)
        # 按 started 降序
        recent.sort(key=lambda x: x.get("started", ""), reverse=True)
        return recent

    # 保留向后兼容的旧方法名
    def get_today_worklogs(self, username: str, display_name: str = "") -> List[Dict[str, Any]]:
        """[已弃用] 请改用 get_recent_worklogs(..., days=1)。"""
        return self.get_recent_worklogs(username, display_name, days=1)

    # ---------- 写操作 ----------

    def add_worklog(self, issue_key: str, time_spent: str, started: Optional[datetime],
                    comment: str = "", adjust_estimate: str = "leave") -> Dict[str, Any]:
        return self.connection.add_worklog(
            issue_key=issue_key,
            time_spent=time_spent,
            started=started,
            comment=comment,
            adjust_estimate=adjust_estimate,
        )

    def update_worklog(self, issue_key: str, worklog_id: str, **fields) -> Dict[str, Any]:
        return self.connection.update_worklog(issue_key, worklog_id, **fields)

    def delete_worklog(self, issue_key: str, worklog_id: str,
                       adjust_estimate: str = "leave") -> bool:
        return self.connection.delete_worklog(issue_key, worklog_id, adjust_estimate=adjust_estimate)