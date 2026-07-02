"""凭据配置文件读写。

存储位置：~/.jira_worklog_gui/config.json（用户目录，不进 git）
优先级：环境变量 > JSON 配置文件 > 留空报错
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".jira_worklog_gui"
CONFIG_FILE = CONFIG_DIR / "config.json"


# 公司 JIRA 实例固定 URL，不再由用户配置
HARDCODED_JIRA_URL = "https://idisplayvision.com/jira/"


@dataclass
class GuiConfig:
    """GUI 工具的完整配置。URL 已硬编码到 HARDCODED_JIRA_URL。"""
    username: str = ""
    password: str = ""
    default_jql: str = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
    last_username: str = ""  # 仅用于 UI 显示

    def is_valid(self) -> bool:
        """基本检查：用户名 + 密码都必须有。"""
        return bool(self.username) and bool(self.password)


def _to_gui_config(d: dict) -> GuiConfig:
    """从 dict 安全构造 GuiConfig。旧字段 jira_url/token/verify_ssl 静默忽略。"""
    return GuiConfig(
        username=d.get("username", "") or "",
        password=d.get("password", "") or "",
        default_jql=d.get("default_jql") or GuiConfig.default_jql,
        last_username=d.get("last_username", "") or "",
    )


def load_config() -> GuiConfig:
    """从 ~/.jira_worklog_gui/config.json 读取配置。

    返回的 GuiConfig 中各字段已经是「环境变量优先、JSON 兜底」合并后的结果。
    若文件不存在，返回带默认值的 GuiConfig（is_valid() 可能为 False）。
    """
    file_cfg: dict = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            file_cfg = {}
    base = _to_gui_config(file_cfg)

    # 环境变量仅覆盖用户名/密码（URL 已硬编码）
    base.username = os.getenv("JIRA_USERNAME") or base.username
    base.password = os.getenv("JIRA_PASSWORD") or base.password
    if base.username:
        base.last_username = base.username
    return base


def save_config(cfg: GuiConfig) -> None:
    """把 GuiConfig 写入 JSON 文件。仅保存非空字段，不写入环境变量覆盖的部分。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    # 去掉空值，避免用空字符串覆盖之前已有的值
    cleaned = {k: v for k, v in data.items() if v not in ("", None)}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)


def config_path() -> Path:
    """返回配置文件路径（用于 UI 展示）。"""
    return CONFIG_FILE