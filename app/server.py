"""本地 HTTP 服务: 静态资源 + JSON API + 后台同步."""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from . import db
from .opencode_api import (
    AuthError,
    OpenCodeAPIError,
    fetch_quota,
    fetch_usage_page,
    resolve_workspace_id,
)

PAGE_SIZE = 50
QUOTA_CACHE_TTL = 30.0
INCREMENTAL_PAGES = 5  # 增量同步最多拉取的页数 (5*50=250 条)
MAX_FULL_PAGES = 2000  # 全量同步上限, 防失控
FETCH_BATCH = 5  # 并发拉取页数 (服务端响应慢, 并发提速)


def _resource_path(rel: str) -> str:
    """定位资源文件 (开发/打包后通用)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "app", "web", rel)
    return os.path.join(os.path.dirname(__file__), "web", rel)


# ---------------------------------------------------------------------------
# 同步状态 (跨线程)
# ---------------------------------------------------------------------------

_sync_lock = threading.Lock()
_sync_state: dict[str, Any] = {
    "running": False,
    "mode": "",
    "page": 0,
    "inserted": 0,
    "phase": "idle",  # idle | quota | usage | done | error
    "message": "",
}
_quota_cache: dict[str, Any] = {"at": 0.0, "data": None}
_quota_refreshing = False  # 防重入: 同一时刻只允许一个 quota 刷新线程
_exchange_cache: dict[str, Any] = {"at": 0.0, "usd_cny": 7.2}
_EXCHANGE_TTL = 6 * 3600  # 汇率缓存 6 小时
_DEFAULT_USD_CNY = 7.2


def _fetch_usd_cny() -> float:
    """从 open.er-api.com 获取 USD→CNY 汇率, 失败时返回上次缓存/默认值."""
    now = time.time()
    if now - _exchange_cache["at"] < _EXCHANGE_TTL:
        return _exchange_cache["usd_cny"]
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "GoUsage/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        rate = float(data.get("rates", {}).get("CNY") or 0)
        if rate > 0:
            _exchange_cache.update(at=now, usd_cny=rate)
    except Exception:  # noqa: BLE001 网络失败时保留旧值
        _exchange_cache["at"] = now
    return _exchange_cache["usd_cny"]


def _sync_progress_snapshot() -> dict[str, Any]:
    with _sync_lock:
        return dict(_sync_state)


def _set_phase(phase: str, message: str = "") -> None:
    with _sync_lock:
        _sync_state["phase"] = phase
        _sync_state["message"] = message
        _sync_state["running"] = phase in ("quota", "usage")


# ---------------------------------------------------------------------------
# 同步执行
# ---------------------------------------------------------------------------


def _fetch_quota_with_cache(token: str, workspace_hint: str) -> dict[str, Any]:
    now = time.time()
    if _quota_cache["data"] and now - _quota_cache["at"] < QUOTA_CACHE_TTL:
        return _quota_cache["data"]
    result = fetch_quota(token, workspace_hint)
    _quota_cache["at"] = now
    _quota_cache["data"] = result.to_dict()
    return _quota_cache["data"]


def _ensure_quota_async() -> None:
    """若配额缓存过期, 在后台线程刷新 (不阻塞 dashboard 响应, 防重入)."""
    global _quota_refreshing
    now = time.time()
    if _quota_cache["data"] and now - _quota_cache["at"] < QUOTA_CACHE_TTL:
        return
    if _quota_refreshing:
        return  # 已有刷新线程在跑
    token = db.get_token()
    if not token:
        return
    workspace_hint = db.get_workspace_hint()
    _quota_refreshing = True

    def worker() -> None:
        global _quota_refreshing
        try:
            # 失败也写入缓存 (None), 60 秒内不再重试, 避免前端无限刷新
            _fetch_quota_with_cache(token, workspace_hint)
        except Exception:  # noqa: BLE001
            _quota_cache["at"] = time.time()
            _quota_cache["data"] = None
        finally:
            _quota_refreshing = False

    threading.Thread(target=worker, daemon=True, name="gousage-quota").start()


def _fetch_usage_batch(
    token: str, workspace_id: str, pages: list[int]
) -> dict[int, Any]:
    """并发拉取多页, 返回 {page: records | Exception}."""
    results: dict[int, Any] = {}
    with ThreadPoolExecutor(max_workers=FETCH_BATCH) as executor:
        futures = {
            executor.submit(fetch_usage_page, token, workspace_id, p): p
            for p in pages
        }
        for future in as_completed(futures):
            page = futures[future]
            try:
                results[page] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[page] = exc
    return results


def sync_usage(mode: str = "incremental") -> dict[str, Any]:
    """同步用量记录: full=首次全量拉取; incremental=增量 (只拉最新几页).

    按设置中的同步范围 (window_days) 拉取与裁剪:
    - window_days=None ("所有"): 拉取至空页 (受 MAX_FULL_PAGES 保险上限)
    - window_days=N: 首次拉取至页内最早记录早于窗口边界; 同步后裁剪过期记录
    """
    token = db.get_token()
    if not token:
        return {"ok": False, "error": "未登录"}
    workspace_id = db.get_workspace_hint()
    window_days = db.get_settings().get("window_days")

    with _sync_lock:
        if _sync_state["running"]:
            return {"ok": False, "error": "已有同步任务进行中"}
        _sync_state.update(running=True, mode=mode, page=0, inserted=0, phase="usage", message="")

    try:
        # 确保工作区 ID 已解析
        try:
            resolved = resolve_workspace_id(workspace_id, token)
            if not workspace_id.startswith("wrk_"):
                workspace_id = resolved
                db.save_resolved_workspace(resolved)
        except (AuthError, OpenCodeAPIError) as exc:
            _set_phase("error", f"工作区解析失败: {exc}")
            db.update_sync_state("error", str(exc))
            return {"ok": False, "error": str(exc)}

        total_inserted = 0
        max_pages = MAX_FULL_PAGES if mode == "full" else INCREMENTAL_PAGES
        page = 0
        empty_batches = 0
        failed_pages = 0
        window_boundary_reached = False

        while page < max_pages:
            batch_pages = list(range(page, min(page + FETCH_BATCH, max_pages)))
            with _sync_lock:
                _sync_state["page"] = page
            results = _fetch_usage_batch(token, workspace_id, batch_pages)

            batch_inserted = 0
            batch_full_pages = 0
            batch_failed = 0
            for p in sorted(results):
                result = results[p]
                if isinstance(result, Exception):
                    batch_failed += 1
                    continue
                if not result:
                    continue  # 空页: 数据到底
                # 同步范围: 全量拉取时, 若本页最早记录早于窗口边界 → 该页整页保留后停止
                if mode == "full" and window_days is not None:
                    earliest = min((r.created_at for r in result), default="")
                    if earliest:
                        try:
                            from datetime import datetime, timedelta, timezone
                            et = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
                            boundary = datetime.now(timezone.utc) - timedelta(days=window_days)
                            if et < boundary:
                                window_boundary_reached = True
                        except (ValueError, TypeError):
                            pass
                inserted = db.insert_usage_records([r.to_db_dict() for r in result])
                total_inserted += inserted
                batch_inserted += inserted
                if len(result) >= PAGE_SIZE:
                    batch_full_pages += 1
                with _sync_lock:
                    _sync_state["inserted"] = total_inserted

            page += FETCH_BATCH

            if window_boundary_reached:
                break
            if batch_failed:
                failed_pages += batch_failed
                if mode == "incremental":
                    msg = "网络请求失败 (IncompleteRead/超时)"
                    _set_phase("error", f"第 {page - FETCH_BATCH + 1} 页拉取失败: {msg}")
                    db.update_sync_state("error", msg, total_inserted)
                    return {"ok": False, "error": msg, "partial_inserted": total_inserted}

            # 本批没有任何满页 → 到底了
            if batch_full_pages == 0:
                break
            # 增量模式: 连续两批全部是旧数据 (插入 0 条) → 停止
            if mode == "incremental" and batch_inserted == 0:
                empty_batches += 1
                if empty_batches >= 2:
                    break
            else:
                empty_batches = 0

        # 按同步范围裁剪窗口外记录 (与本次新增数独立)
        if window_days is not None:
            db.prune_old_records(window_days)

        if failed_pages:
            msg = f"完成, 但 {failed_pages} 页拉取失败 (数据不完整, 可再次全量同步补全)"
            db.update_sync_state("partial", msg, total_inserted)
            _set_phase("done", msg)
            return {"ok": True, "partial": True, "failed_pages": failed_pages,
                    "inserted": total_inserted, "pages": page}
        db.update_sync_state("ok", None, total_inserted)
        _set_phase("done", f"同步完成, 新增 {total_inserted} 条")
        return {"ok": True, "inserted": total_inserted, "pages": page}
    except Exception as exc:  # noqa: BLE001
        db.update_sync_state("error", str(exc))
        _set_phase("error", str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        with _sync_lock:
            _sync_state["running"] = False


def sync_all_async(mode: str) -> None:
    """后台线程执行 用量同步 (配额由独立后台线程刷新, 不阻塞用量)."""
    def worker() -> None:
        try:
            _ensure_quota_async()  # 触发配额后台刷新 (独立线程, 防重入)
            sync_usage(mode)
        except Exception:  # noqa: BLE001
            _set_phase("error", "同步失败")

    thread = threading.Thread(target=worker, daemon=True, name="gousage-sync")
    thread.start()


# ---------------------------------------------------------------------------
# HTTP 服务
# ---------------------------------------------------------------------------

_on_open_login: Optional[Callable[[], None]] = None
_server: Optional[ThreadingHTTPServer] = None


def set_login_callback(callback: Callable[[], None]) -> None:
    """由 main.py 注册: 前端请求重新登录时触发窗口跳转."""
    global _on_open_login
    _on_open_login = callback


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _static_response(handler: BaseHTTPRequestHandler, rel: str) -> None:
    # 防目录穿越
    rel = rel.lstrip("/")
    if ".." in rel.replace("\\", "/").split("/"):
        handler.send_error(403)
        return
    path = _resource_path(rel)
    if not os.path.isfile(path):
        handler.send_error(404)
        return
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        with open(path, "rb") as fh:
            body = fh.read()
    except OSError:
        handler.send_error(500)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def _handle_api(handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]]) -> None:
    method = handler.command
    route = path

    if route == "/api/state" and method == "GET":
        account = db.get_account()
        sync = db.get_sync_state()
        _json_response(
            handler,
            {
                "logged_in": account.get("has_token", False),
                "account": account,
                "sync": sync,
                "progress": _sync_progress_snapshot(),
                "datadir": db.data_dir(),
            },
        )
        return

    if route == "/api/sync" and method == "POST":
        mode = (query.get("mode") or ["incremental"])[0]
        if mode not in ("incremental", "full"):
            _json_response(handler, {"ok": False, "error": "invalid mode"}, 400)
            return
        token = db.get_token()
        if not token:
            _json_response(handler, {"ok": False, "error": "未登录"}, 401)
            return
        sync_all_async(mode)
        _json_response(handler, {"ok": True})
        return

    if route == "/api/dashboard" and method == "GET":
        # 时间范围: today / 7d / 30d / all
        range_param = query.get("range", ["today"])[0]
        if range_param == "today":
            period, days = "today", 1
        elif range_param == "7d":
            period, days = "7d", 7
        elif range_param == "all":
            period, days = "all", 365
        else:
            period, days = "30d", 30
        token = db.get_token()
        # quota 使用缓存, 过期时后台刷新, 不阻塞 dashboard 响应
        _ensure_quota_async()
        quota = _quota_cache["data"] if token else None
        _json_response(
            handler,
            {
                "logged_in": bool(token),
                "quota": quota,
                "totals": db.totals(period),
                "today": db.totals("today"),
                "daily": db.daily_stats(7),  # 每日趋势固定显示近 7 天
                "trend": db.daily_stats(30),  # 用量趋势 (费用/请求双轴)
                "today_trend": db.today_trend(),  # 今日 24 小时趋势
                "models": db.model_stats(period),
                "sync": db.get_sync_state(),
                "progress": _sync_progress_snapshot(),
                "range": range_param,
                "exchange_rate": {"usd_cny": _fetch_usd_cny(), "currency": "CNY"},
                "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        return

    if route == "/api/logout" and method == "POST":
        db.clear_account()
        _json_response(handler, {"ok": True})
        return

    if route == "/api/relogin" and method == "POST":
        db.clear_account()
        if _on_open_login:
            _on_open_login()
        _json_response(handler, {"ok": True})
        return

    if route == "/api/usage/records" and method == "GET":
        try:
            page = max(1, int(query.get("page", ["1"])[0]))
        except ValueError:
            page = 1
        try:
            page_size = max(1, min(int(query.get("page_size", ["50"])[0]), 100))
        except ValueError:
            page_size = 50
        model = query.get("model", [""])[0] or None
        days_raw = query.get("days", [""])[0]
        try:
            days = max(1, min(int(days_raw), 365)) if days_raw else None
        except ValueError:
            days = None
        records, total = db.usage_records_page(page, page_size, model, days)
        _json_response(
            handler,
            {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "models": db.list_models(),
                "filter": {"model": model, "days": days},
            },
        )
        return

    if route == "/api/settings" and method == "GET":
        _json_response(handler, db.get_settings())
        return

    if route == "/api/settings" and method == "PUT":
        try:
            length = int(handler.headers.get("Content-Length") or 0)
            body = json.loads(handler.rfile.read(length).decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": "无效请求体"}, 400)
            return
        _json_response(handler, db.save_settings(body))
        return

    handler.send_error(404)


class _Handler(BaseHTTPRequestHandler):
    server_version = "GoUsage/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # 静默日志
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                _handle_api(self, path, query)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, {"ok": False, "error": str(exc)}, 500)
            return
        if path == "/" or path == "":
            _static_response(self, "index.html")
        else:
            _static_response(self, path)

    def do_POST(self) -> None:  # noqa: N802
        self._handle_api_request()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle_api_request()

    def _handle_api_request(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                _handle_api(self, path, query)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, {"ok": False, "error": str(exc)}, 500)
            return
        self.send_error(404)


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[str, int]:
    """启动 HTTP 服务, 返回 (host, port)."""
    global _server
    _server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True, name="gousage-http")
    thread.start()
    return _server.server_address[0], _server.server_address[1]


def stop_server() -> None:
    global _server
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None
