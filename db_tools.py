import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy import text, bindparam
from contextlib import contextmanager
from typing import Dict, Any, Optional, List

_engine: Optional[Engine] = None
_allow_writes: bool = False


class SqlSafetyError(Exception):
    pass


def make_db_url(host: str, port: int, user: str, password: str, database: str) -> str:
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def set_engine(db_url: str):
    global _engine
    _engine = sa.create_engine(db_url, pool_pre_ping=True, pool_recycle=3600, future=True)


def set_write_policy(allow_writes: bool):
    global _allow_writes
    _allow_writes = bool(allow_writes)


@contextmanager
def _connect():
    if _engine is None:
        raise RuntimeError("Database engine is not configured. Call set_engine first.")
    conn = _engine.connect()
    try:
        yield conn
    finally:
        conn.close()


READ_ONLY_PREFIXES = ("SELECT", "WITH", "EXPLAIN")
BANNED_TOKENS = [
    ";--",  # statement stacking attempt
    " DROP ",
    " TRUNCATE ",
    " SHUTDOWN ",
    "/*",  # block comments
]


def _enforce_safety(sql: str, write: bool):
    s = (sql or "").strip().upper()
    if not write and not s.startswith(READ_ONLY_PREFIXES):
        raise SqlSafetyError("Write operation attempted without approval.")
    for b in BANNED_TOKENS:
        if b in s:
            raise SqlSafetyError(f"Banned token detected: {b.strip()}")
    if write and not _allow_writes:
        raise SqlSafetyError("Write operations are disabled by policy.")


def get_schema(include_counts: bool = False, tables: Optional[List[str]] = None) -> Dict[str, Any]:
    tables = tables or []
    out: Dict[str, Any] = {}
    with _connect() as c:
        if tables:
            # Build explicit IN list to avoid driver quirks
            placeholders = ",".join([":t" + str(i) for i in range(len(tables))])
            params = {"t" + str(i): t for i, t in enumerate(tables)}
            sql = text(
                f"""
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({placeholders})
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
            )
            rows = c.execute(sql, params).mappings().all()
        else:
            sql = text(
                """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
            )
            rows = c.execute(sql).mappings().all()
        for r in rows:
            out.setdefault(r["TABLE_NAME"], []).append({
                "column": r["COLUMN_NAME"],
                "type": r["DATA_TYPE"],
            })
        if include_counts:
            for t in list(out.keys()):
                cnt = c.execute(text(f"SELECT COUNT(*) AS n FROM `{t}`")).scalar()
                out[t] = {"columns": out[t], "row_count": int(cnt or 0)}
    return out


def run_sql(sql: str, params: Optional[Dict[str, Any]] = None, write: bool = False, row_limit: int = 200) -> Dict[str, Any]:
    params = params or {}
    _enforce_safety(sql, write)
    with _connect() as c:
        if not write:
            up = sql.strip().upper()
            if up.startswith("SELECT") and " LIMIT " not in up:
                sql = f"{sql}\nLIMIT {int(row_limit)}"
            res = c.execute(text(sql), params)
            rows = res.mappings().fetchmany(row_limit)
            return {"rows": [dict(r) for r in rows]}
        else:
            trans = c.begin()
            try:
                res = c.execute(text(sql), params)
                trans.commit()
                return {"rowcount": getattr(res, "rowcount", None)}
            except Exception as e:
                trans.rollback()
                raise


def sample_rows(table: str, limit: int = 50) -> Dict[str, Any]:
    sql = f"SELECT * FROM `{table}` LIMIT {int(limit)}"
    return run_sql(sql, write=False, row_limit=limit)
