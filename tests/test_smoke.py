"""
Basic smoke tests. Requires fastapi/uvicorn/requests/httpx installed and
network-less TestClient usage (httpx). Not runnable in the build sandbox
(no PyPI access there) — run this wherever the app is actually deployed
or in any dev environment with `pip install -r requirements.txt httpx pytest`.
"""
import os
import time

os.environ.setdefault("OLYMPUS_DB_PATH", "test_olympus.db")
os.environ.setdefault("OLYMPUS_ADMIN_EMAIL", "test-admin@ung-olympus.local")
os.environ.setdefault("OLYMPUS_ADMIN_PASSWORD", "TestPass123!")

import pytest
from fastapi.testclient import TestClient

# Fresh DB per test run
if os.path.exists("test_olympus.db"):
    os.remove("test_olympus.db")

from main import app  # noqa: E402
from auth import new_totp_secret, totp_code, hash_password  # noqa: E402
from db import get_db  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_requires_mfa_for_commander():
    r = client.post("/auth/login", json={
        "email": "test-admin@ung-olympus.local", "password": "TestPass123!",
    })
    assert r.status_code == 403  # MFA not set up yet


def test_full_commander_flow():
    # Manually enable MFA for the bootstrapped admin so we can log in
    secret = new_totp_secret()
    conn = get_db()
    conn.execute("UPDATE users SET mfa_secret=?, mfa_enabled=1 WHERE email=?",
                 (secret, "test-admin@ung-olympus.local"))
    conn.commit()
    conn.close()

    code = totp_code(secret)
    r = client.post("/auth/login", json={
        "email": "test-admin@ung-olympus.local", "password": "TestPass123!", "totp_code": code,
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/cop", headers=headers)
    assert r.status_code == 200
    domains = {d["domain"]: d for d in r.json()["domains"]}
    assert domains["logistics"]["integrated"] is True
    assert domains["defense"]["integrated"] is False  # Phase 3, not wired yet

    r = client.post("/directives", headers=headers, json={
        "domain": "logistics", "subsystem": "MERCURY", "action": "test_action", "payload": {},
    })
    assert r.status_code == 200
    assert r.json()["status"] in ("acknowledged", "rejected")

    r = client.get("/events", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["events"]) > 0
