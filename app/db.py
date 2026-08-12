"""SQLite 存储与聚合查询.

Schema 与聚合口径移植自 68HUB electron/backend/db.ts.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Optional

_DB: Optional[sqlite3.Connection] = None
_data_dir_override: Optional[str] = None


def set_data_dir(path: str) -> None:
    global _data_dir_override
    _data_dir_override = path


def _default_data_dir() -> str:
    if _data_dir_override:
        return os.path.abspath(_data_dir_override)
    if os.environ.get("GOUSAGE_DATA"):
        return os.path.abspath(os.environ["GOUSAGE_DATA"])
    # 单文件 exe: 优先 exe 同目录 data/, 不可写则回退到 LOCALAPPDATA
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidate = os.path.join(exe_dir, "data")
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".write-test")
            with open(probe, "w", encoding="utf-8") as fh:
                fh.write("ok")
            os.remove(probe)
            return candidate
        except OSError:
            pass
        local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(local, "GoUsage", "data")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def data_dir() -> str:
    return _default_data_dir()


def db_path() -> str:
    return os.path.join(data_dir(), "gousage.db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_db() -> sqlite3.Connection:
    global _DB
    if _DB is not None:
        return _DB
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _DB = conn
    _init_schema(conn)
    return conn


def close_db() -> None:
    global _DB
    if _DB is not None:
        _DB.close()
        _DB = None


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS account (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_records (
          usg_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          model TEXT NOT NULL,
          provider TEXT,
          input_tokens INTEGER NOT NULL,
          output_tokens INTEGER NOT NULL,
          reasoning_tokens INTEGER NOT NULL DEFAULT 0,
          cache_read_tokens INTEGER NOT NULL DEFAULT 0,
          cache_write_5m_tokens INTEGER NOT NULL DEFAULT 0,
          cache_write_1h_tokens INTEGER NOT NULL DEFAULT 0,
          cost_raw INTEGER NOT NULL,
          cost_usd REAL NOT NULL,
          key_id TEXT,
          session_id TEXT,
          plan TEXT,
          synced_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_records(created_at DESC);

        CREATE TABLE IF NOT EXISTS usage_sync_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_error TEXT,
          last_inserted_count INTEGER NOT NULL DEFAULT 0,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
          total_records INTEGER NOT NULL DEFAULT 0,
          oldest_record_at TEXT,
          newest_record_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          payload TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    # 确保 settings 行存在
    if conn.execute("SELECT id FROM settings WHERE id = 1").fetchone() is None:
        conn.execute("INSERT INTO settings (id, payload, updated_at) VALUES (1, '{}', ?)", (_now_iso(),))
        conn.commit()
    # 迁移: 旧库补充新列
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(usage_records)").fetchall()}
    for col in ("reasoning_tokens", "session_id"):
        if col not in cols:
            if col == "reasoning_tokens":
                conn.execute(f"ALTER TABLE usage_records ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            else:
                conn.execute(f"ALTER TABLE usage_records ADD COLUMN {col} TEXT")
    # 确保账户行存在
    row = conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
    if row is None:
        now = _now_iso()
        conn.execute(
            "INSERT INTO account (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)"
            " VALUES (1, 'Default', 'Default', NULL, '', ?, ?)",
            (now, now),
        )
    sync = conn.execute("SELECT id FROM usage_sync_state WHERE id = 1").fetchone()
    if sync is None:
        conn.execute("INSERT INTO usage_sync_state (id) VALUES (1)")
    conn.commit()


# ---------------------------------------------------------------------------
# 账户 / token
# ---------------------------------------------------------------------------


def get_account() -> dict[str, Any]:
    row = get_db().execute(
        "SELECT * FROM account WHERE id = 1"
    ).fetchone()
    if row is None:
        return {}
    return {
        "name": row["name"],
        "workspace_id": row["workspace_id"],
        "resolved_workspace_id": row["resolved_workspace_id"],
        "has_token": bool(row["token"].strip()),
    }


def save_token(token: str, workspace_id: str = "Default") -> None:
    conn = get_db()
    now = _now_iso()
    conn.execute(
        """UPDATE account SET token = ?, workspace_id = ?, resolved_workspace_id = NULL,
           updated_at = ? WHERE id = 1""",
        (token.strip(), workspace_id.strip() or "Default", now),
    )
    conn.execute(
        "UPDATE usage_sync_state SET deepest_page_fetched = -1 WHERE id = 1"
    )
    conn.commit()


def save_resolved_workspace(workspace_id: str) -> None:
    conn = get_db()
    conn.execute(
        "UPDATE account SET resolved_workspace_id = ?, updated_at = ? WHERE id = 1",
        (workspace_id, _now_iso()),
    )
    conn.commit()


def get_token() -> str:
    row = get_db().execute("SELECT token FROM account WHERE id = 1").fetchone()
    return row["token"] if row else ""


def get_workspace_hint() -> str:
    row = get_db().execute(
        "SELECT workspace_id, resolved_workspace_id FROM account WHERE id = 1"
    ).fetchone()
    if row is None:
        return "Default"
    return row["resolved_workspace_id"] or row["workspace_id"] or "Default"


def clear_account() -> None:
    import traceback
    print("[db] clear_account called from:", "".join(traceback.format_stack()[-6:]), flush=True)
    conn = get_db()
    conn.execute("DELETE FROM usage_records")
    conn.execute("UPDATE account SET token = '', resolved_workspace_id = NULL, updated_at = ? WHERE id = 1", (_now_iso(),))
    conn.execute(
        "UPDATE usage_sync_state SET last_sync_status = NULL, last_sync_error = NULL,"
        " last_inserted_count = 0, deepest_page_fetched = -1, total_records = 0,"
        " oldest_record_at = NULL, newest_record_at = NULL WHERE id = 1"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 用量记录写入 / 同步状态
# ---------------------------------------------------------------------------


def insert_usage_records(records: list[dict[str, Any]]) -> int:
    """批量写入, 按 usg_id 去重; 返回新增条数."""
    if not records:
        return 0
    conn = get_db()
    synced_at = _now_iso()
    stmt = (
        "INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens,"
        " output_tokens, reasoning_tokens, cache_read_tokens, cache_write_5m_tokens,"
        " cache_write_1h_tokens, cost_raw, cost_usd, key_id, session_id, plan, synced_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(usg_id) DO UPDATE SET"
        " input_tokens = excluded.input_tokens,"
        " output_tokens = excluded.output_tokens,"
        " reasoning_tokens = excluded.reasoning_tokens,"
        " cache_read_tokens = excluded.cache_read_tokens,"
        " cache_write_5m_tokens = excluded.cache_write_5m_tokens,"
        " cache_write_1h_tokens = excluded.cache_write_1h_tokens,"
        " cost_raw = excluded.cost_raw, cost_usd = excluded.cost_usd,"
        " synced_at = excluded.synced_at"
    )
    inserted = 0
    try:
        conn.execute("BEGIN")
        for rec in records:
            cur = conn.execute(
                "SELECT 1 FROM usage_records WHERE usg_id = ?", (rec["usg_id"],)
            )
            existed = cur.fetchone() is not None
            conn.execute(
                stmt,
                (
                    rec["usg_id"], rec["created_at"], rec["model"], rec.get("provider"),
                    rec["input_tokens"], rec["output_tokens"], rec["reasoning_tokens"],
                    rec["cache_read_tokens"], rec["cache_write_5m_tokens"],
                    rec["cache_write_1h_tokens"], rec["cost_raw"], rec["cost_usd"],
                    rec.get("key_id"), rec.get("session_id"), rec.get("plan"),
                    synced_at,
                ),
            )
            if not existed:
                inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return inserted


def get_sync_state() -> dict[str, Any]:
    row = get_db().execute("SELECT * FROM usage_sync_state WHERE id = 1").fetchone()
    if row is None:
        return {}
    return {
        "last_sync_at": row["last_sync_at"],
        "last_sync_status": row["last_sync_status"],
        "last_sync_error": row["last_sync_error"],
        "last_inserted_count": row["last_inserted_count"],
        "deepest_page_fetched": row["deepest_page_fetched"],
        "total_records": row["total_records"],
        "oldest_record_at": row["oldest_record_at"],
        "newest_record_at": row["newest_record_at"],
    }


def update_sync_state(status: str, error: Optional[str] = None, inserted: int = 0) -> None:
    conn = get_db()
    conn.execute(
        """UPDATE usage_sync_state
           SET last_sync_at = ?, last_sync_status = ?, last_sync_error = ?,
               last_inserted_count = last_inserted_count + ?
           WHERE id = 1""",
        (_now_iso(), status, error, inserted),
    )
    _refresh_sync_totals(conn)
    conn.commit()


def _refresh_sync_totals(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT COUNT(*) AS total, MIN(created_at) AS oldest, MAX(created_at) AS newest"
        " FROM usage_records"
    ).fetchone()
    conn.execute(
        "UPDATE usage_sync_state SET total_records = ?, oldest_record_at = ?, newest_record_at = ?"
        " WHERE id = 1",
        (row["total"], row["oldest"], row["newest"]),
    )


# ---------------------------------------------------------------------------
# 明细分页查询 + 设置
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS = {
    "sync_interval_sec": 300,  # 自动增量同步间隔 (1/5/15/30 分钟)
    "window_days": 60,  # 同步范围: 30/60/90/180, None=所有
    "auto_sync": True,  # 自动增量同步开关
}


def prune_old_records(window_days: int | None) -> int:
    """按同步范围裁剪过期记录, 返回删除条数. window_days=None 时不裁剪."""
    if window_days is None:
        return 0
    window_days = max(1, min(int(window_days), 3650))
    cur = get_db().execute(
        "DELETE FROM usage_records WHERE datetime(created_at) < datetime('now', ?)",
        (f"-{window_days} days",),
    )
    get_db().commit()
    return cur.rowcount


def usage_records_page(
    page: int = 1,
    page_size: int = 20,
    model: Optional[str] = None,
    days: Optional[int] = None,
) -> tuple[list[dict[str, Any]], int]:
    """用量明细分页查询 (按时间倒序), 返回 (records, total)."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    where: list[str] = []
    params: list[Any] = []
    if model:
        where.append("model = ?")
        params.append(model)
    if days:
        where.append("datetime(created_at) >= datetime('now', ?)")
        params.append(f"-{days} days")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_db()
    total = int(
        conn.execute(f"SELECT COUNT(*) AS c FROM usage_records {where_sql}", params).fetchone()["c"]
    )
    rows = conn.execute(
        f"SELECT * FROM usage_records {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    records = []
    for r in rows:
        rec = {
            "usg_id": r["usg_id"],
            "created_at": r["created_at"],
            "model": r["model"],
            "provider": r["provider"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "reasoning_tokens": r["reasoning_tokens"],
            "cache_read_tokens": r["cache_read_tokens"],
            "cache_write_tokens": (r["cache_write_5m_tokens"] or 0) + (r["cache_write_1h_tokens"] or 0),
            "cost_usd": r["cost_usd"],
            "session_id": r["session_id"],
            "plan": r["plan"],
        }
        records.append(rec)
    return records, total


def list_models() -> list[str]:
    rows = get_db().execute(
        "SELECT DISTINCT model FROM usage_records ORDER BY model"
    ).fetchall()
    return [r["model"] for r in rows]


def get_settings() -> dict[str, Any]:
    row = get_db().execute("SELECT payload FROM settings WHERE id = 1").fetchone()
    if not row:
        return dict(_DEFAULT_SETTINGS)
    try:
        data = json.loads(row["payload"])
        if not isinstance(data, dict):
            return dict(_DEFAULT_SETTINGS)
    except (TypeError, ValueError):
        return dict(_DEFAULT_SETTINGS)
    merged = dict(_DEFAULT_SETTINGS)
    merged.update({k: v for k, v in data.items() if k in _DEFAULT_SETTINGS})
    return merged


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = get_settings()
    for key in _DEFAULT_SETTINGS:
        if key in payload and payload[key] is not None:
            if key == "sync_interval_sec":
                try:
                    current[key] = max(30, min(int(payload[key]), 3600))
                except (TypeError, ValueError):
                    pass
            elif key == "window_days":
                val = payload[key]
                if val is None or val == "" or str(val).lower() in ("all", "所有"):
                    current[key] = None
                else:
                    try:
                        current[key] = max(1, min(int(val), 3650))
                    except (TypeError, ValueError):
                        pass
            elif key == "auto_sync":
                current[key] = bool(payload[key])
            else:
                current[key] = payload[key]
    conn = get_db()
    conn.execute(
        "UPDATE settings SET payload = ?, updated_at = ? WHERE id = 1",
        (json.dumps(current, ensure_ascii=False), _now_iso()),
    )
    conn.commit()
    return current

_PERIOD_CLAUSES = {
    "5h": "datetime(created_at) >= datetime('now', '-5 hours')",
    "today": "substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')",
}


def _period_where(period: str) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if period in _PERIOD_CLAUSES:
        clauses.append(_PERIOD_CLAUSES[period])
    elif period != "all":
        days = 30
        match = _NUM_DAYS_RE.match(period or "")
        if match:
            days = max(1, int(match.group(1)))
        clauses.append("datetime(created_at) >= datetime('now', ?)")
        params.append(f"-{days} days")
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


_NUM_DAYS_RE = __import__("re").compile(r"^(\d+)d$")


def model_stats(period: str = "30d") -> list[dict[str, Any]]:
    """按模型聚合: 请求数 / 会话数 / 输入(含缓存) / 普通输入 / 推理 / 缓存命中 / 缓存写入 / 输出 / 成本 / 命中率."""
    where, params = _period_where(period)
    rows = get_db().execute(
        f"""
        SELECT model,
               COUNT(*) AS request_count,
               COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END) AS session_count,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cache_read_tokens) AS cache_hit_tokens,
               SUM(cache_write_5m_tokens + cache_write_1h_tokens) AS cache_write_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(cost_usd) AS total_cost_usd
        FROM usage_records
        {where}
        GROUP BY model
        ORDER BY (SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens)
                  + SUM(output_tokens)) DESC
        """,
        params,
    ).fetchall()
    result: list[dict[str, Any]] = []
    for r in rows:
        hit = int(r["cache_hit_tokens"] or 0)
        miss = int(r["uncached_input_tokens"] or 0)
        hit_rate = (hit / (hit + miss) * 100) if (hit + miss) > 0 else 0.0
        result.append(
            {
                "model": r["model"],
                "request_count": int(r["request_count"]),
                "session_count": int(r["session_count"] or 0),
                "total_input_tokens": int(r["total_input_tokens"] or 0),
                "uncached_input_tokens": miss,
                "total_reasoning_tokens": int(r["total_reasoning_tokens"] or 0),
                "cache_hit_tokens": hit,
                "cache_write_tokens": int(r["cache_write_tokens"] or 0),
                "total_output_tokens": int(r["total_output_tokens"] or 0),
                "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
                "hit_rate": round(hit_rate, 2),
            }
        )
    return result


def daily_stats(days: int = 30) -> list[dict[str, Any]]:
    """每日聚合: 输入(含缓存) / 普通输入 / 推理 / 缓存命中 / 缓存写入 / 输出 / 成本 / 请求数."""
    days = max(1, min(days, 365))
    rows = get_db().execute(
        """
        SELECT substr(datetime(created_at, 'localtime'), 1, 10) AS date,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cache_read_tokens) AS cache_hit_tokens,
               SUM(cache_write_5m_tokens + cache_write_1h_tokens) AS cache_write_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(cost_usd) AS total_cost_usd,
               COUNT(*) AS request_count
        FROM usage_records
        WHERE substr(datetime(created_at, 'localtime'), 1, 10) >= date('now', 'localtime', ?)
        GROUP BY substr(datetime(created_at, 'localtime'), 1, 10)
        ORDER BY date ASC
        """,
        (f"-{days} days",),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for r in rows:
        hit = int(r["cache_hit_tokens"] or 0)
        miss = int(r["uncached_input_tokens"] or 0)
        hit_rate = (hit / (hit + miss) * 100) if (hit + miss) > 0 else 0.0
        result.append(
            {
                "date": r["date"],
                "total_input_tokens": int(r["total_input_tokens"] or 0),
                "uncached_input_tokens": miss,
                "total_reasoning_tokens": int(r["total_reasoning_tokens"] or 0),
                "cache_hit_tokens": hit,
                "cache_write_tokens": int(r["cache_write_tokens"] or 0),
                "total_output_tokens": int(r["total_output_tokens"] or 0),
                "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
                "request_count": int(r["request_count"]),
                "hit_rate": round(hit_rate, 2),
            }
        )
    return result


def today_trend() -> list[dict[str, Any]]:
    """今日 24 小时趋势: 每小时 输入/输出/推理 (本地时区, 无数据补 0)."""
    rows = get_db().execute(
        """
        SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS h,
               SUM(input_tokens) AS input,
               SUM(output_tokens) AS output,
               SUM(reasoning_tokens) AS reasoning
        FROM usage_records
        WHERE substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')
        GROUP BY h
        """
    ).fetchall()
    by_hour = {int(r["h"]): r for r in rows}
    result: list[dict[str, Any]] = []
    for h in range(24):
        r = by_hour.get(h)
        result.append(
            {
                "hour": f"{h:02d}:00",
                "input": int(r["input"]) if r else 0,
                "output": int(r["output"]) if r else 0,
                "reasoning": int(r["reasoning"]) if r else 0,
            }
        )
    return result


def totals(period: str = "30d") -> dict[str, Any]:
    """总览指标, 口径与模型占比一致."""
    where, params = _period_where(period)
    row = get_db().execute(
        f"""
        SELECT COUNT(*) AS request_count,
               COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END) AS session_count,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cache_read_tokens) AS cache_hit_tokens,
               SUM(cache_write_5m_tokens + cache_write_1h_tokens) AS cache_write_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(cost_usd) AS total_cost_usd
        FROM usage_records
        {where}
        """,
        params,
    ).fetchone()
    if row is None or row["request_count"] is None:
        return {
            "request_count": 0, "session_count": 0, "total_input_tokens": 0,
            "uncached_input_tokens": 0, "total_reasoning_tokens": 0,
            "cache_hit_tokens": 0, "cache_write_tokens": 0,
            "total_output_tokens": 0, "total_cost_usd": 0.0, "hit_rate": 0.0,
        }
    hit = int(row["cache_hit_tokens"] or 0)
    miss = int(row["uncached_input_tokens"] or 0)
    hit_rate = (hit / (hit + miss) * 100) if (hit + miss) > 0 else 0.0
    return {
        "request_count": int(row["request_count"] or 0),
        "session_count": int(row["session_count"] or 0),
        "total_input_tokens": int(row["total_input_tokens"] or 0),
        "uncached_input_tokens": miss,
        "total_reasoning_tokens": int(row["total_reasoning_tokens"] or 0),
        "cache_hit_tokens": hit,
        "cache_write_tokens": int(row["cache_write_tokens"] or 0),
        "total_output_tokens": int(row["total_output_tokens"] or 0),
        "total_cost_usd": round(float(row["total_cost_usd"] or 0), 6),
        "hit_rate": round(hit_rate, 2),
    }
