"""SQLite 存储与聚合查询 (多账号版).

账号模型:
- ``accounts`` 表存放多个 OpenCode Go 账号 (各自持有 token/workspace),
  ``settings.payload`` 中的 ``active_account_id`` 指向当前活跃账号;
- 所有用量记录通过 ``usage_records.account_id`` 归属账号;
- 同步状态 ``usage_sync_state`` 以 account_id 为主键, 每账号一份增量游标.
兼容约定: 历史函数名保持不变, 未显式传 account_id 时一律作用于活跃账号.
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
        return os.path.join(local, "GoGauge", "data")
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


# ---------------------------------------------------------------------------
# schema 初始化与存量迁移
# ---------------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


_SS_TAIL = """
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_error TEXT,
          last_inserted_count INTEGER NOT NULL DEFAULT 0,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
          total_records INTEGER NOT NULL DEFAULT 0,
          oldest_record_at TEXT,
          newest_record_at TEXT"""


def _init_schema(conn: sqlite3.Connection) -> None:
    # 新形状建表: usage_records 自带 account_id; accounts 多行; 同步状态按账号主键
    conn.executescript(
        """
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
          synced_at TEXT NOT NULL,
          account_id INTEGER NOT NULL DEFAULT 1,
          local_date TEXT  -- 本地日 "YYYY-MM-DD"; 见 _init_schema 迁移说明
        );

        CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_records(created_at DESC);

        CREATE TABLE IF NOT EXISTS accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_sync_state (
          account_id INTEGER PRIMARY KEY,
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

    # 迁移 1: 旧单行 account 表 -> accounts 多行表 (仅当目标为空时拷贝, 保证幂等)
    if _table_exists(conn, "account"):
        empty = conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"] == 0
        if empty:
            conn.execute(
                """INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
                   SELECT id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at FROM account"""
            )
        conn.execute("DROP TABLE account")
        conn.commit()

    # 全新库: 种子默认空账号 (未登录态, 与历史行为一致)
    if conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"] == 0:
        now = _now_iso()
        conn.execute(
            "INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)"
            " VALUES (1, 'Default', 'Default', NULL, '', ?, ?)",
            (now, now),
        )
        conn.commit()

    # 迁移 2: 旧库补充新列 (含本次的 account_id 维度列)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(usage_records)").fetchall()}
    for col, ddl in (
        ("reasoning_tokens", "ALTER TABLE usage_records ADD COLUMN reasoning_tokens INTEGER NOT NULL DEFAULT 0"),
        ("session_id", "ALTER TABLE usage_records ADD COLUMN session_id TEXT"),
        ("account_id", "ALTER TABLE usage_records ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1"),
    ):
        if col not in cols:
            conn.execute(ddl)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_account_time ON usage_records(account_id, created_at DESC)"
    )

    # 迁移 3: 单行 usage_sync_state(id 主键) 重建为按账号多行 (数据无损搬运)
    ss_cols = {row["name"] for row in conn.execute("PRAGMA table_info(usage_sync_state)").fetchall()}
    if ss_cols and "id" in ss_cols and "account_id" not in ss_cols:
        conn.executescript(
            f"""
            ALTER TABLE usage_sync_state RENAME TO usage_sync_state_legacy;
            CREATE TABLE usage_sync_state (
              account_id INTEGER PRIMARY KEY,{_SS_TAIL}
            );
            INSERT INTO usage_sync_state (account_id, last_sync_at, last_sync_status, last_sync_error,
                                          last_inserted_count, deepest_page_fetched, total_records,
                                          oldest_record_at, newest_record_at)
            SELECT id, last_sync_at, last_sync_status, last_sync_error,
                   last_inserted_count, deepest_page_fetched, total_records,
                   oldest_record_at, newest_record_at FROM usage_sync_state_legacy;
            DROP TABLE usage_sync_state_legacy;
            """
        )
    conn.commit()

    # 迁移 4: opencode.ai 2026-09 改版后旧会话 Cookie (auth=…) 已失效,
    # 置空凭证让应用回到欢迎页引导重新登录 (新格式 __Host-console_session=… 不受影响);
    # 仅清凭证不删历史记录, 幂等
    conn.execute("UPDATE accounts SET token = '' WHERE token LIKE 'auth=%'")

    # 迁移 5: 新增 local_date 列 (本地日 "YYYY-MM-DD") + (account_id, local_date) 索引.
    #
    # 时间过滤原先写作 datetime(created_at) / substr(datetime(created_at,'localtime'),1,10),
    # 函数包裹索引列使 SQLite 无法范围扫描, 每个周期查询都退化为按账号全表扫描
    # (dashboard 一次刷新要跑多条聚合). 但 localtime 是非确定性函数, SQLite 会直接
    # 拒绝为它建表达式索引, 故改为写入时落一列 local_date, 再建确定性索引.
    rec_cols = {row["name"] for row in conn.execute("PRAGMA table_info(usage_records)").fetchall()}
    if "local_date" not in rec_cols:
        conn.execute("ALTER TABLE usage_records ADD COLUMN local_date TEXT")
    # 存量回填 (仅未回填行; 幂等)
    conn.execute(
        "UPDATE usage_records SET local_date = date(created_at, 'localtime')"
        " WHERE local_date IS NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_account_localdate"
        " ON usage_records(account_id, local_date)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# settings payload 底层读写 (key_names 与 active_account_id 等共用一个 JSON)
# ---------------------------------------------------------------------------


def _raw_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["payload"])
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _write_payload(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE settings SET payload = ?, updated_at = ? WHERE id = 1",
        (json.dumps(data, ensure_ascii=False), _now_iso()),
    )


