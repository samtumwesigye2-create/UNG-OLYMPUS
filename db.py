"""UNG-OLYMPUS — database layer."""
import sqlite3
import time
import os

DB_PATH = os.environ.get("OLYMPUS_DB_PATH", "olympus.db")
DOMAINS = ("defense", "emergency", "logistics", "itinfra")
ROLES = ("commander", "domain_controller", "analyst", "integrator")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,salt TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('commander','domain_controller','analyst','integrator')),mfa_secret TEXT,mfa_enabled INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS user_domains (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,domain TEXT NOT NULL CHECK(domain IN ('defense','emergency','logistics','itinfra')),PRIMARY KEY (user_id, domain));
CREATE TABLE IF NOT EXISTS mfa_backup_codes (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,code_hash TEXT NOT NULL,salt TEXT NOT NULL,used INTEGER NOT NULL DEFAULT 0,used_at REAL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (email TEXT PRIMARY KEY,failed_count INTEGER NOT NULL DEFAULT 0,first_failed_at REAL,locked_until REAL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,domain TEXT NOT NULL,subsystem TEXT,event_type TEXT NOT NULL,severity TEXT NOT NULL DEFAULT 'info',summary TEXT NOT NULL,detail_json TEXT,actor_email TEXT,occurred_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS directives (id INTEGER PRIMARY KEY AUTOINCREMENT,domain TEXT NOT NULL,subsystem TEXT NOT NULL,action TEXT NOT NULL,payload_json TEXT,issued_by TEXT NOT NULL,issued_at REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending',subsystem_ack TEXT,ack_at REAL,requires_approval INTEGER NOT NULL DEFAULT 0,approved_by TEXT,approved_at REAL);
CREATE TABLE IF NOT EXISTS subsystem_cache (subsystem TEXT PRIMARY KEY,status_json TEXT NOT NULL,cached_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT,domain TEXT NOT NULL,rule TEXT NOT NULL,severity TEXT NOT NULL DEFAULT 'warning',summary TEXT NOT NULL,correlated_domains TEXT,created_at REAL NOT NULL,resolved INTEGER NOT NULL DEFAULT 0);
"""

def init_db():
    conn = get_db(); conn.executescript(SCHEMA); conn.commit(); conn.close()

def log_event(conn, domain, event_type, summary, subsystem=None, severity="info", detail_json=None, actor_email=None):
    conn.execute("INSERT INTO events (domain, subsystem, event_type, severity, summary, detail_json, actor_email, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",(domain, subsystem, event_type, severity, summary, detail_json, actor_email, time.time()))
    conn.commit()
