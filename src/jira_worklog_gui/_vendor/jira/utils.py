"""
Dolby Jira Manager - 工具库

整合项目中可复用的方法，降低后续开发成本
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


# ============================================================
# 工具函数
# ============================================================

_SENTINEL = object()


def get_field_value(data, *keys, default=None):
    """
    安全获取嵌套字典值

    Args:
        data: 字典数据
        *keys: 嵌套键路径
        default: 默认值

    Returns:
        提取的值或默认值
    """
    if data is None:
        return default

    value = data
    for key in keys:
        value = get_attr_value(value, key, default=_SENTINEL)
        if value is _SENTINEL:
            return default
    return value


def get_attr_value(obj, attr_name, default=None):
    """
    安全获取对象属性值或字典值

    Args:
        obj: 对象或字典
        attr_name: 属性名
        default: 默认值

    Returns:
        属性值或默认值
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        value = obj.get(attr_name, default)
        return value if value is not None else default
    value = getattr(obj, attr_name, None)
    return value if value is not None else default


def format_date(date_str: str, fmt: str = "%Y-%m-%d") -> str:
    """
    格式化日期显示

    Args:
        date_str: ISO 格式日期字符串
        fmt: 输出格式

    Returns:
        格式化后的日期字符串
    """
    if not date_str:
        return "N/A"
    return parse_jira_datetime(date_str, fmt=fmt)


# ============================================================
# 用户匹配工具
# ============================================================

def match_user_by_name(author: str, check_users: List[str]) -> Optional[str]:
    """
    根据用户名匹配用户

    Args:
        author: 工作日志中的 author 字段
        check_users: 要检查的用户列表（支持姓氏首字符或用户名部分匹配）

    Returns:
        匹配的用户名，未匹配返回 None
    """
    if not author:
        return None

    author_str = str(author)

    for user in check_users:
        if user in author_str:
            return user

    return None


# ============================================================
# 统计工具
# ============================================================

def calculate_total_hours(worklogs: List) -> float:
    """
    计算工作日志总小时数

    Args:
        worklogs: WorkLog 对象列表

    Returns:
        总小时数
    """
    total_seconds = sum(
        (getattr(wl, 'time_spent_seconds', 0) or 0)
        for wl in worklogs
    )
    return round(total_seconds / 3600, 2)


def group_worklogs_by_user(worklogs: List, user_field: str = 'author') -> Dict[str, List]:
    """
    按用户分组工作日志

    Args:
        worklogs: WorkLog 对象列表
        user_field: 用户字段名

    Returns:
        {username: [worklog1, worklog2, ...]}
    """
    result = {}
    for wl in worklogs:
        user = getattr(wl, user_field, None) if hasattr(wl, user_field) else None
        if user:
            if user not in result:
                result[user] = []
            result[user].append(wl)
    return result


# ============================================================
# Issue 解析
# ============================================================

def parse_issue_core(issue, extra_fields: dict = None) -> Dict[str, Any]:
    """
    统一的 Issue 解析核心函数

    提取 JIRA Issue 对象的公共字段，各模块通过 extra_fields 扩展差异字段。

    Args:
        issue: JIRA Issue 对象
        extra_fields: 额外字段提取器 {field_name: callable(fields)->value}

    Returns:
        Dict: 包含公共字段的字典
    """
    fields = issue.fields
    status = getattr(fields, 'status', None)
    issuetype = getattr(fields, 'issuetype', None)
    priority = getattr(fields, 'priority', None)
    assignee = getattr(fields, 'assignee', None)
    reporter = getattr(fields, 'reporter', None)

    data = {
        'key': issue.key,
        'summary': getattr(fields, 'summary', None),
        'status': status.name if status else None,
        'issue_type': issuetype.name if issuetype else None,
        'priority': priority.name if priority else None,
        'assignee': assignee.displayName if assignee else None,
        'reporter': reporter.displayName if reporter else None,
        'created': getattr(fields, 'created', None),
        'updated': getattr(fields, 'updated', None),
    }

    if extra_fields:
        for name, extractor in extra_fields.items():
            data[name] = extractor(fields)

    return data


def parse_timetracking(issue) -> Dict[str, int]:
    """从 JIRA Issue 提取 timetracking (计划/预估工时) 数据。

    JIRA timetracking 返回结构:
        {'originalestimate': '1d 4h', 'originalestimateSeconds': 28800,
         'remainingestimate': '1d', 'remainingestimateSeconds': 28800}

    Args:
        issue: JIRA Issue 对象 (has .fields) 或 fields dict

    Returns:
        Dict with keys: original_estimate_seconds, remaining_estimate_seconds
    """
    fields = getattr(issue, 'fields', issue)
    tt = get_attr_value(fields, 'timetracking')
    if not tt or not isinstance(tt, dict):
        return {'original_estimate_seconds': 0, 'remaining_estimate_seconds': 0}
    return {
        'original_estimate_seconds': tt.get('originalestimateSeconds', 0) or 0,
        'remaining_estimate_seconds': tt.get('remainingestimateSeconds', 0) or 0,
    }


def parse_jira_datetime(date_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将 JIRA 日期字符串解析为统一格式。
    
    支持: '2026-01-27T21:00:00.000+0800', '2026-01-27T21:00:00+0800', '2026-01-27T21:00:00.000Z'
    """
    no_t = date_str.replace('T', ' ')
    if '.' in no_t:
        idx_dot = no_t.index('.')
        idx_plus = no_t.index('+') if '+' in no_t else len(no_t)
        no_ms = no_t[:idx_dot] + no_t[idx_plus:]
    else:
        no_ms = no_t
    
    if '+' in no_ms:
        no_tz = no_ms[:no_ms.index('+')]
    elif no_ms.endswith('Z'):
        no_tz = no_ms[:-1]
    else:
        no_tz = no_ms
    
    try:
        dt = datetime.strptime(no_tz.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime(fmt)
    except ValueError:
        return date_str[:10]


# ============================================================
# 导出
# ============================================================

__all__ = [
    'get_field_value',
    'get_attr_value',
    'format_date',
    'match_user_by_name',
    'calculate_total_hours',
    'group_worklogs_by_user',
    'parse_issue_core',
    'parse_jira_datetime',
    'parse_timetracking',
]