"""通用搜索辅助函数。"""
from typing import List, Any

def search_all_issues(conn, jql: str, page_size: int = 500, fields: list = None) -> List[Any]:
    """分页搜索所有匹配的 JIRA issues。"""
    all_issues = []
    start_at = 0
    while True:
        batch = conn.search_issues_raw(jql, max_results=page_size, start_at=start_at, fields=fields)
        if not batch:
            break
        all_issues.extend(batch)
        if len(batch) < page_size:
            break
        start_at += page_size
    return all_issues
