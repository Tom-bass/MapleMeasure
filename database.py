"""
Database layer — schema initialisation and all query functions.

Every SQL statement in the application lives here.  Route handlers call these
functions and never construct queries themselves.
"""

import sqlite3
from contextlib import contextmanager
from typing import Optional


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT NOT NULL,
                session_date        TEXT,
                auto_battle_minutes INTEGER,
                kills               INTEGER,
                solo_frags          INTEGER,
                image_filename      TEXT
            );
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_data(db_path: str) -> dict:
    """Aggregate stats and per-date chart series for the dashboard."""
    with get_conn(db_path) as conn:
        total_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]

        total_minutes = conn.execute(
            "SELECT SUM(auto_battle_minutes) FROM sessions"
        ).fetchone()[0] or 0

        total_kills = conn.execute(
            "SELECT SUM(kills) FROM sessions"
        ).fetchone()[0] or 0

        total_frags = conn.execute(
            "SELECT SUM(solo_frags) FROM sessions"
        ).fetchone()[0] or 0

        recent = [dict(r) for r in conn.execute("""
            SELECT id, session_date, auto_battle_minutes, kills, solo_frags, created_at
            FROM sessions
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()]

        chart_rows = [dict(r) for r in conn.execute("""
            SELECT
                session_date,
                SUM(auto_battle_minutes) AS total_minutes,
                SUM(kills)               AS total_kills,
                SUM(solo_frags)          AS total_frags
            FROM sessions
            WHERE session_date IS NOT NULL
            GROUP BY session_date
            ORDER BY session_date ASC
        """).fetchall()]

    return {
        "total_sessions": total_sessions,
        "total_hours":    round(total_minutes / 60, 1),
        "total_kills":    total_kills,
        "total_frags":    total_frags,
        "recent":         recent,
        "chart_rows":     chart_rows,
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def insert_session(db_path: str, session_data: dict) -> int:
    """Write a new session.  Returns the new session id."""
    with get_conn(db_path) as conn:
        cur = conn.execute("""
            INSERT INTO sessions (
                created_at, session_date, auto_battle_minutes, kills,
                solo_frags, image_filename
            ) VALUES (
                :created_at, :session_date, :auto_battle_minutes, :kills,
                :solo_frags, :image_filename
            )
        """, session_data)
        session_id = cur.lastrowid
        conn.commit()
    return session_id


def list_sessions(
    db_path: str,
    sort: str,
    order: str,
    page: int,
    per_page: int,
) -> tuple:
    """Return (rows, total) for the paginated session history table."""
    offset = (page - 1) * per_page
    with get_conn(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        rows  = conn.execute(
            f"""
            SELECT id, session_date, auto_battle_minutes, kills, solo_frags, created_at
            FROM sessions
            ORDER BY {sort} {order}
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        ).fetchall()
    return [dict(r) for r in rows], total


def get_session(db_path: str, session_id: int) -> Optional[dict]:
    """Return the session dict, or None if not found."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id, session_date, auto_battle_minutes, kills, solo_frags, "
            "image_filename, created_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_session(db_path: str, session_id: int) -> None:
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()


def update_session(db_path: str, session_id: int, session_data: dict) -> None:
    with get_conn(db_path) as conn:
        conn.execute("""
            UPDATE sessions SET
                session_date        = :session_date,
                auto_battle_minutes = :auto_battle_minutes,
                kills               = :kills,
                solo_frags          = :solo_frags,
                image_filename      = :image_filename
            WHERE id = :id
        """, {**session_data, "id": session_id})
        conn.commit()


# ---------------------------------------------------------------------------
# Session analytics (history page summary + chart data)
# ---------------------------------------------------------------------------

def get_sessions_analytics(db_path: str) -> dict:
    """Totals, averages, and per-session chart series across all sessions."""
    with get_conn(db_path) as conn:
        agg = conn.execute("""
            SELECT
                COUNT(*)                            AS count,
                SUM(auto_battle_minutes)             AS total_minutes,
                SUM(kills)                           AS total_kills,
                SUM(solo_frags)                      AS total_frags,
                ROUND(AVG(auto_battle_minutes), 1)   AS avg_minutes,
                ROUND(AVG(kills), 0)                 AS avg_kills,
                ROUND(AVG(solo_frags), 1)            AS avg_frags,
                ROUND(AVG(
                    CASE WHEN kills > 0
                         THEN CAST(solo_frags AS REAL) / kills * 1000
                         ELSE NULL END
                ), 2)                                AS avg_frags_per_1k,
                ROUND(AVG(
                    CASE WHEN auto_battle_minutes > 0 AND solo_frags IS NOT NULL
                         THEN CAST(solo_frags AS REAL) / auto_battle_minutes * 60
                         ELSE NULL END
                ), 1)                                AS avg_frags_per_hour
            FROM sessions
        """).fetchone()

        chart_rows = [dict(r) for r in conn.execute("""
            SELECT id, session_date, auto_battle_minutes, kills, solo_frags
            FROM sessions
            ORDER BY session_date ASC, created_at ASC
        """).fetchall()]

    return {
        "count":         agg["count"] or 0,
        "total_minutes": agg["total_minutes"] or 0,
        "total_kills":   agg["total_kills"] or 0,
        "total_frags":   agg["total_frags"] or 0,
        "avg_minutes":   agg["avg_minutes"] or 0,
        "avg_kills":     int(agg["avg_kills"] or 0),
        "avg_frags":          agg["avg_frags"] or 0,
        "avg_frags_per_1k":   agg["avg_frags_per_1k"] or 0,
        "avg_frags_per_hour": agg["avg_frags_per_hour"] or 0,
        "total_frags_per_1k": round(
            (agg["total_frags"] or 0) / agg["total_kills"] * 1000, 2
        ) if agg["total_kills"] else 0,
        "total_frags_per_hour": round(
            (agg["total_frags"] or 0) / agg["total_minutes"] * 60, 1
        ) if agg["total_minutes"] else 0,
        "chart_rows":    chart_rows,
    }


# ---------------------------------------------------------------------------
# CSV export / import
# ---------------------------------------------------------------------------

def export_sessions_rows(db_path: str) -> list:
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT session_date, auto_battle_minutes, kills, solo_frags "
            "FROM sessions ORDER BY session_date ASC, created_at ASC"
        ).fetchall()


def import_sessions(db_path: str, rows: list) -> int:
    """Bulk-insert pre-validated session dicts. Returns count inserted."""
    with get_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sessions (created_at, session_date, auto_battle_minutes, kills, solo_frags, image_filename)
            VALUES (:created_at, :session_date, :auto_battle_minutes, :kills, :solo_frags, NULL)
            """,
            rows,
        )
        conn.commit()
        return len(rows)
