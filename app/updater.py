"""检查 GitHub Releases 是否有新版本 (轻量更新提示, 不自动下载替换).

流程: 请求 GitHub API 最新 release -> 解析 tag -> 与本地 __version__ 比较.
发现新版本后由用户点击按钮用系统浏览器打开 Releases 页自行下载.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Optional

from . import __version__

REPO = "yphyphyph/opencode-go-gauge"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_PAGE_URL = f"https://github.com/{REPO}/releases/latest"
_TIMEOUT = 8  # 秒; GitHub 直连可能超时, 快速失败避免卡住 UI

_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _parse_version(text: str) -> Optional[tuple[int, int, int]]:
    m = _TAG_RE.match((text or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def check_update() -> dict[str, Any]:
    """请求 GitHub 最新 release 并与本地版本比较.

    Returns:
        {"has_update": bool, "current": str, "latest": str,
         "release_url": str, "notes": str}
    Raises:
        Exception: 网络失败 / 解析失败 (由调用方转为错误响应)
    """
    req = urllib.request.Request(
        RELEASES_URL,
        headers={"User-Agent": f"GoGauge/{__version__}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag = data.get("tag_name") or ""
    latest = _parse_version(tag)
    current = _parse_version(__version__)
    release_url = data.get("html_url") or RELEASE_PAGE_URL
    notes = (data.get("body") or "").strip()

    has_update = bool(latest and current and latest > current)
    return {
        "has_update": has_update,
        "current": __version__,
        "latest": tag,
        "release_url": release_url,
        "notes": notes[:600],
    }
