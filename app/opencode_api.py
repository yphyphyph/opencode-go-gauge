"""OpenCode Go API client.

数据获取逻辑移植自 68HUB (https://github.com/evanfu0110/68hub) 的
electron/backend/{quota,opencode-usage}.ts，MIT 协议。

两种能力:
1. 配额 (quota): 抓取 opencode.ai dashboard HTML, 正则解析 5h/weekly/monthly 用量百分比与重置时间
2. 用量记录 (usage): 调用 opencode.ai/_server server-fn 接口, 解析每条请求的 token/cost 明细
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DASHBOARD_BASE = "https://opencode.ai/workspace"
WORKSPACE_SERVER_ID = (
    "def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f"
)
DEFAULT_USAGE_SERVER_ID = (
    "bfd684bfc2e4eed05cd0b518f5e4eafd3f3376e3938abb9e536e7c03df831e5c"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0"
)
REQUEST_TIMEOUT = 30.0
MAX_BODY_BYTES = 4 << 20  # 4 MiB
FETCH_RETRIES = 3  # 网络抖动重试次数
RETRY_BACKOFF = [0.5, 1.5, 3.0]

LABEL_ROLLING = "5h Rolling"
LABEL_WEEKLY = "Weekly"
LABEL_MONTHLY = "Monthly"

# 令牌格式: auth cookie 或 OAuth token 统一以 "auth=<value>" 形式携带
AUTH_HEADER_PREFIX = "auth="

# ---------------------------------------------------------------------------
# 正则 (字段顺序有两种: usagePercent 在前 或 resetInSec 在前)
# ---------------------------------------------------------------------------

_ROLLING_PCT_FIRST = re.compile(
    r"rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)
_ROLLING_RESET_FIRST = re.compile(
    r"rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)
_WEEKLY_PCT_FIRST = re.compile(
    r"weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)
_WEEKLY_RESET_FIRST = re.compile(
    r"weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)
_MONTHLY_PCT_FIRST = re.compile(
    r"monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)
_MONTHLY_RESET_FIRST = re.compile(
    r"monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)"
    r"[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"
)

_WORKSPACE_ID_RE = re.compile(r"wrk_[A-Za-z0-9]+")
_WORKSPACE_ENTRY_RE = re.compile(
    r'id\s*:\s*"(wrk_[^"]+)"[^{}]*?name\s*:\s*"([^"]*)"', re.DOTALL
)

# server-fn 响应中的一条 usage 记录 (兼容 GET 无空格 / POST 带空格两种格式)
_RECORD_ANCHOR_RE = re.compile(r'id:\s*"(usg_[^"]+)"')
_PLAN_RE = re.compile(r'id:\s*"(usg_[^"]+)"[^}]*?enrichment:\$R\[\d+\]=\{plan:"([^"]+)"\}', re.DOTALL)

_CREATED_RE = re.compile(r'timeCreated:\s*\$R\[\d+\]\s*=\s*new Date\("([^"]+)"\)')

# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass
class QuotaWindow:
    label: str
    used: float  # 已用百分比 0-100
    remaining: float
    total: float
    unit: str
    reset_at: str  # ISO
    reset_in_sec: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "used": self.used,
            "remaining": self.remaining,
            "total": self.total,
            "unit": self.unit,
            "reset_at": self.reset_at,
            "reset_in_sec": self.reset_in_sec,
        }


@dataclass
class QuotaResult:
    name: str
    workspace_id: str
    success: bool
    updated_at: str
    windows: list[QuotaWindow] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "workspace_id": self.workspace_id,
            "success": self.success,
            "updated_at": self.updated_at,
        }
        if self.error:
            payload["error"] = self.error
        if self.windows:
            payload["windows"] = [w.to_dict() for w in self.windows]
        return payload


@dataclass
class UsageRecord:
    usg_id: str
    created_at: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    cost_raw: int  # 单位 1e-8 USD
    key_id: str
    session_id: str
    plan: Optional[str] = None

    @property
    def cost_usd(self) -> float:
        return self.cost_raw / 100_000_000.0

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "usg_id": self.usg_id,
            "created_at": self.created_at,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_5m_tokens": self.cache_write_5m_tokens,
            "cache_write_1h_tokens": self.cache_write_1h_tokens,
            "cost_raw": self.cost_raw,
            "cost_usd": self.cost_usd,
            "key_id": self.key_id,
            "session_id": self.session_id,
            "plan": self.plan,
        }


class OpenCodeAPIError(Exception):
    """opencode.ai API 调用失败."""


class AuthError(OpenCodeAPIError):
    """认证失败 (token 无效/过期)."""


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------


def build_cookie_header(token: str) -> str:
    """规范化 token 为 Cookie 头中的 auth 段."""
    cookie = token.strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    if not cookie:
        return ""
    for part in cookie.split(";"):
        p = part.strip()
        if p.startswith("auth="):
            return p
    return f"auth={cookie}"


def _fetch(
    url: str,
    headers: dict[str, str],
    timeout: float = REQUEST_TIMEOUT,
    retries: int = FETCH_RETRIES,
) -> str:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                if status == 401 or status == 403:
                    raise AuthError(f"认证失败 (HTTP {status})，请重新登录")
                if status == 404:
                    raise OpenCodeAPIError("工作区不存在 (HTTP 404)")
                if status < 200 or status >= 300:
                    raise OpenCodeAPIError(f"请求返回 HTTP {status}")
                return resp.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if isinstance(exc, urllib.error.HTTPError):
                status = exc.code
                if status == 401 or status == 403:
                    raise AuthError(f"认证失败 (HTTP {status})，请重新登录") from exc
                if status == 404:
                    raise OpenCodeAPIError("工作区不存在 (HTTP 404)") from exc
                raise OpenCodeAPIError(f"请求返回 HTTP {status}") from exc
            if attempt < retries - 1:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
    if isinstance(last_exc, urllib.error.URLError):
        raise OpenCodeAPIError(f"网络错误: {last_exc.reason}") from last_exc
    raise OpenCodeAPIError(f"网络错误: {last_exc}") from last_exc


def _server_call(
    server_id: str, args: list[Any], referer_path: str, token: str
) -> str:
    """调用 opencode.ai/_server 的 server-fn 接口, 返回原始文本."""
    cookie = build_cookie_header(token)
    if not cookie:
        raise OpenCodeAPIError("token 为空")
    url = (
        "https://opencode.ai/_server?id="
        + urllib.parse.quote(server_id)
        + "&args="
        + urllib.parse.quote(json.dumps(args))
    )
    headers = {
        "Cookie": cookie,
        "X-Server-Id": server_id,
        "X-Server-Instance": f"server-fn:{int(time.time() * 1e6)}",
        "User-Agent": USER_AGENT,
        "Origin": "https://opencode.ai",
        "Referer": f"https://opencode.ai{referer_path}",
        "Accept": "text/javascript, application/json;q=0.9, */*;q=0.8",
    }
    return _fetch(url, headers)


# ---------------------------------------------------------------------------
# 工作区解析
# ---------------------------------------------------------------------------


def extract_workspace_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("wrk_") and len(value) > 4:
        return value
    match = _WORKSPACE_ID_RE.search(value)
    return match.group(0) if match else ""


def fetch_workspace_refs(token: str) -> list[tuple[str, str]]:
    """获取账号下所有工作区 (id, name)."""
    cookie = build_cookie_header(token)
    if not cookie:
        raise OpenCodeAPIError("token 为空")
    url = (
        "https://opencode.ai/_server?id="
        + urllib.parse.quote(WORKSPACE_SERVER_ID)
    )
    headers = {
        "Cookie": cookie,
        "X-Server-Id": WORKSPACE_SERVER_ID,
        "X-Server-Instance": f"server-fn:{int(time.time() * 1e6)}",
        "User-Agent": USER_AGENT,
        "Origin": "https://opencode.ai",
        "Referer": "https://opencode.ai",
        "Accept": "text/javascript, application/json;q=0.9, */*;q=0.8",
    }
    text = _fetch(url, headers)
    refs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _WORKSPACE_ENTRY_RE.finditer(text):
        workspace_id, name = m.group(1), m.group(2).strip()
        if workspace_id in seen:
            continue
        seen.add(workspace_id)
        refs.append((workspace_id, name))
    if not refs:
        raise OpenCodeAPIError("无法从账号数据解析工作区 ID")
    return refs


def resolve_workspace_id(hint: str, token: str) -> str:
    """将工作区提示 (id/name/Default) 解析为 wrk_xxx ID."""
    resolved = extract_workspace_id(hint)
    if resolved:
        return resolved
    refs = fetch_workspace_refs(token)
    hint_l = hint.strip().lower()
    if hint_l:
        for workspace_id, name in refs:
            if (
                workspace_id.lower() == hint_l
                or name.lower() == hint_l
            ):
                return workspace_id
    if refs:
        return refs[0][0]
    raise OpenCodeAPIError(f"无法从 \"{hint}\" 解析工作区 ID")


# ---------------------------------------------------------------------------
# 配额
# ---------------------------------------------------------------------------


def _parse_window(pct_first: re.Pattern, reset_first: re.Pattern, html: str) -> Optional[tuple[float, int]]:
    match = pct_first.search(html)
    if match:
        return float(match.group(1)), int(float(match.group(2)))
    match = reset_first.search(html)
    if match:
        return float(match.group(2)), int(float(match.group(1)))
    return None


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def parse_quota_html(html: str, now: Optional[datetime] = None) -> list[QuotaWindow]:
    now = now or datetime.now(timezone.utc)
    windows: list[QuotaWindow] = []
    pairs = [
        (LABEL_ROLLING, _ROLLING_PCT_FIRST, _ROLLING_RESET_FIRST),
        (LABEL_WEEKLY, _WEEKLY_PCT_FIRST, _WEEKLY_RESET_FIRST),
        (LABEL_MONTHLY, _MONTHLY_PCT_FIRST, _MONTHLY_RESET_FIRST),
    ]
    for label, pct_re, reset_re in pairs:
        parsed = _parse_window(pct_re, reset_re, html)
        if parsed:
            used = _clamp_percent(parsed[0])
            reset_in = parsed[1]
            reset_at = now + timedelta(seconds=reset_in)
            windows.append(
                QuotaWindow(
                    label=label,
                    used=used,
                    remaining=round(100.0 - used, 1),
                    total=100.0,
                    unit="%",
                    reset_at=reset_at.isoformat().replace("+00:00", "Z"),
                    reset_in_sec=reset_in,
                )
            )
    return windows


def fetch_quota(token: str, workspace_hint: str = "Default") -> QuotaResult:
    """获取单个工作区的配额 (5h/weekly/monthly)."""
    now = datetime.now(timezone.utc)
    updated_at = now.isoformat().replace("+00:00", "Z")
    hint = (workspace_hint or "Default").strip() or "Default"
    if not token.strip():
        return QuotaResult(
            name="Default", workspace_id=hint, success=False,
            updated_at=updated_at, error="未配置 token",
        )
    try:
        workspace_id = resolve_workspace_id(hint, token)
        cookie = build_cookie_header(token)
        if not cookie:
            raise OpenCodeAPIError("token 为空")
        url = f"{DASHBOARD_BASE}/{urllib.parse.quote(workspace_id)}/go"
        headers = {
            "Cookie": cookie,
            "User-Agent": USER_AGENT,
            "Accept": "text/html, application/xhtml+xml",
        }
        # dashboard HTML 较慢, 短超时 + 少重试, 避免长时间阻塞
        html = _fetch(url, headers, timeout=20.0, retries=2)
        windows = parse_quota_html(html, now)
        if not windows:
            raise OpenCodeAPIError("无法从 Dashboard HTML 解析额度数据")
        return QuotaResult(
            name="Default", workspace_id=workspace_id, success=True,
            updated_at=updated_at, windows=windows,
        )
    except Exception as exc:  # noqa: BLE001
        return QuotaResult(
            name="Default", workspace_id=hint, success=False,
            updated_at=updated_at, error=str(exc),
        )


# ---------------------------------------------------------------------------
# 用量记录
# ---------------------------------------------------------------------------


def _parse_num_field(body: str, name: str) -> int:
    match = re.search(rf"{re.escape(name)}:\s*(\d+|null)", body)
    if not match:
        return 0
    value = match.group(1)
    if value == "null":
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _parse_str_field(body: str, name: str) -> str:
    match = re.search(rf'{re.escape(name)}:\s*"([^"]*)"', body)
    return match.group(1) if match else ""


def parse_usage_response(text: str) -> list[UsageRecord]:
    """解析 server-fn 响应为 UsageRecord 列表.

    兼容两种序列化格式:
    - GET 方式: id:"usg_..." (68HUB 风格, 无空格)
    - POST 方式: id: "usg_..." (新格式, 有空格)
    """
    plans: dict[str, str] = {}
    for m in _PLAN_RE.finditer(text):
        plans[m.group(1)] = m.group(2)

    # 以 usg_id 锚点切分记录, 每个锚点到下一个锚点之间是一条记录体
    anchors = list(_RECORD_ANCHOR_RE.finditer(text))
    records: list[UsageRecord] = []
    for i, m in enumerate(anchors):
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        body = text[m.end():end]
        created_match = _CREATED_RE.search(body)
        if not created_match:
            continue
        usg_id = m.group(1)
        records.append(
            UsageRecord(
                usg_id=usg_id,
                created_at=created_match.group(1),
                model=_parse_str_field(body, "model"),
                provider=_parse_str_field(body, "provider"),
                input_tokens=_parse_num_field(body, "inputTokens"),
                output_tokens=_parse_num_field(body, "outputTokens"),
                reasoning_tokens=_parse_num_field(body, "reasoningTokens"),
                cache_read_tokens=_parse_num_field(body, "cacheReadTokens"),
                cache_write_5m_tokens=_parse_num_field(body, "cacheWrite5mTokens"),
                cache_write_1h_tokens=_parse_num_field(body, "cacheWrite1hTokens"),
                cost_raw=_parse_num_field(body, "cost"),
                key_id=_parse_str_field(body, "keyID"),
                session_id=_parse_str_field(body, "sessionID"),
                plan=plans.get(usg_id),
            )
        )
    return records


def fetch_usage_page(
    token: str,
    workspace_id: str,
    page: int = 0,
    key_id: Optional[str] = None,
    usage_server_id: Optional[str] = None,
) -> list[UsageRecord]:
    """拉取一页用量记录 (每页 50 条, page 从 0 开始).

    使用 GET /_server?id=...&args=[workspace_id, page] 方式 (68HUB 同款).
    """
    args: list[Any] = [workspace_id]
    if key_id:
        if page > 0:
            args.extend([page, key_id])
        else:
            args.append(key_id)
    elif page > 0:
        args.append(page)

    server_id = usage_server_id or DEFAULT_USAGE_SERVER_ID
    text = _server_call(server_id, args, f"/workspace/{workspace_id}/usage", token)
    return parse_usage_response(text)
