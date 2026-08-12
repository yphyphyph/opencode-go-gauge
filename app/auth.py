"""WebView 登录: 加载 opencode.ai 授权页, 捕获 auth cookie 与工作区 ID.

原理: pywebview (WebView2) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于 opencode.ai 域, 从中提取 auth cookie.
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import uuid
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Optional

import webview

LOGIN_BASE = "https://auth.opencode.ai/authorize"
LOGIN_CLIENT_ID = "app"
LOGIN_REDIRECT_URI = "https://opencode.ai/auth/callback"
AUTH_COOKIE_NAME = "auth"
COOKIE_POLL_SEC = 1.0
_WORKSPACE_URL_RE = re.compile(r"/workspace/(wrk_[A-Za-z0-9]+)")
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断)."""
    print(msg, flush=True)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def build_login_url() -> str:
    """构造授权登录 URL (与 68HUB electron 同款流程)."""
    params = {
        "client_id": LOGIN_CLIENT_ID,
        "redirect_uri": LOGIN_REDIRECT_URI,
        "response_type": "code",
        "state": uuid.uuid4().hex,
    }
    from urllib.parse import urlencode
    return f"{LOGIN_BASE}?{urlencode(params)}"


class LoginWatcher:
    """后台轮询登录窗口, 捕获 auth cookie."""

    def __init__(
        self,
        win,
        on_success: Callable[[str, str], None],
        on_cancelled: Optional[Callable[[], None]] = None,
    ):
        self.win = win
        self.on_success = on_success  # fn(auth_cookie, workspace_hint)
        self.on_cancelled = on_cancelled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.done = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="gousage-login")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _window_alive(self) -> bool:
        try:
            return self.win in webview.windows
        except Exception:  # noqa: BLE001
            return False

    def _run(self) -> None:
        _log("[login] watcher started")
        while not self._stop.is_set():
            try:
                url = self.win.get_current_url() or ""
            except Exception as exc:  # noqa: BLE001 窗口未加载完成或已销毁
                if not self._window_alive():
                    _log("[login] window closed, watcher exits")
                    break
                self._stop.wait(1.0)
                continue

            if url.startswith("https://opencode.ai"):
                try:
                    cookies = self.win.get_cookies() or []
                    raw_desc = [str(c) for c in cookies]
                except Exception as exc:  # noqa: BLE001
                    cookies = []
                    raw_desc = [f"<get_cookies ERROR {type(exc).__name__}: {exc}>"]
                _log(f"[login] on opencode.ai, url={url[:120]}, cookies={raw_desc}")

                for cookie in cookies:
                    # pywebview 返回 http.cookies.SimpleCookie 对象 (dict 子类!)
                    # 注意: SimpleCookie 是 dict 子类, 必须优先按 SimpleCookie 解析
                    names: list[str] = []
                    if isinstance(cookie, SimpleCookieCls):
                        names = list(cookie.keys())
                    elif isinstance(cookie, dict):
                        names = [cookie.get("name", "")]
                    for name in names:
                        if name != AUTH_COOKIE_NAME:
                            continue
                        try:
                            value = cookie[name].value if isinstance(cookie, SimpleCookieCls) else cookie.get("value", "")
                        except Exception:  # noqa: BLE001
                            value = ""
                        if not value:
                            continue
                        match = _WORKSPACE_URL_RE.search(url)
                        workspace_hint = match.group(1) if match else "Default"
                        _log(f"[login] SUCCESS: auth cookie captured (len={len(value)}), ws={workspace_hint}")
                        self.done = True
                        self._stop.set()
                        self.on_success(f"auth={value}", workspace_hint)
                        return
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()
