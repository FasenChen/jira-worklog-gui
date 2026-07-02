"""JiraService 单元测试。

Mock 目标：JiraConnection（避免真网络）。
"""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jira_worklog_gui.jira_service import JiraService, parse_issue_summary


pytestmark = pytest.mark.unit


def _make_mock_connection(mock_conn_cls):
    """构造一个能模拟 chain-of-calls 的 JiraConnection mock。

    JiraConnection(...).connect() 必须返回同一个连接实例（链式）。
    """
    mock_conn = Mock()
    mock_conn.connect.return_value = mock_conn  # 链式
    mock_conn.is_connected = True
    mock_conn_cls.return_value = mock_conn
    return mock_conn


# ============================================================
# parse_issue_summary
# ============================================================

class TestJqlConstants:
    def test_my_tasks_jql_includes_assignee_and_excludes_issue_type_ids(self):
        """JQL 用 issue type id（10102 = 问题缺陷）排除，因为该 JIRA
        实例的解析器不识别中文 type name。"""
        from jira_worklog_gui.jira_service import MY_TASKS_JQL
        assert isinstance(MY_TASKS_JQL, str)
        assert "assignee = currentUser()" in MY_TASKS_JQL
        # 用 id 排除，不依赖中文 type name
        assert "issuetype NOT IN (10102" in MY_TASKS_JQL
        # 中文字面量绝不能出现（会被 JQL 解析器拒绝）
        assert '"问题缺陷"' not in MY_TASKS_JQL
        assert "statusCategory != Done" in MY_TASKS_JQL
        assert "ORDER BY updated DESC" in MY_TASKS_JQL

    def test_my_tasks_jql_excludes_ippub_project(self):
        """'我的任务'段排除 IPPUB 项目（IPPUB 任务在 IPPUB 段看）。"""
        from jira_worklog_gui.jira_service import MY_TASKS_JQL
        assert 'project NOT IN (IPPUB)' in MY_TASKS_JQL
        assert '"IPPUB"' not in MY_TASKS_JQL  # 不应用字面量

    def test_my_tasks_jql_excludes_subtasks(self):
        """'我的任务'段排除所有子任务类型（认证子任务、测试子任务等）。"""
        from jira_worklog_gui.jira_service import (
            MY_TASKS_JQL, EXCLUDED_ISSUE_TYPE_IDS,
        )
        # 10101=子任务, 10303=项目子任务, 10205=测试执行子任务
        for tid in (10101, 10303, 10205):
            assert tid in EXCLUDED_ISSUE_TYPE_IDS
            assert str(tid) in MY_TASKS_JQL

    def test_excluded_ids_constant_is_tuple_of_strings(self):
        """EXCLUDED_ISSUE_TYPE_IDS 是个 tuple，便于 join 拼接。"""
        from jira_worklog_gui.jira_service import EXCLUDED_ISSUE_TYPE_IDS
        assert isinstance(EXCLUDED_ISSUE_TYPE_IDS, tuple)
        assert 10102 in EXCLUDED_ISSUE_TYPE_IDS  # 问题缺陷
        assert 10101 in EXCLUDED_ISSUE_TYPE_IDS  # 子任务

    def test_ippub_jql_includes_project_and_assignee(self):
        """IPPUB 段：只显示我经办的、未完成的 IPPUB 任务（2026-07-01 确认）。"""
        from jira_worklog_gui.jira_service import IPPUB_JQL
        assert isinstance(IPPUB_JQL, str)
        assert 'project = "IPPUB"' in IPPUB_JQL
        assert "assignee = currentUser()" in IPPUB_JQL
        # 用 id 列表排除（共享 EXCLUDED_ISSUE_TYPE_IDS）
        assert "issuetype NOT IN (10102" in IPPUB_JQL
        assert '"问题缺陷"' not in IPPUB_JQL
        assert "statusCategory != Done" in IPPUB_JQL  # 与我的任务段一致：只看未完成
        assert "ORDER BY updated DESC" in IPPUB_JQL


