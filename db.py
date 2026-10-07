"""Small SQLite persistence layer."""
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("COCOA_DB_PATH", Path(__file__).parent / "cocoa.db"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS weather_daily (
          plot_id TEXT NOT NULL, date TEXT NOT NULL, rainfall_mm REAL NOT NULL,
          humidity_pct REAL NOT NULL, temp_c REAL NOT NULL,
          days_since_last_spray INTEGER NOT NULL, inspection_note TEXT, entered_by TEXT,
          PRIMARY KEY (plot_id, date));
        CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, plot_id TEXT NOT NULL, ts TEXT NOT NULL,
          risk_bucket TEXT NOT NULL, recommendation TEXT NOT NULL, rationale TEXT NOT NULL,
          evidence_json TEXT NOT NULL, confidence REAL NOT NULL, gated INTEGER NOT NULL,
          human_decision TEXT, human_reason TEXT, cited_case_ids TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS auth_accounts (
          google_sub TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'inputer', totp_secret_enc TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS inputer_invites (
          email TEXT PRIMARY KEY, name TEXT NOT NULL, invited_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS blocked_auth_identities (
          google_sub TEXT PRIMARY KEY, email TEXT NOT NULL, blocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """)
        weather_columns = {row["name"] for row in db.execute("PRAGMA table_info(weather_daily)")}
        if "entered_by" not in weather_columns:
            db.execute("ALTER TABLE weather_daily ADD COLUMN entered_by TEXT")
        db.execute("UPDATE auth_accounts SET role='inputer' WHERE role='user'")


def get_or_create_auth_account(google_sub, email, name, bootstrap_role="inputer"):
    allowed_roles = {"inputer", "admin", "administrator", "manager"}
    if bootstrap_role not in allowed_roles:
        bootstrap_role = "inputer"
    email = email.strip().lower()
    with connect() as db:
        blocked = db.execute("SELECT 1 FROM blocked_auth_identities WHERE google_sub=? OR email=?", (google_sub, email)).fetchone()
        if blocked:
            return None
        row = db.execute("SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        if row is None:
            invitation = db.execute("SELECT name FROM inputer_invites WHERE email=?", (email,)).fetchone()
            role = bootstrap_role if bootstrap_role != "inputer" else "inputer"
            db.execute("INSERT INTO auth_accounts (google_sub,email,name,role) VALUES (?,?,?,?)",
                       (google_sub, email, name or (invitation["name"] if invitation else email), role))
            db.execute("DELETE FROM inputer_invites WHERE email=?", (email,))
            row = db.execute("SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        else:
            if bootstrap_role != "inputer":
                db.execute("UPDATE auth_accounts SET email=?,name=?,role=? WHERE google_sub=?",
                           (email, name, bootstrap_role, google_sub))
            else:
                db.execute("UPDATE auth_accounts SET email=?,name=? WHERE google_sub=?", (email, name, google_sub))
            row = db.execute("SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        return dict(row)


def set_totp_secret(google_sub, encrypted_secret):
    with connect() as db:
        db.execute("UPDATE auth_accounts SET totp_secret_enc=? WHERE google_sub=?",
                   (encrypted_secret, google_sub))


def auth_account(google_sub):
    with connect() as db:
        row = db.execute("SELECT * FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
    return dict(row) if row else None


def auth_accounts():
    with connect() as db:
        rows = db.execute("SELECT google_sub,email,name,role,created_at,CASE WHEN totp_secret_enc IS NULL THEN 'Not enrolled' ELSE 'Enrolled' END AS authenticator FROM auth_accounts ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def inputer_invites():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT email,name,invited_by,created_at FROM inputer_invites ORDER BY created_at DESC")]


def create_inputer_invite(email, name, invited_by):
    email = email.strip().lower()
    with connect() as db:
        exists = db.execute("SELECT 1 FROM auth_accounts WHERE lower(email)=?", (email,)).fetchone()
        if exists:
            return False, "An account with that email already exists."
        try:
            db.execute("INSERT INTO inputer_invites(email,name,invited_by) VALUES(?,?,?)", (email, name.strip(), invited_by))
        except sqlite3.IntegrityError:
            return False, "An inputer invitation for that email already exists."
        db.execute("DELETE FROM blocked_auth_identities WHERE email=?", (email,))
    return True, "Inputer invitation added. The person must sign in with this Google email to activate it."


def delete_inputer_account(google_sub):
    with connect() as db:
        account = db.execute("SELECT name,email,role FROM auth_accounts WHERE google_sub=?", (google_sub,)).fetchone()
        if not account or account["role"] != "inputer":
            return False
        db.execute("INSERT OR REPLACE INTO blocked_auth_identities(google_sub,email) VALUES(?,?)", (google_sub, account["email"]))
        db.execute("DELETE FROM auth_accounts WHERE google_sub=? AND role='inputer'", (google_sub,))
    return True


def delete_inputer_invite(email):
    with connect() as db:
        cursor = db.execute("DELETE FROM inputer_invites WHERE email=?", (email.strip().lower(),))
    return cursor.rowcount > 0


def seed_weather(rows):
    with connect() as db:
        db.executemany("""INSERT OR IGNORE INTO weather_daily
          (plot_id,date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note)
          VALUES (:plot_id,:date,:rainfall_mm,:humidity_pct,:temp_c,:days_since_last_spray,:inspection_note)""", rows)


def weather_for_plot(plot_id, limit=None):
    query = "SELECT * FROM weather_daily WHERE plot_id=? ORDER BY date DESC"
    params = [plot_id]
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with connect() as db:
        rows = [dict(row) for row in db.execute(query, params)]
    return list(reversed(rows))


def add_weather_observation(plot_id, observation, entered_by):
    with connect() as db:
        db.execute("""INSERT INTO weather_daily
          (plot_id,date,rainfall_mm,humidity_pct,temp_c,days_since_last_spray,inspection_note,entered_by)
          VALUES (?,?,?,?,?,?,?,?)""", (plot_id, observation["date"], observation["rainfall_mm"],
          observation["humidity_pct"], observation["temp_c"], observation["days_since_last_spray"],
          observation.get("inspection_note") or None, entered_by))


def get_past_overrides(bucket, limit=3):
    with connect() as db:
        rows = db.execute("""SELECT id,plot_id,risk_bucket,recommendation,human_decision,human_reason
          FROM decisions WHERE risk_bucket=? AND human_decision IS NOT NULL
          AND human_decision != recommendation ORDER BY id DESC LIMIT ?""", (bucket, limit)).fetchall()
    return [dict(row) for row in rows]


def add_decision(result):
    with connect() as db:
        cur = db.execute("""INSERT INTO decisions
          (plot_id,ts,risk_bucket,recommendation,rationale,evidence_json,confidence,gated,cited_case_ids)
          VALUES (?,?,?,?,?,?,?,?,?)""", (result["plot_id"], result["ts"], result["risk_bucket"],
          result["action"], result["rationale"], json.dumps(result["evidence"]), result["confidence"],
          int(result["gated"]), json.dumps(result["cited_case_ids"])))
        return cur.lastrowid


def record_human_decision(decision_id, action, reason=None):
    with connect() as db:
        db.execute("UPDATE decisions SET human_decision=?,human_reason=? WHERE id=? AND human_decision IS NULL",
                   (action, reason, decision_id))


def get_decision(decision_id):
    with connect() as db:
        row = db.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()
    return dict(row) if row else None


def audit_log():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM decisions ORDER BY id DESC")]
