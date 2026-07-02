"""自定义 Tk 控件。"""
from .duration_entry import (
    DurationEntry,
    accumulate_duration,
    install_invalid_entry_style,
    parse_duration,
)

__all__ = [
    "DurationEntry",
    "accumulate_duration",
    "install_invalid_entry_style",
    "parse_duration",
]


# 占位：未来可能新增 widget
