"""Persistence for the field station.

Local development uses SQLite. Set COCOA_DATABASE_URL (or the same key in
Streamlit Secrets) to use the shared Supabase PostgreSQL database. PostgreSQL
schema is installed separately from backend/supabase_schema.sql.
"""
import json
import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("COCOA_DB_PATH", Path(__file__).parent / "cocoa.db"))


def _database_url():
    value = os.getenv("COCOA_DATABASE_URL", "").strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get("COCOA_DATABASE_URL", "")).strip()
    except Exception:
        return ""


def _is_postgres():
    return bool(_database_url())


def connect():
    url = _database_url()
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg to connect to the Supabase database.") from exc
        return psycopg.connect(url, sslmode="require", row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


try:
    import psycopg
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
except ImportError:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def _execute(db, sql, params=()):
    if isinstance(db, sqlite3.Connection):
        return db.execute(sql, params)
    # SQL text is application-owned; all external values remain bound params.
    return db.execute(sql.replace("?", "%s"), params)


def _executemany(db, sql, rows):
    if isinstance(db, sqlite3.Connection):
        return db.executemany(sql, rows)
    sql = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
    return db.executemany(sql.replace("?", "%s"), rows)


def _table_exists(db, table):
    return _execute(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def init_db():
    """Initialize/migrate local SQLite only; cloud schema is explicit SQL."""
    if _is_postgres():
        return
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS field_plots (
          plot_id TEXT PRIMARY KEY, description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS field_weather (
          plot_id TEXT NOT NULL, observation_date TEXT NOT NULL,
          rainfall_mm REAL NOT NULL, humidity_pct REAL NOT NULL, temp_c REAL NOT NULL,
          days_since_last_spray INTEGER NOT NULL, inspection_note TEXT,
          entered_by INTEGER, entered_by_email TEXT,
          PRIMARY KEY (plot_id, observation_date));
        CREATE TABLE IF NOT EXISTS field_decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, entered_by_email TEXT,
          plot_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          risk_bucket TEXT NOT NULL, recommendation TEXT NOT NULL, rationale TEXT NOT NULL,
          evidence_json TEXT NOT NULL DEFAULT '[]', confidence REAL NOT NULL, gated INTEGER NOT NULL,
          human_decision TEXT, human_reason TEXT, cited_case_ids TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS auth_accounts (
          google_sub TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'inputer', totp_secret_enc TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inputer_invites (
          email TEXT PRIMARY KEY, name TEXT NOT NULL, invited_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS blocked_auth_identities (
          google_sub TEXT PRIMARY KEY, email TEXT NOT NULL,
          blocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """)

        # Bring forward data from the prototype's original SQLite table names.
        if _table_exists(db, "weather_daily"):
            _execute(db, """INSERT INTO field_weather
                (plot_id,observation_date,rainfall_mm,humidity_pct,temp_c,
                 days_since_last_spray,inspection_note,entered_by_email)
                SELECT plot_id,date,rainfall_mm,humidity_pct,temp_c,
                       days_since_last_spray,inspection_note,entered_by
                FROM weather_daily WHERE 1
                ON CONFLICT(plot_id,observation_date) DO NOTHING""")
        if _table_exists(db, "decisions"):
            _execute(db, """INSERT OR IGNORE INTO field_decisions
                (id,plot_id,created_at,risk_bucket,recommendation,rationale,evidence_json,
                 confidence,gated,human_decision,human_reason,cited_case_ids)
                SELECT id,plot_id,ts,risk_bucket,recommendation,rationale,evidence_json,
                       confidence,gated,human_decision,human_reason,cited_case_ids
                FROM decisions""")
        if _table_exists(db, "auth_accounts"):
            columns = {row["name"] for row in _execute(db, "PRAGMA table_info(auth_accounts)")}
            if "totp_secret_enc" not in columns:
                _execute(db, "ALTER TABLE auth_accounts ADD COLUMN totp_secret_enc TEXT")
            if "role" not in columns:
                _execute(db, "ALTER TABLE auth_accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'inputer'")
            _execute(db, "UPDATE auth_accounts SET role='inputer' WHERE role='user'")
        # Older installations may have a narrower version of the shared tables.
        weather_columns = {row["name"] for row in _execute(db, "PRAGMA table_info(field_weather)")}
        if "entered_by_email" not in weather_columns:
            _execute(db, "ALTER TABLE field_weather ADD COLUMN entered_by_email TEXT")
        decision_columns = {row["name"] for row in _execute(db, "PRAGMA table_info(field_decisions)")}
        for column, definition in (("user_id", "INTEGER"), ("entered_by_email", "TEXT"),
                                  ("cited_case_ids", "TEXT NOT NULL DEFAULT '[]'")):
            if column not in decision_columns:
                _execute(db, f"ALTER TABLE field_decisions ADD COLUMN {column} {definition}")


def get_or_create_auth_account(google_sub, email, name, bootstrap_role="inputer"):
    allowed_roles = {"inputer", "admin", "administrator", "manager"}
    if bootstrap_role not in allowed_roles:
        bootstrap_role = "inputer"
    email = email.strip().lower()
    with connect() as db:
        blocked = _execute(db, "SELECT 1 FROM blocked_auth_identities WHERE google_sub=? OR email=?", (google_sub, email)).fetchone()
        if blocked:
            return None
        row = _execute(db, "SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        if row is None:
            invitation = _execute(db, "SELECT name FROM inputer_invites WHERE email=?", (email,)).fetchone()
            account_name = name or (invitation["name"] if invitation else email)
            _execute(db, "INSERT INTO auth_accounts (google_sub,email,name,role) VALUES (?,?,?,?) ON CONFLICT(google_sub) DO NOTHING",
                     (google_sub, email, account_name, bootstrap_role))
            _execute(db, "DELETE FROM inputer_invites WHERE email=?", (email,))
            row = _execute(db, "SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        else:
            if bootstrap_role != "inputer":
                _execute(db, "UPDATE auth_accounts SET email=?,name=?,role=? WHERE google_sub=?",
                         (email, name, bootstrap_role, google_sub))
            else:
                _execute(db, "UPDATE auth_accounts SET email=?,name=? WHERE google_sub=?", (email, name, google_sub))
            row = _execute(db, "SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        return dict(row)


def set_totp_secret(google_sub, encrypted_secret):
    with connect() as db:
        _execute(db, "UPDATE auth_accounts SET totp_secret_enc=? WHERE google_sub=?", (encrypted_secret, google_sub))


def auth_account(google_sub):
    with connect() as db:
        row = _execute(db, "SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
    return dict(row) if row else None


def auth_accounts():
    with connect() as db:
        rows = _execute(db, """SELECT google_sub,email,name,role,created_at,
            CASE WHEN totp_secret_enc IS NULL THEN 'Not enrolled' ELSE 'Enrolled' END AS authenticator
            FROM auth_accounts ORDER BY created_at DESC""").fetchall()
    return [dict(row) for row in rows]


def inputer_invites():
    with connect() as db:
        rows = _execute(db, "SELECT email,name,invited_by,created_at FROM inputer_invites ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def create_inputer_invite(email, name, invited_by):
    email = email.strip().lower()
    with connect() as db:
        exists = _execute(db, "SELECT 1 FROM auth_accounts WHERE lower(email)=?", (email,)).fetchone()
        if exists:
            return False, "An account with that email already exists."
        try:
            _execute(db, "INSERT INTO inputer_invites(email,name,invited_by) VALUES(?,?,?)", (email, name.strip(), invited_by))
        except INTEGRITY_ERRORS:
            return False, "An inputer invitation for that email already exists."
        _execute(db, "DELETE FROM blocked_auth_identities WHERE email=?", (email,))
    return True, "Inputer invitation added. The person must sign in with this Google email to activate it."


def delete_inputer_account(google_sub):
    with connect() as db:
        account = _execute(db, "SELECT name,email,role FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        if not account or account["role"] != "inputer":
            return False
        _execute(db, """INSERT INTO blocked_auth_identities(google_sub,email) VALUES(?,?)
            ON CONFLICT(google_sub) DO UPDATE SET email=excluded.email, blocked_at=CURRENT_TIMESTAMP""",
                 (google_sub, account["email"]))
        _execute(db, "DELETE FROM auth_accounts WHERE google_sub=? AND role='inputer'", (google_sub,))
    return True


def delete_inputer_invite(email):
    with connect() as db:
        cursor = _execute(db, "DELETE FROM inputer_invites WHERE email=?", (email.strip().lower(),))
    return cursor.rowcount > 0


def seed_weather(rows):
    with connect() as db:
        _executemany(db, """INSERT INTO field_weather
          (plot_id,observation_date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note)
          VALUES (:plot_id,:date,:rainfall_mm,:humidity_pct,:temp_c,:days_since_last_spray,:inspection_note)
          ON CONFLICT(plot_id,observation_date) DO NOTHING""", rows)


def weather_for_plot(plot_id, limit=None):
    query = "SELECT plot_id,observation_date AS date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note,entered_by_email AS entered_by FROM field_weather WHERE plot_id=? ORDER BY observation_date DESC"
    params = [plot_id]
    if limit:
        query += " LIMIT ?"
        params.append(int(limit))
    with connect() as db:
        rows = [dict(row) for row in _execute(db, query, params)]
    for row in rows:
        if hasattr(row["date"], "isoformat"):
            row["date"] = row["date"].isoformat()
    return list(reversed(rows))


def add_weather_observation(plot_id, observation, entered_by):
    with connect() as db:
        _execute(db, """INSERT INTO field_weather
          (plot_id,observation_date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note,entered_by_email)
          VALUES (?,?,?,?,?,?,?,?)""", (plot_id, observation["date"], observation["rainfall_mm"],
          observation["humidity_pct"], observation["temp_c"], observation["days_since_last_spray"],
          observation.get("inspection_note") or None, entered_by))


def get_past_overrides(bucket, limit=3):
    with connect() as db:
        rows = _execute(db, """SELECT id,plot_id,risk_bucket,recommendation,human_decision,human_reason
          FROM field_decisions WHERE risk_bucket=? AND human_decision IS NOT NULL
          AND human_decision != recommendation ORDER BY id DESC LIMIT ?""", (bucket, int(limit))).fetchall()
    return [dict(row) for row in rows]


def add_decision(result):
    with connect() as db:
        cur = _execute(db, """INSERT INTO field_decisions
          (plot_id,created_at,risk_bucket,recommendation,rationale,evidence_json,confidence,gated,cited_case_ids)
          VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""", (result["plot_id"], result["ts"], result["risk_bucket"],
          result["action"], result["rationale"], json.dumps(result["evidence"]), result["confidence"],
          int(result["gated"]), json.dumps(result["cited_case_ids"])))
        row = cur.fetchone()
        return int(row["id"] if isinstance(row, dict) else row[0])


def record_human_decision(decision_id, action, reason=None):
    with connect() as db:
        _execute(db, "UPDATE field_decisions SET human_decision=?,human_reason=? WHERE id=? AND human_decision IS NULL",
                 (action, reason, decision_id))


def get_decision(decision_id):
    with connect() as db:
        row = _execute(db, "SELECT * FROM field_decisions WHERE id=?", (decision_id,)).fetchone()
    return dict(row) if row else None


def audit_log():
    with connect() as db:
        rows = _execute(db, """SELECT id,plot_id,created_at AS ts,risk_bucket,recommendation,rationale,
          evidence_json,confidence,gated,human_decision,human_reason,cited_case_ids
          FROM field_decisions ORDER BY id DESC""").fetchall()
    return [dict(row) for row in rows]
