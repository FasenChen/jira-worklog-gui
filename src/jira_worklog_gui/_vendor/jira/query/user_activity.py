"""
用户工作日志查询模块

查询指定用户的工作日志记录，并输出详细信息。

作为库使用:
    from src.jira.query import get_user_worklogs

作为脚本使用:
    python -m src.jira.query.user_activity -u <用户名> -n <显示名> -d <天数>
"""

import os
import argparse
import json
from datetime import datetime, timedelta

from ..connection import JiraConnection
from ..utils import parse_jira_datetime


def get_user_worklogs(conn, username, display_name, days=7):
    """
    获取用户的工作日志记录

    Args:
        conn: JiraConnection 对象
        username: 用户名 (如 fasen1.chen)
        display_name: 显示名称 (如 陈发森SCE)
        days: 查询最近多少天

    Returns:
        List: 工作日志列表
    """
    print(f"查询用户 '{display_name}' 最近 {days} 天的工作日志...")

    # 计算截止日期（用于筛选 started 实际工作日期）
    cutoff_datetime = datetime.now() - timedelta(days=days)

    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 查询用户有工作日志的任务
    jql = f'worklogAuthor = {username} AND worklogDate >= "{since_date}" ORDER BY updated DESC'

    try:
        # 使用 search_issues_raw 获取原始对象
        issues = conn.search_issues_raw(jql, max_results=100)
        print(f"找到 {len(issues)} 个有工作日志的任务\n")

        all_worklogs = []

        # 遍历每个任务，获取工作日志详情
        for issue in issues:
            issue_key = issue.key

            try:
                # 获取工作日志
                worklogs = conn.get_worklog(issue_key)

                # 筛选该用户的工作日志（用 displayName 匹配）
                user_worklogs = [w for w in worklogs if display_name in str(w.get('author', ''))]

                # 调试打印
                if not user_worklogs and worklogs:
                    print(f"  DEBUG: display_name={display_name}, authors={[w.get('author') for w in worklogs]}")

                # 获取 summary
                summary = getattr(issue.fields, 'summary', 'N/A')

                for wl in user_worklogs:
                    # 解析 started 时间（实际工作开始时间）
                    started = wl.get('started', '')
                    started_datetime = None

                    if started:
                        try:
                            started_clean = parse_jira_datetime(started)
                            started_datetime = datetime.strptime(started_clean[:19], "%Y-%m-%d %H:%M:%S")
                        except:
                            pass

                    # 筛选：只保留实际工作日期在最近 days 天内的记录
                    if started_datetime and started_datetime >= cutoff_datetime:
                        started_display = parse_jira_datetime(started) if started else ''

                        # 直接使用 time_spent_seconds（connection.py 已转换好）
                        time_spent_seconds = wl.get('time_spent_seconds', 0) or 0

                        if time_spent_seconds and isinstance(time_spent_seconds, int):
                            hours = time_spent_seconds / 3600
                            time_spent_str = f"{hours:.2f} hours"
                        else:
                            time_spent_str = "N/A"

                        all_worklogs.append({
                            'issue_key': issue_key,
                            'summary': summary,
                            'author': wl.get('author'),
                            'started': started_display,
                            'time_spent_seconds': time_spent_seconds,
                            'time_spent_display': time_spent_str,
                            'comment': wl.get('comment', '')
                        })

            except Exception as e:
                print(f"  获取 {issue_key} 工作日志失败: {e}")

        return all_worklogs

    except Exception as e:
        print(f"查询失败: {e}")
        return []


def format_worklog_output(worklogs, username, days):
    """
    格式化输出工作日志
    """
    if not worklogs:
        print(f"\n最近 {days} 天没有找到工作日志记录")
        return

    # 按时间排序
    worklogs.sort(key=lambda x: x['started'], reverse=True)

    # 计算总时间
    total_seconds = sum(w['time_spent_seconds'] for w in worklogs)
    total_hours = total_seconds / 3600

    print(f"\n{'='*80}")
    print(f" 用户 '{username}' 最近 {days} 天的工作日志")
    print(f" 总计: {len(worklogs)} 条记录, {total_hours:.2f} 小时")
    print(f"{'='*80}\n")

    # 按日期分组显示
    current_date = None
    daily_total = 0
    daily_count = 0

    for wl in worklogs:
        # 提取日期
        date = wl['started'][:10] if wl['started'] else 'Unknown'

        if date != current_date:
            if current_date is not None:
                print(f"  Subtotal: {daily_count} records, {daily_total/3600:.2f} hours\n")
            current_date = date
            daily_total = 0
            daily_count = 0
            print(f"\n[{date}]")

        print(f"  [{wl['issue_key']}] {wl['time_spent_display']}")
        summary = wl.get('summary') or 'N/A'
        if summary and summary != 'N/A':
            print(f"    Task: {summary[:60]}...")
        if wl.get('comment'):
            print(f"    Comment: {wl['comment'][:80]}")
        print()

        daily_total += wl['time_spent_seconds']
        daily_count += 1

    # 打印最后一天的汇总
    if daily_count > 0:
        print(f"  小计: {daily_count} 条, {daily_total/3600:.2f} 小时\n")


def save_to_json(worklogs, username, days):
    """
    保存到 JSON 文件
    """
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"user_worklog_{username}_{days}days_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    # 计算汇总
    total_seconds = sum(w['time_spent_seconds'] for w in worklogs)
    total_hours = total_seconds / 3600

    output_data = {
        "username": username,
        "days": days,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(worklogs),
        "total_hours": round(total_hours, 2),
        "worklogs": worklogs
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n已保存到: {filepath}")


def main():
    parser = argparse.ArgumentParser(description='查询用户工作日志')
    parser.add_argument('--user', '-u', default=None, help='用户名')
    parser.add_argument('--name', '-n', default=None, help='显示名称')
    parser.add_argument('--days', '-d', type=int, default=7, help='查询最近多少天')

    args = parser.parse_args()

    if not args.user:
        print("错误: 请提供用户名 (-u/--user)")
        parser.print_help()
        return
    if not args.name:
        print("错误: 请提供显示名称 (-n/--name)")
        parser.print_help()
        return

    # JiraConnection 会自动回退到环境变量 (JIRA_URL, JIRA_USERNAME, JIRA_PASSWORD)
    conn = JiraConnection()

    try:
        conn.connect()
        print("连接成功!\n")

        # 查询工作日志（传入 username 和 display_name）
        worklogs = get_user_worklogs(conn, args.user, args.name, args.days)

        # 格式化输出
        format_worklog_output(worklogs, args.name, args.days)

        # 保存到 JSON
        if worklogs:
            save_to_json(worklogs, args.user, args.days)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.disconnect()


if __name__ == '__main__':
    main()
