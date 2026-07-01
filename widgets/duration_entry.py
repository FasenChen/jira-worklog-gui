"""耗时输入控件。

支持格式：
    1h 30m    → 1 小时 30 分
    1.5h      → 1.5 小时
    90m       → 90 分钟
    5400s     → 5400 秒
    1h30m     → 也支持（无空格）
    2d        → 2 天（按 8h 工作日换算）
    1w        → 1 周（按 5d = 40h 换算）

输出：jira 库可识别的字符串（如 "1h 30m"）。
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple


# 单位到秒的换算
_UNIT_SECONDS = {
    "w": 5 * 8 * 3600,   # 1 周按 5 个工作日、每天 8 小时
    "d": 8 * 3600,       # 1 天按 8 小时
    "h": 3600,
    "m": 60,
    "s": 1,
}


_TOKEN_RE = re.compile(r"\s*(\d+(?:\.\d+)?)\s*([wdhms])", re.IGNORECASE)


def parse_duration(text: str) -> Tuple[Optional[int], str]:
    """解析字符串为 (total_seconds, normalized_jira_str)。

    单位必须显式写出：w/d/h/m/s。例如 '1h' / '1h30m' / '90m' / '1.5h' / '5400s'。
    失败时返回 (None, "")。
    normalized_jira_str 形如 "1h 30m" 或 "45m"。
    """
    if not text or not text.strip():
        return None, ""
    text = text.strip().lower()
    total = 0
    consumed = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() != consumed:
            return None, ""
        consumed = m.end()
        num = float(m.group(1))
        unit = m.group(2).lower()
        total += int(num * _UNIT_SECONDS[unit])
    if consumed != len(text):
        return None, ""

    # 格式化为 jira 字符串
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:  # < 1 分钟
        parts.append(f"{seconds}s")
    return total, " ".join(parts)


def format_seconds_to_jira(total_seconds: int) -> str:
    """把总秒数格式化为 jira 字符串（如 '1h 30m'）。

    规则：
        - 0 秒 → "0s"
        - 只含秒（< 60）→ "30s"
        - 整小时无零头 → "1h" / "24h"
        - 小时 + 秒（无分钟）→ "1h 30s"
        - 否则 "Xh Ym" / "Xm" / "Xm Ys"
    """
    if total_seconds <= 0:
        return "0s"
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        # 仅当“秒”以外的字段没填满时才补秒（避免 "1h 30m 30s" 这种冗余）
        if not hours and not minutes:
            parts.append(f"{seconds}s")
        elif hours and not minutes:
            # 例如 1h 30s → "1h 30s"
            parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"


def accumulate_duration(current: str, add_seconds: int) -> str:
    """把 current 解析为秒，加上 add_seconds，返回 jira 字符串。

    Raises:
        ValueError: current 非空且无法解析时。
    """
    if current and current.strip():
        secs, _ = parse_duration(current)
        if secs is None:
            raise ValueError(f"无法解析耗时：'{current}'")
        new_total = secs + add_seconds
    else:
        new_total = add_seconds
    return format_seconds_to_jira(new_total)


class DurationEntry(ttk.Frame):
    """一个 Entry + 校验边框的组合控件。

    用法：
        de = DurationEntry(parent)
        de.get() -> "1h 30m"（jira 格式）或 ""（空）
        de.get_seconds() -> 5400 或 None（无效）
        de.is_valid() -> bool
    """

    def __init__(self, master, textvariable: Optional[tk.StringVar] = None, **kw):
        super().__init__(master)
        self._var = textvariable or tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self._var, **kw)
        self._entry.pack(fill="x")
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._invalid = False

    def _on_focus_out(self, _evt=None):
        self._refresh_style()

    def _refresh_style(self):
        text = self._var.get()
        if not text:
            self._invalid = False
            self._entry.configure(style="TEntry")
            return
        secs, _ = parse_duration(text)
        self._invalid = secs is None
        self._entry.configure(style="Invalid.TEntry" if self._invalid else "TEntry")

    def get(self) -> str:
        """返回 jira 格式字符串（如 '1h 30m'）。空输入或无效输入返回 ""。"""
        secs, normalized = parse_duration(self._var.get())
        return normalized if secs is not None else ""

    def get_seconds(self) -> Optional[int]:
        secs, _ = parse_duration(self._var.get())
        return secs

    def is_valid(self) -> bool:
        text = self._var.get()
        if not text:
            return True  # 空不视为非法，由调用方决定是否必填
        secs, _ = parse_duration(text)
        return secs is not None

    def clear(self):
        self._var.set("")
        self._refresh_style()


def install_invalid_entry_style(root: tk.Tk) -> None:
    """在 root 上注册红框样式（应用启动时调一次）。"""
    style = ttk.Style(root)
    style.configure(
        "Invalid.TEntry",
        fieldbackground="#fff0f0",
        bordercolor="#cc0000",
        lightcolor="#cc0000",
        darkcolor="#cc0000",
    )