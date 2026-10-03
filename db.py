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
          days_since_last_spray INTEGER NOT NULL, inspection_note TEXT,
          PRIMARY KEY (plot_id, date));
        CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT, plot_id TEXT NOT NULL, ts TEXT NOT NULL,
          risk_bucket TEXT NOT NULL, recommendation TEXT NOT NULL, rationale TEXT NOT NULL,
          evidence_json TEXT NOT NULL, confidence REAL NOT NULL, gated INTEGER NOT NULL,
          human_decision TEXT, human_reason TEXT, cited_case_ids TEXT NOT NULL);
        """)


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