class TestParseIssueSummary:
    def _make_issue(self, key="PARCER-1", summary="登录bug",
                    issue_type="Bug", status="In Progress",
                    assignee_name="Alice", parent_key=None,
                    epic_link=None):
        return SimpleNamespace(
            key=key,
            fields=SimpleNamespace(
                summary=summary,
                issuetype=SimpleNamespace(name=issue_type),
                status=SimpleNamespace(name=status),
                assignee=SimpleNamespace(displayName=assignee_name) if assignee_name else None,
                parent=SimpleNamespace(key=parent_key) if parent_key else None,
                customfield_10107=epic_link,
            ),
        )

    def test_full_fields(self):
        issue = self._make_issue(
            parent_key="PARCER-100", epic_link="PARCER-1", assignee_name="Bob",
        )
        d = parse_issue_summary(issue)
        assert d["key"] == "PARCER-1"
        assert d["summary"] == "登录bug"
        assert d["issue_type"] == "Bug"
        assert d["status"] == "In Progress"
        assert d["assignee"] == "Bob"
        assert d["parent"] == "PARCER-100"
        assert d["epic_link"] == "PARCER-1"

    def test_no_assignee(self):
        issue = self._make_issue(assignee_name="")
        assert parse_issue_summary(issue)["assignee"] == ""

    def test_no_parent(self):
        issue = self._make_issue(parent_key=None)
        assert parse_issue_summary(issue)["parent"] is None

    def test_missing_fields_attribute(self):
        # 兜底路径：没有 fields
        bare = SimpleNamespace(key="X-1")
        d = parse_issue_summary(bare)
        assert d["key"] == "X-1"
        assert d["summary"] == ""
        assert d["epic_link"] is None


# ============================================================
# JiraService
# ============================================================

