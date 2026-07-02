"""DurationEntry.parse_duration 单元测试。

Mock 目标：无（纯函数）。
"""
import pytest

from jira_worklog_gui.widgets.duration_entry import parse_duration


pytestmark = pytest.mark.unit


# ============================================================
# 合法输入
# ============================================================

class TestParseDurationValid:
    @pytest.mark.parametrize("text,expected_secs,expected_norm", [
        ("1h", 3600, "1h"),
        ("2h", 7200, "2h"),
        ("30m", 30 * 60, "30m"),
        ("90m", 90 * 60, "1h 30m"),
        ("1h30m", 5400, "1h 30m"),
        ("1H30M", 5400, "1h 30m"),       # 大小写
        ("1h 30m", 5400, "1h 30m"),      # 带空格
        ("1.5h", 5400, "1h 30m"),
        ("0.5h", 1800, "30m"),
        ("5400s", 5400, "1h 30m"),
        ("30s", 30, "30s"),
        ("2d", 16 * 3600, "16h"),        # 1d = 8h
        ("1w", 5 * 8 * 3600, "40h"),     # 1w = 5d = 40h
        ("1d4h", 8 * 3600 + 4 * 3600, "12h"),
    ])
    def test_valid_inputs(self, text, expected_secs, expected_norm):
        secs, norm = parse_duration(text)
        assert secs == expected_secs
        assert norm == expected_norm


# ============================================================
# 非法输入
# ============================================================

class TestParseDurationInvalid:
    @pytest.mark.parametrize("text", [
        "",            # 空
        "   ",         # 全空白
        "xyz",
        "abc",
        "1",           # 无单位
        "1.5.5",
        "1h 2",        # 末段不完整
        "h",           # 只有单位
        "1.",          # 小数点不完整
        "5x",          # 非法单位
        "1h 1.5",      # 末段非法小数
    ])
    def test_invalid_inputs(self, text):
        secs, norm = parse_duration(text)
        assert secs is None
        assert norm == ""


# ============================================================
# 边界
# ============================================================

class TestParseDurationEdge:
    def test_one_minute_is_minimum(self):
        secs, norm = parse_duration("1m")
        assert secs == 60
        assert norm == "1m"

    def test_30_seconds_uses_s_unit(self):
        """< 1 分钟时必须输出秒单位，而不是空字符串。"""
        secs, norm = parse_duration("30s")
        assert secs == 30
        assert norm == "30s"

    def test_1_second(self):
        secs, norm = parse_duration("1s")
        assert secs == 1
        assert norm == "1s"

    def test_combined_units_full_coverage(self):
        secs, norm = parse_duration("1w2d3h4m5s")
        expected = 5 * 8 * 3600 + 2 * 8 * 3600 + 3 * 3600 + 4 * 60 + 5
        assert secs == expected


# ============================================================
# format_seconds_to_jira
# ============================================================

class TestFormatSecondsToJira:
    def test_zero(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(0) == "0s"

    def test_only_seconds(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(30) == "30s"

    def test_only_minutes(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(60) == "1m"

    def test_only_hours(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(3600) == "1h"

    def test_hours_and_minutes(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(5400) == "1h 30m"

    def test_24h(self):
        from jira_worklog_gui.widgets.duration_entry import format_seconds_to_jira
        assert format_seconds_to_jira(86400) == "24h"


# ============================================================
# accumulate_duration
# ============================================================

class TestAccumulateDuration:
    def test_empty_plus_1h(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("", 3600) == "1h"

    def test_1h30m_plus_30min(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("1h 30m", 1800) == "2h"

    def test_invalid_raises_value_error(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        with pytest.raises(ValueError):
            accumulate_duration("xyz", 3600)

    def test_30s_plus_1h(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("30s", 3600) == "1h 30s"

    def test_8h_plus_8h(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("8h", 8 * 3600) == "16h"

    def test_whitespace_stripped(self):
        from jira_worklog_gui.widgets.duration_entry import accumulate_duration
        assert accumulate_duration("  1h  ", 1800) == "1h 30m"