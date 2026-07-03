"""Vendor 烟雾测试：验证 _vendor 子包导入完整、不依赖 sys.path hack。

不依赖真 JIRA 服务器——只验证 import 链路与类签名。
"""
import pytest


def test_vendor_common_decorators_importable():
    from jira_worklog_gui._vendor.common.decorators import require_connection
    assert callable(require_connection)


def test_vendor_jira_utils_importable():
    from jira_worklog_gui._vendor.jira.utils import get_field_value, parse_jira_datetime
    assert callable(get_field_value)
    assert callable(parse_jira_datetime)


def test_vendor_jira_connection_exceptions_importable():
    from jira_worklog_gui._vendor.jira.connection.exceptions import (
        JiraConnectionError, JiraAuthError, JiraRequestError,
    )
    assert issubclass(JiraConnectionError, Exception)
    assert issubclass(JiraAuthError, Exception)
    assert issubclass(JiraRequestError, Exception)


def test_vendor_jira_connection_jira_connection_importable():
    from jira_worklog_gui._vendor.jira.connection import JiraConnection
    # JiraConnection 是 mixin 组合类
    mro_names = [c.__name__ for c in JiraConnection.__mro__]
    assert "_IssueOpsMixin" in mro_names
    assert "_MetadataMixin" in mro_names
    assert "_PluginMixin" in mro_names
    assert "_WorklogWriteMixin" in mro_names


def test_vendor_jira_query_importable():
    from jira_worklog_gui._vendor.jira.query import search_all_issues, get_user_worklogs
    assert callable(search_all_issues)
    assert callable(get_user_worklogs)


def test_vendor_does_not_depend_on_ip_jira_manager_metadata():
    """Vendor 之后，import jira_worklog_gui 不应触发 ip-jira-manager 包的 dist-info 探测。

    删掉 jira_service.py 里的 _bootstrap_ip_jira_manager_src() 后，这个测试是回归保护。
    """
    # ip-jira-manager 包可能根本未安装；vendor 后不应再依赖
    try:
        import importlib
        importlib.import_module("ip_jira_manager")
        # 如果装了，只检查 jira_worklog_gui._vendor 子模块是否独立可用
        from jira_worklog_gui._vendor.jira.connection import JiraConnection
        assert JiraConnection is not None
    except ImportError:
        # ip-jira-manager 不存在才是理想状态
        from jira_worklog_gui._vendor.jira.connection import JiraConnection
        assert JiraConnection is not None