class TestJiraServiceConnect:
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_connect(self, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.test_connection.return_value = {"user": "alice", "server_title": "Test"}

        svc = JiraService({"username": "u", "password": "p"})
        info = svc.connect()

        assert info["user"] == "alice"
        mock_conn_cls.assert_called_once()
        kwargs = mock_conn_cls.call_args.kwargs
        # URL 现在来自 HARDCODED_JIRA_URL，不再来自 config dict
        from jira_worklog_gui.config_store import HARDCODED_JIRA_URL
        assert kwargs["url"] == HARDCODED_JIRA_URL
        assert kwargs["username"] == "u"
        assert kwargs["password"] == "p"
        assert svc.is_connected is True

    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_connect_uses_hardcoded_url(self, mock_conn_cls):
        """connect() 使用 HARDCODED_JIRA_URL，不读 config 里的 jira_url。"""
        from jira_worklog_gui.config_store import HARDCODED_JIRA_URL
        _make_mock_connection(mock_conn_cls)
        svc = JiraService({"username": "u", "password": "p"})
        svc.connect()
        kwargs = mock_conn_cls.call_args.kwargs
        assert kwargs["url"] == HARDCODED_JIRA_URL
        assert kwargs["username"] == "u"
        assert kwargs["password"] == "p"
        assert "token" not in kwargs


class TestJiraServiceSearch:
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    @patch("jira_worklog_gui.jira_service.search_all_issues")
    def test_search_issues(self, mock_search, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        # 返回 1 个原始 issue 对象
        raw_issue = SimpleNamespace(
            key="PARCER-1",
            fields=SimpleNamespace(
                summary="x", issuetype=SimpleNamespace(name="Bug"),
                status=SimpleNamespace(name="Open"), assignee=None, parent=None,
                customfield_10107=None,
            ),
        )
        mock_search.return_value = [raw_issue]

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        items = svc.search_issues("project = PARCER")

        assert len(items) == 1
        assert items[0]["key"] == "PARCER-1"
        mock_search.assert_called_once()
        # 传过去的 jql 应该原样
        assert mock_search.call_args.args[1] == "project = PARCER"


class TestJiraServiceHierarchical:
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    @patch("jira_worklog_gui.jira_service.search_all_issues")
    def test_grouped_by_epic(self, mock_search, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        # 让 get_issue 返回带 summary 的 dict
        mock_conn.get_issue.return_value = {"summary": "Epic Summary", "status": "In Progress"}

        # 构造 3 个 issue：2 个有 epic_link，1 个没有
        issues = [
            SimpleNamespace(key="A-1", fields=SimpleNamespace(
                summary="child 1", issuetype=SimpleNamespace(name="任务"),
                status=SimpleNamespace(name="Open"), assignee=None, parent=None,
                customfield_10107="EPIC-1",
            )),
            SimpleNamespace(key="A-2", fields=SimpleNamespace(
                summary="child 2", issuetype=SimpleNamespace(name="任务"),
                status=SimpleNamespace(name="Done"), assignee=None, parent=None,
                customfield_10107="EPIC-1",
            )),
            SimpleNamespace(key="B-1", fields=SimpleNamespace(
                summary="orphan", issuetype=SimpleNamespace(name="任务"),
                status=SimpleNamespace(name="Open"), assignee=None, parent=None,
                customfield_10107=None,
            )),
        ]
        mock_search.return_value = issues

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        data = svc.search_issues_hierarchical("project in (A, B)")

        assert len(data["epics"]) == 1
        epic = data["epics"][0]
        assert epic["key"] == "EPIC-1"
        assert epic["summary"] == "Epic Summary"  # 通过 get_issue 补全
        assert len(epic["children"]) == 2
        assert data["orphans"][0]["key"] == "B-1"

    @patch("jira_worklog_gui.jira_service.JiraConnection")
    @patch("jira_worklog_gui.jira_service.search_all_issues")
    def test_missing_epic_is_silently_ignored(self, mock_search, mock_conn_cls):
        """当 get_issue 拿不到 epic 时不应阻塞整个查询。"""
        from src.jira.connection.exceptions import JiraRequestError
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.get_issue.side_effect = JiraRequestError("not found")
        mock_search.return_value = [
            SimpleNamespace(key="A-1", fields=SimpleNamespace(
                summary="x", issuetype=SimpleNamespace(name="Bug"),
                status=SimpleNamespace(name="Open"), assignee=None, parent=None,
                customfield_10107="MISSING-1",
            )),
        ]

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        data = svc.search_issues_hierarchical("project = A")
        assert data["epics"][0]["summary"] == ""  # 缺失时不报错


class TestJiraServiceWrite:
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_add_worklog_passes_through(self, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.add_worklog.return_value = {
            "id": "100", "time_spent": "1h", "time_spent_seconds": 3600,
            "started": "2026-07-01T09:00:00.000+0800",
            "comment": "ok", "author": "Alice",
        }

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        tz = timezone(timedelta(hours=8))
        result = svc.add_worklog(
            issue_key="A-1", time_spent="1h",
            started=datetime(2026, 7, 1, 9, 0, 0, tzinfo=tz),
            comment="hi", adjust_estimate="leave",
        )

        assert result["id"] == "100"
        kwargs = mock_conn.add_worklog.call_args.kwargs
        assert kwargs["issue_key"] == "A-1"
        assert kwargs["time_spent"] == "1h"
        assert kwargs["comment"] == "hi"
        assert kwargs["adjust_estimate"] == "leave"

    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_update_worklog(self, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.update_worklog.return_value = {"id": "100", "comment": "new"}

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        svc.update_worklog("A-1", "100", comment="new")

        args = mock_conn.update_worklog.call_args.args
        kwargs = mock_conn.update_worklog.call_args.kwargs
        assert args == ("A-1", "100")  # issue_key, worklog_id 走位置
        assert kwargs == {"comment": "new"}

    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_delete_worklog(self, mock_conn_cls):
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.delete_worklog.return_value = True

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        ok = svc.delete_worklog("A-1", "100")

        assert ok is True
        args = mock_conn.delete_worklog.call_args.args
        kwargs = mock_conn.delete_worklog.call_args.kwargs
        assert args == ("A-1", "100")
        assert kwargs == {"adjust_estimate": "leave"}


class TestJiraServiceGetRecentWorklogs:
    @patch("jira_worklog_gui.jira_service.get_user_worklogs")
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_days_1_keeps_old_behavior(self, mock_conn_cls, mock_get_user):
        """days=1 时只返回今天（向后兼容原 get_today_worklogs 行为）。"""
        mock_conn = _make_mock_connection(mock_conn_cls)

        today_morning = "2026-07-01T09:00:00.000+0800"
        today_afternoon = "2026-07-01T14:00:00.000+0800"
        yesterday_evening = "2026-06-30T18:00:00.000+0800"
        mock_get_user.return_value = [
            {"issue_key": "A-1", "started": yesterday_evening, "time_spent_seconds": 3600},
            {"issue_key": "A-2", "started": today_morning, "time_spent_seconds": 3600},
            {"issue_key": "A-3", "started": today_afternoon, "time_spent_seconds": 7200},
        ]

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()

        from datetime import datetime as _dt

        class FakeDateTime(_dt):
            @classmethod
            def now(cls, tz=None):
                return _dt(2026, 7, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))

            @classmethod
            def fromisoformat(cls, s):
                return _dt.fromisoformat(s)

        with patch("jira_worklog_gui.jira_service.datetime", FakeDateTime):
            today = svc.get_recent_worklogs("alice", days=1)

        assert len(today) == 2
        keys = {wl["issue_key"] for wl in today}
        assert keys == {"A-2", "A-3"}
        # 验证 get_user_worklogs 被传了 days=2（多 1 天余量）
        assert mock_get_user.call_args.kwargs["days"] == 2

    @patch("jira_worklog_gui.jira_service.get_user_worklogs")
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_days_7_returns_whole_week(self, mock_conn_cls, mock_get_user):
        """days=7 时返回最近 7 天所有日志。"""
        mock_conn = _make_mock_connection(mock_conn_cls)

        # 当前 fake 时间：2026-07-01 12:00（+08:00）
        # cutoff = 2026-06-25 00:00（7 天前）
        # 应包含：06-25 到 07-01 的所有；不应包含：06-24
        mock_get_user.return_value = [
            {"issue_key": "OLD-1", "started": "2026-06-24T18:00:00.000+0800", "time_spent_seconds": 60},
            {"issue_key": "DAY1",  "started": "2026-06-25T09:00:00.000+0800", "time_spent_seconds": 60},
            {"issue_key": "DAY3",  "started": "2026-06-27T09:00:00.000+0800", "time_spent_seconds": 60},
            {"issue_key": "TODAY", "started": "2026-07-01T09:00:00.000+0800", "time_spent_seconds": 60},
        ]

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()

        from datetime import datetime as _dt

        class FakeDateTime(_dt):
            @classmethod
            def now(cls, tz=None):
                return _dt(2026, 7, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))

            @classmethod
            def fromisoformat(cls, s):
                return _dt.fromisoformat(s)

        with patch("jira_worklog_gui.jira_service.datetime", FakeDateTime):
            week = svc.get_recent_worklogs("alice", days=7)

        assert len(week) == 3
        assert {wl["issue_key"] for wl in week} == {"DAY1", "DAY3", "TODAY"}
        # get_user_worklogs 多拉 1 天
        assert mock_get_user.call_args.kwargs["days"] == 8

    @patch("jira_worklog_gui.jira_service.get_user_worklogs")
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_legacy_get_today_worklogs_still_works(self, mock_conn_cls, mock_get_user):
        """get_today_worklogs 旧方法名仍可用（向后兼容），内部走 days=1。"""
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_get_user.return_value = []

        svc = JiraService({"jira_url": "x", "username": "u", "password": "p"})
        svc.connect()
        # 不抛错即可
        result = svc.get_today_worklogs("alice")
        assert result == []

# ============================================================
# _parse_jira_datetime（防 can't compare offset-naive 崩溃）
# ============================================================

class TestParseJiraDatetime:
    def test_with_colon_offset(self):
        """标准 ISO 8601 with +08:00."""
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00.000+08:00")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.hour == 9

    def test_without_colon_offset(self):
        """JIRA Server 默认格式 +0800（无冒号）。"""
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00.000+0800")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 8 * 3600

    def test_zulu(self):
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00.000Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 0

    def test_no_milliseconds(self):
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00+0800")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_treated_as_utc(self):
        """没带时区的字符串兜底为 UTC（防 can't compare 崩溃）。"""
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 0

    def test_empty_returns_none(self):
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        assert _parse_jira_datetime("") is None
        assert _parse_jira_datetime(None) is None

    def test_invalid_returns_none(self):
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        assert _parse_jira_datetime("not a date") is None
        assert _parse_jira_datetime("2026-13-99") is None

    def test_negative_offset(self):
        from jira_worklog_gui.jira_service import _parse_jira_datetime
        dt = _parse_jira_datetime("2026-07-01T09:00:00.000-0500")
        assert dt is not None
        assert dt.utcoffset().total_seconds() == -5 * 3600


# ============================================================
# get_recent_worklogs 自动取 display name
# ============================================================

class TestGetRecentWorklogsDisplayNameFallback:
    @patch("jira_worklog_gui.jira_service.get_user_worklogs")
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_empty_display_name_falls_back_to_test_connection(self, mock_conn_cls, mock_get_user):
        """display_name 留空时，应从 test_connection() 的 user 字段拿真显示名。"""
        from jira_worklog_gui.jira_service import JiraService
        mock_conn = _make_mock_connection(mock_conn_cls)
        mock_conn.test_connection.return_value = {"user": "陈发森SCE", "user_email": "x@y.com"}
        mock_get_user.return_value = [
            {"issue_key": "A-1", "started": "2026-07-01T09:00:00.000+0800", "time_spent_seconds": 3600,
             "summary": "test", "author": "陈发森SCE", "time_spent": "1h", "comment": "x"},
        ]
        svc = JiraService({"username": "fasen1.chen", "password": "p"})
        svc.connect()
        svc.get_recent_worklogs("fasen1.chen", display_name="", days=7)
        # 传给底层 get_user_worklogs 的 display_name 应该是从 test_connection 拿的真值
        # get_user_worklogs(conn, username, display_name, days) — 位置参数
        args = mock_get_user.call_args.args
        assert args[2] == "陈发森SCE"  # 第 3 个位置参数是 display_name

    @patch("jira_worklog_gui.jira_service.get_user_worklogs")
    @patch("jira_worklog_gui.jira_service.JiraConnection")
    def test_explicit_display_name_respected(self, mock_conn_cls, mock_get_user):
        """显式传 display_name 时应优先使用。"""
        from jira_worklog_gui.jira_service import JiraService
        _make_mock_connection(mock_conn_cls)
        mock_get_user.return_value = []
        svc = JiraService({"username": "fasen1.chen", "password": "p"})
        svc.connect()
        svc.get_recent_worklogs("fasen1.chen", display_name="My Name", days=7)
        args = mock_get_user.call_args.args
        assert args[2] == "My Name"