# ---------------------------------------------------------------------------
# 活跃账号
# ---------------------------------------------------------------------------


def _persist_active(conn: sqlite3.Connection, account_id: int) -> None:
    data = _raw_payload(conn)
    data["active_account_id"] = int(account_id)
    _write_payload(conn, data)
    conn.commit()


def get_active_account_id() -> int:
    """当前活跃账号 id; 无任何账号时返回 0.

    偏好已登录账号: 存储的活跃账号若未登录, 自动让位给最小的已登录账号,
    保证应用启动时默认落在可用的账号上; 全部未登录时维持原选择,
    使欢迎页登录能落到既有行上.
    """
    conn = get_db()
    aid = _raw_payload(conn).get("active_account_id")
    logged_row = conn.execute(
        "SELECT MIN(id) AS i FROM accounts WHERE TRIM(token) != ''"
    ).fetchone()
    logged_min = int(logged_row["i"]) if logged_row and logged_row["i"] is not None else 0
    if isinstance(aid, int) and aid > 0:
        row = conn.execute("SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
        if row is not None:
            if row["token"].strip():
                return aid
            if logged_min:  # 活跃行未登录但有其他已登录账号 -> 让位
                _persist_active(conn, logged_min)
                return logged_min
            return aid     # 全部未登录: 维持原选择
    if logged_min:
        _persist_active(conn, logged_min)
        return logged_min
    row = conn.execute("SELECT MIN(id) AS i FROM accounts").fetchone()
    fallback = int(row["i"]) if row and row["i"] is not None else 0
    if fallback:
        _persist_active(conn, fallback)
    return fallback


def _resolve_account_id(account_id: Optional[int]) -> int:
    """None/0 -> 活跃账号 (可能为 0 表示无账号, 查询将得到空集)."""
    if account_id:
        return int(account_id)
    return get_active_account_id()


def set_active_account(account_id: int) -> bool:
    conn = get_db()
    row = conn.execute("SELECT id FROM accounts WHERE id = ?", (int(account_id),)).fetchone()
    if row is None:
        return False
    _persist_active(conn, int(account_id))
    return True


# ---------------------------------------------------------------------------
# 账号 CRUD / token
# ---------------------------------------------------------------------------


def _account_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "workspace_id": row["workspace_id"],
        "resolved_workspace_id": row["resolved_workspace_id"],
        "has_token": bool(row["token"].strip()),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_account() -> dict[str, Any]:
    """活跃账号摘要; 无账号返回 {}."""
    aid = get_active_account_id()
    if not aid:
        return {}
    row = get_db().execute("SELECT * FROM accounts WHERE id = ?", (aid,)).fetchone()
    return _account_dict(row) if row else {}


def list_accounts() -> list[dict[str, Any]]:
    rows = get_db().execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
    return [_account_dict(r) for r in rows]


def count_accounts() -> int:
    return int(get_db().execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"])


def count_logged_in_accounts() -> int:
    row = get_db().execute(
        "SELECT COUNT(*) AS c FROM accounts WHERE TRIM(token) != ''"
    ).fetchone()
    return int(row["c"])


def _ensure_state_row(conn: sqlite3.Connection, account_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO usage_sync_state (account_id, deepest_page_fetched) VALUES (?, -1)",
        (account_id,),
    )


def save_token(token: str, workspace_id: str = "Default") -> None:
    """重新登录语义: 更新活跃账号的凭证并重置其增量游标."""
    conn = get_db()
    aid = get_active_account_id()
    if not aid:
        return
    conn.execute(
        """UPDATE accounts SET token = ?, workspace_id = ?, resolved_workspace_id = NULL,
           updated_at = ? WHERE id = ?""",
        (token.strip(), workspace_id.strip() or "Default", _now_iso(), aid),
    )
    _ensure_state_row(conn, aid)
    conn.execute(
        "UPDATE usage_sync_state SET deepest_page_fetched = -1 WHERE account_id = ?", (aid,)
    )
    conn.commit()


def save_resolved_workspace(workspace_id: str, account_id: Optional[int] = None) -> None:
    conn = get_db()
    aid = _resolve_account_id(account_id)
    if not aid:
        return
    conn.execute(
        "UPDATE accounts SET resolved_workspace_id = ?, updated_at = ? WHERE id = ?",
        (workspace_id, _now_iso(), aid),
    )
    conn.commit()


def get_token() -> str:
    aid = get_active_account_id()
    if not aid:
        return ""
    row = get_db().execute("SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    return row["token"] if row else ""


def get_workspace_hint() -> str:
    aid = get_active_account_id()
    if not aid:
        return "Default"
    row = get_db().execute(
        "SELECT workspace_id, resolved_workspace_id FROM accounts WHERE id = ?", (aid,)
    ).fetchone()
    if row is None:
        return "Default"
    return row["resolved_workspace_id"] or row["workspace_id"] or "Default"


def get_account_credentials(account_id: int) -> tuple[str, str]:
    """读取任意账号的凭证 (token, 工作区提示); 账号不存在返回 ("", "Default")."""
    row = get_db().execute(
        "SELECT token, workspace_id, resolved_workspace_id FROM accounts WHERE id = ?",
        (int(account_id),),
    ).fetchone()
    if row is None:
        return "", "Default"
    hint = row["resolved_workspace_id"] or row["workspace_id"] or "Default"
    return (row["token"] or "").strip(), hint


def add_account(token: str, workspace_hint: str = "", switch: bool = True) -> int:
    """添加新账号; 若已有完全相同的 token 则视为同一用户, 更新工作区提示后返回其 id."""
    conn = get_db()
    token = token.strip()
    hint = (workspace_hint or "").strip()
    existing = conn.execute(
        "SELECT id FROM accounts WHERE TRIM(token) = ? ORDER BY id LIMIT 1", (token,)
    ).fetchone() if token else None
    if existing is not None:
        aid = int(existing["id"])
        if hint:
            conn.execute(
                "UPDATE accounts SET workspace_id = ?, updated_at = ? WHERE id = ?",
                (hint, _now_iso(), aid),
            )
        if switch:
            _persist_active(conn, aid)
        else:
            conn.commit()
        return aid
    nxt = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM accounts").fetchone()["n"]
    name = hint[:50] if hint else f"User {nxt}"
    now = _now_iso()
    cur = conn.execute(
        """INSERT INTO accounts (name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
           VALUES (?, ?, NULL, ?, ?, ?)""",
        (name, hint or "Default", token, now, now),
    )
    aid = int(cur.lastrowid or nxt)
    _ensure_state_row(conn, aid)
    if switch:
        _persist_active(conn, aid)
    else:
        conn.commit()
    return aid


def rename_account(account_id: int, name: str) -> bool:
    name = (name or "").strip()[:50]
    if not name:
        return False
    conn = get_db()
    cur = conn.execute(
        "UPDATE accounts SET name = ?, updated_at = ? WHERE id = ?",
        (name, _now_iso(), int(account_id)),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_account(account_id: int) -> int:
    """删除账号及其本地全部数据 (级联), 返回剩余账号数."""
    conn = get_db()
    aid = int(account_id)
    conn.execute("DELETE FROM usage_records WHERE account_id = ?", (aid,))
    conn.execute("DELETE FROM usage_sync_state WHERE account_id = ?", (aid,))
    conn.execute("DELETE FROM accounts WHERE id = ?", (aid,))
    remaining = int(conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"])
    active = _raw_payload(conn).get("active_account_id")
    if active == aid:
        nxt = conn.execute("SELECT MIN(id) AS i FROM accounts").fetchone()["i"]
        if nxt is not None:
            _persist_active(conn, int(nxt))
        else:
            data = _raw_payload(conn)
            data.pop("active_account_id", None)
            _write_payload(conn, data)
            conn.commit()
    conn.commit()
    return remaining


def clear_account() -> None:
    """退出登录当前活跃账号: 清除其凭证与本地缓存数据 (保留账号行便于重新登录)."""
    conn = get_db()
    aid = get_active_account_id()
    if not aid:
        return
    conn.execute("DELETE FROM usage_records WHERE account_id = ?", (aid,))
    conn.execute(
        "UPDATE accounts SET token = '', resolved_workspace_id = NULL, updated_at = ? WHERE id = ?",
        (_now_iso(), aid),
    )
    _ensure_state_row(conn, aid)
    conn.execute(
        "UPDATE usage_sync_state SET last_sync_status = NULL, last_sync_error = NULL,"
        " last_inserted_count = 0, deepest_page_fetched = -1, total_records = 0,"
        " oldest_record_at = NULL, newest_record_at = NULL WHERE account_id = ?",
        (aid,),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 用量记录写入 / 同步状态
# ---------------------------------------------------------------------------


def insert_usage_records(records: list[dict[str, Any]], account_id: Optional[int] = None) -> int:
    """批量写入 (归属指定/活跃账号), 按 usg_id 去重; 返回新增条数."""
    if not records:
        return 0
    aid = _resolve_account_id(account_id)
    conn = get_db()
    synced_at = _now_iso()
    stmt = (
        "INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens,"
        " output_tokens, reasoning_tokens, cache_read_tokens, cache_write_5m_tokens,"
        " cache_write_1h_tokens, cost_raw, cost_usd, key_id, session_id, plan, synced_at,"
        " account_id, local_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date(?, 'localtime'))"
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
                    synced_at, aid,
                    # local_date 由 SQLite 按本地时区从 created_at 派生 (末位绑定)
                    rec["created_at"],
                ),
            )
            if not existed:
                inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return inserted


def get_sync_state(account_id: Optional[int] = None) -> dict[str, Any]:
    aid = _resolve_account_id(account_id)
    if not aid:
        return {}
    row = get_db().execute(
        "SELECT * FROM usage_sync_state WHERE account_id = ?", (aid,)
    ).fetchone()
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


def update_sync_state(
    status: str,
    error: Optional[str] = None,
    inserted: int = 0,
    account_id: Optional[int] = None,
) -> None:
    aid = _resolve_account_id(account_id)
    if not aid:
        return
    conn = get_db()
    _ensure_state_row(conn, aid)
    conn.execute(
        """UPDATE usage_sync_state
           SET last_sync_at = ?, last_sync_status = ?, last_sync_error = ?,
               last_inserted_count = last_inserted_count + ?
           WHERE account_id = ?""",
        (_now_iso(), status, error, inserted, aid),
    )
    _refresh_sync_totals(conn, aid)
    conn.commit()


def _refresh_sync_totals(conn: sqlite3.Connection, account_id: int) -> None:
    row = conn.execute(
        "SELECT COUNT(*) AS total, MIN(created_at) AS oldest, MAX(created_at) AS newest"
        " FROM usage_records WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    conn.execute(
        "UPDATE usage_sync_state SET total_records = ?, oldest_record_at = ?, newest_record_at = ?"
        " WHERE account_id = ?",
        (row["total"], row["oldest"], row["newest"], account_id),
    )


# ---------------------------------------------------------------------------
# 明细分页查询 + 设置
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS = {
    "sync_interval_sec": 300,  # 自动增量同步间隔 (1/5/15/30 分钟)
    "window_days": 60,  # 同步范围: 30/60/90/180, None=所有
    "auto_sync": True,  # 自动增量同步开关
    "show_accounts_panel": False,  # 账户总览面板开关 (侧边栏入口显隐)
}


def prune_old_records(window_days: int | None, account_id: Optional[int] = None) -> int:
    """按同步范围裁剪过期记录, 返回删除条数. window_days=None 时不裁剪."""
    if window_days is None:
        return 0
    aid = _resolve_account_id(account_id)
    if not aid:
        return 0
    window_days = max(1, min(int(window_days), 3650))
    # local_date 走 idx_usage_account_localdate; 原先 datetime(created_at) <
    # datetime('now', ?) 每次同步都要按账号全表扫一遍. 日历日口径最多多保留
    # 窗口边界当天一天的记录, 只多不少, 不会丢数据.
    cur = get_db().execute(
        "DELETE FROM usage_records WHERE account_id = ?"
        " AND local_date < date('now', 'localtime', ?)",
        (aid, f"-{window_days} days"),
    )
    get_db().commit()
    return cur.rowcount


def _account_filter(where: str, params: list[Any], aid: int) -> tuple[str, list[Any]]:
    """把 account_id 过滤拼接到已生成的 WHERE 片段上."""
    if where:
        return where + " AND account_id = ?", params + [aid]
    return "WHERE account_id = ?", params + [aid]


def usage_records_page(
    page: int = 1,
    page_size: int = 20,
    model: Optional[str] = None,
    days: Optional[int] = None,
    account_id: Optional[int] = None,
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
        # 日历日口径 + local_date 索引 (原先 datetime(created_at) 全表扫)
        where.append("local_date >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    where_sql, params = _account_filter(where_sql, params, _resolve_account_id(account_id))
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
            "key_id": r["key_id"],
            "plan": r["plan"],
        }
        records.append(rec)
    return records, total


def list_models(account_id: Optional[int] = None) -> list[str]:
    where, params = _account_filter("", [], _resolve_account_id(account_id))
    rows = get_db().execute(
        f"SELECT DISTINCT model FROM usage_records {where} ORDER BY model", params
    ).fetchall()
    return [r["model"] for r in rows]


def session_stats_page(
    page: int = 1,
    page_size: int = 10,
    days: Optional[int] = None,
    account_id: Optional[int] = None,
) -> tuple[list[dict[str, Any]], int]:
    """按会话聚合用量, 按成本降序, 返回 (records, total).

    无 session_id 的记录 (其他 agent 工具 / 直接调 key 等) 不再合并成一行,
    改为按 key_id 拆分, 前端以 "未归属 · key尾号" 展示, 来源一目了然.
    仍有 key_id 也为空的记录兜底聚合为 session_id="" 的"未归属"行,
    保证会话用量与明细/统计合计一致.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 50))
    where: list[str] = []
    params: list[Any] = []
    if days:
        # 日历日口径 + local_date 索引 (原先 datetime(created_at) 全表扫)
        where.append("local_date >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    where_sql, params = _account_filter(where_sql, params, _resolve_account_id(account_id))
    session_key = (
        "CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id "
        "WHEN key_id IS NOT NULL AND key_id != '' THEN key_id ELSE '' END"
    )
    conn = get_db()
    total = int(
        conn.execute(
            f"SELECT COUNT(DISTINCT {session_key}) AS c FROM usage_records {where_sql}", params
        ).fetchone()["c"]
    )
    rows = conn.execute(
        f"""SELECT {session_key} AS session_id,
               MAX(key_id) AS key_id,
               COUNT(*) AS request_count,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cost_usd) AS total_cost_usd,
               MAX(created_at) AS last_at
        FROM usage_records {where_sql}
        GROUP BY {session_key}
        ORDER BY last_at DESC
        LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    records = [
        {
            "session_id": r["session_id"],
            "key_id": r["key_id"],
            "request_count": int(r["request_count"]),
            "total_input_tokens": int(r["total_input_tokens"] or 0),
            "uncached_input_tokens": int(r["uncached_input_tokens"] or 0),
            "total_output_tokens": int(r["total_output_tokens"] or 0),
            "total_reasoning_tokens": int(r["total_reasoning_tokens"] or 0),
            "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
            "last_at": r["last_at"],
        }
        for r in rows
    ]
    return records, total


def get_settings() -> dict[str, Any]:
    merged = dict(_DEFAULT_SETTINGS)
    merged.update({k: v for k, v in _raw_payload(get_db()).items() if k in _DEFAULT_SETTINGS})
    return merged


def get_key_names() -> dict[str, str]:
    """读取缓存的 key_id -> 显示名称 映射 (来自 opencode keys 页面)."""
    names = _raw_payload(get_db()).get("key_names") or {}
    return names if isinstance(names, dict) else {}


def save_key_names(names: dict[str, str]) -> None:
    """持久化 key_id -> 显示名称 映射到 settings."""
    conn = get_db()
    data = _raw_payload(conn)
    data["key_names"] = {k: v for k, v in names.items() if k and v}
    _write_payload(conn, data)
    conn.commit()


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    conn = get_db()
    raw = _raw_payload(conn)
    current = dict(_DEFAULT_SETTINGS)
    current.update({k: v for k, v in raw.items() if k in _DEFAULT_SETTINGS})
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
            elif key in ("auto_sync", "show_accounts_panel"):
                current[key] = bool(payload[key])
            else:
                current[key] = payload[key]
    # 写回时保留非白名单键 (key_names / active_account_id 等), 避免被整体覆盖丢失
    out = dict(raw)
    out.update(current)
    _write_payload(conn, out)
    conn.commit()
    return current

_PERIOD_CLAUSES = {
    # local_date 为写入时落库的本地日 (见 _init_schema 迁移 5), 可直接走
    # idx_usage_account_localdate; 原先的 substr(datetime(...,'localtime')) 无法用索引.
    #
    # "5h" 滚动窗口: datetime() 包裹索引列无法走索引, 先用 local_date 把行集
    # 收敛到昨/今两天 (索引范围扫, 行数少), 再叠加 datetime() 保留精确的
    # 滚动 5 小时口径 —— 外层索引过滤 + 内层精确过滤, 两全.
    "5h": (
        "(local_date >= date('now', 'localtime', '-1 day')"
        " AND datetime(created_at) >= datetime('now', '-5 hours'))"
    ),
    "today": "local_date = date('now', 'localtime')",
}


def _period_where(period: str) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if period in _PERIOD_CLAUSES:
        clauses.append(_PERIOD_CLAUSES[period])
    elif period != "all":
        # "7d"/"30d" 等: 日历日口径 (与 daily_stats/today_trend 一致), 走索引;
        # 原先 datetime(created_at) >= datetime('now','-N days') 无法用索引,
        # dashboard 一次刷新多条聚合全是按账号全范围扫描.
        days = 30
        match = _NUM_DAYS_RE.match(period or "")
        if match:
            days = max(1, int(match.group(1)))
        clauses.append("local_date >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


_NUM_DAYS_RE = __import__("re").compile(r"^(\d+)d$")


def model_stats(period: str = "30d", account_id: Optional[int] = None) -> list[dict[str, Any]]:
    """按模型聚合: 请求数 / 会话数 / 输入(含缓存) / 普通输入 / 推理 / 缓存命中 / 缓存写入 / 输出 / 成本 / 命中率."""
    where, params = _period_where(period)
    where, params = _account_filter(where, params, _resolve_account_id(account_id))
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


def daily_stats(days: int = 30, account_id: Optional[int] = None) -> list[dict[str, Any]]:
    """每日聚合: 输入(含缓存) / 普通输入 / 推理 / 缓存命中 / 缓存写入 / 输出 / 成本 / 请求数."""
    days = max(1, min(days, 365))
    aid = _resolve_account_id(account_id)
    rows = get_db().execute(
        """
        SELECT local_date AS date,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cache_read_tokens) AS cache_hit_tokens,
               SUM(cache_write_5m_tokens + cache_write_1h_tokens) AS cache_write_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(cost_usd) AS total_cost_usd,
               COUNT(*) AS request_count
        FROM usage_records
        WHERE account_id = ?
          AND local_date >= date('now', 'localtime', ?)
        GROUP BY local_date
        ORDER BY date ASC
        """,
        (aid, f"-{days} days"),
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


def today_trend(account_id: Optional[int] = None) -> list[dict[str, Any]]:
    """今日 24 小时趋势: 每小时 输入/输出/推理 (本地时区, 无数据补 0)."""
    aid = _resolve_account_id(account_id)
    rows = get_db().execute(
        """
        SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS h,
               SUM(input_tokens) AS input,
               SUM(output_tokens) AS output,
               SUM(reasoning_tokens) AS reasoning
        FROM usage_records
        WHERE account_id = ?
          AND local_date = date('now', 'localtime')
        GROUP BY h
        """,
        (aid,),
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


def totals(period: str = "30d", account_id: Optional[int] = None) -> dict[str, Any]:
    """总览指标, 口径与模型占比一致."""
    where, params = _period_where(period)
    where, params = _account_filter(where, params, _resolve_account_id(account_id))
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
