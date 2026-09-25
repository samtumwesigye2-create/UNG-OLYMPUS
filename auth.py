"""
UNG-OLYMPUS — authentication & RBAC.

Same pattern as the rest of the UNG ecosystem: PBKDF2 password hashing,
JWT session tokens, TOTP MFA for elevated roles. Implemented with the
standard library only (hashlib, hmac, base64, struct, json) — no PyJWT
or pyotp dependency, matching the "stdlib only" convention already used
in auth.py for the tax filing app.

RBAC has two independent axes:
  - role: commander | domain_controller | analyst | integrator
  - domain scope: which of (defense, emergency, logistics, itinfra) a
    user is allowed to see/act in. Commander implicitly sees all domains.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from db import get_db, DOMAINS

PBKDF2_ITERATIONS = 260_000
BACKUP_CODE_COUNT = 10


def _load_jwt_secret() -> str:
    """OLYMPUS_JWT_SECRET should be set explicitly in production — if it
    isn't, every restart would otherwise mint a new random secret and
    silently invalidate every session. As a fallback (mainly for local
    dev), persist a generated secret to a local file so it survives
    restarts within the same filesystem, and warn loudly either way."""
    env_secret = os.environ.get("OLYMPUS_JWT_SECRET")
    if env_secret:
        return env_secret

    secret_file = os.environ.get("OLYMPUS_JWT_SECRET_FILE", ".jwt_secret")
    try:
        if os.path.exists(secret_file):
            with open(secret_file) as f:
                return f.read().strip()
        generated = secrets.token_hex(32)
        with open(secret_file, "w") as f:
            f.write(generated)
        print(
            "[OLYMPUS] WARNING: OLYMPUS_JWT_SECRET is not set. Generated one and "
            f"saved it to {secret_file} so sessions survive a restart, but this file "
            "will NOT survive a fresh deploy (e.g. a new Railway build) — every "
            "deploy will silently log everyone out until you set OLYMPUS_JWT_SECRET "
            "as a real environment variable."
        )
        return generated
    except OSError:
        # Read-only filesystem or similar — fall back to in-memory only,
        # which means every process restart invalidates all sessions.
        print(
            "[OLYMPUS] WARNING: OLYMPUS_JWT_SECRET is not set and no writable "
            "filesystem is available to persist a generated one. Sessions will "
            "NOT survive a restart. Set OLYMPUS_JWT_SECRET as an environment variable."
        )
        return secrets.token_hex(32)


JWT_SECRET = _load_jwt_secret()

# Zero-trust-flavored session lifetimes: "never trust, always verify" means
# a session shouldn't be trusted indefinitely just because it authenticated
# once — elevated roles re-prove identity (MFA) more often than read-only ones.
JWT_TTL_BY_ROLE = {
    "commander": 2 * 3600,
    "domain_controller": 4 * 3600,
    "analyst": 8 * 3600,
    "integrator": 8 * 3600,
}
JWT_TTL_SECONDS = 8 * 3600  # fallback

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------- passwords

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    digest, _ = hash_password(password, salt)
    return hmac.compare_digest(digest, password_hash)


# --------------------------------------------------------------------- TOTP
# RFC 6238, 30-second step, 6 digits — implemented directly so MFA has no
# third-party dependency.

def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp_code(secret_b32: str, for_time: float | None = None) -> str:
    key = base64.b32decode(secret_b32.upper())
    counter = int((for_time or time.time()) // 30)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    now = time.time()
    for step in range(-window, window + 1):
        if hmac.compare_digest(totp_code(secret_b32, now + step * 30), code):
            return True
    return False


# ------------------------------------------------------------ MFA backup codes
# Recovery path for a lost MFA device. Generated once when MFA is enabled
# (or regenerated on demand), shown to the user exactly once in plaintext,
# stored only as PBKDF2 hashes. Each code is single-use.

def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def store_backup_codes(conn, user_id: int, codes: list[str]) -> None:
    conn.execute("DELETE FROM mfa_backup_codes WHERE user_id=?", (user_id,))
    for code in codes:
        code_hash, salt = hash_password(code)
        conn.execute(
            "INSERT INTO mfa_backup_codes (user_id, code_hash, salt, used, created_at) VALUES (?, ?, ?, 0, ?)",
            (user_id, code_hash, salt, time.time()),
        )
    conn.commit()


def consume_backup_code(conn, user_id: int, code: str) -> bool:
    """Checks `code` against this user's unused backup codes; if it matches,
    marks that code used (one-time) and returns True."""
    rows = conn.execute(
        "SELECT id, code_hash, salt FROM mfa_backup_codes WHERE user_id=? AND used=0", (user_id,)
    ).fetchall()
    for row in rows:
        if verify_password(code, row["code_hash"], row["salt"]):
            conn.execute(
                "UPDATE mfa_backup_codes SET used=1, used_at=? WHERE id=?", (time.time(), row["id"])
            )
            conn.commit()
            return True
    return False


# ---------------------------------------------------------------------- JWT
# Minimal HS256 JWT — header/payload/signature, stdlib only.

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_token(user_row) -> str:
    ttl = JWT_TTL_BY_ROLE.get(user_row["role"], JWT_TTL_SECONDS)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_row["email"],
        "role": user_row["role"],
        "uid": user_row["id"],
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def decode_token(token: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url(expected_sig), sig_b64):
            raise ValueError("bad signature")
        payload = json.loads(_b64url_decode(payload_b64))
        if payload["exp"] < time.time():
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


# ---------------------------------------------------------- request helpers

class CurrentUser:
    def __init__(self, uid: int, email: str, role: str, domains: list[str]):
        self.uid = uid
        self.email = email
        self.role = role
        self.domains = domains  # explicit scope; commander sees all regardless

    def can_see(self, domain: str) -> bool:
        return self.role == "commander" or domain in self.domains

    def can_task(self, domain: str) -> bool:
        if self.role not in ("commander", "domain_controller"):
            return False
        return self.can_see(domain)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_token(creds.credentials)
    conn = get_db()
    try:
        rows = conn.execute("SELECT domain FROM user_domains WHERE user_id=?", (payload["uid"],)).fetchall()
        domains = [r["domain"] for r in rows]
    finally:
        conn.close()
    return CurrentUser(uid=payload["uid"], email=payload["sub"], role=payload["role"], domains=domains)


def require_role(*roles):
    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return checker


def bootstrap_admin_if_empty():
    """Create a first commander account from env vars if the users table is empty,
    so a fresh deploy isn't locked out. Mirrors the pattern of seeding an initial
    admin used elsewhere in the ecosystem."""
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count > 0:
            return
        email = os.environ.get("OLYMPUS_ADMIN_EMAIL", "admin@ung-olympus.local")
        password = os.environ.get("OLYMPUS_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        pw_hash, salt = hash_password(password)
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, salt, role, mfa_enabled, created_at) "
            "VALUES (?, ?, ?, 'commander', 0, ?)",
            (email, pw_hash, salt, time.time()),
        )
        uid = cur.lastrowid
        for d in DOMAINS:
            conn.execute("INSERT INTO user_domains (user_id, domain) VALUES (?, ?)", (uid, d))
        conn.commit()
        if not os.environ.get("OLYMPUS_ADMIN_PASSWORD"):
            print(f"[OLYMPUS] Bootstrapped commander account {email} / {password} — change this immediately.")
    finally:
        conn.close()
