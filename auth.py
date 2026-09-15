"""UNG-OLYMPUS — authentication & RBAC."""
import base64, hashlib, hmac, json, os, secrets, struct, time
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_db, DOMAINS
PBKDF2_ITERATIONS=260_000
BACKUP_CODE_COUNT=10

def _load_jwt_secret():
    env_secret=os.environ.get("OLYMPUS_JWT_SECRET")
    if env_secret: return env_secret
    secret_file=os.environ.get("OLYMPUS_JWT_SECRET_FILE", ".jwt_secret")
    try:
        if os.path.exists(secret_file):
            with open(secret_file) as f: return f.read().strip()
        generated=secrets.token_hex(32)
        with open(secret_file,"w") as f: f.write(generated)
        print("[OLYMPUS] WARNING: OLYMPUS_JWT_SECRET is not set. Generated a local fallback secret; set the environment variable before production deployment.")
        return generated
    except OSError:
        print("[OLYMPUS] WARNING: OLYMPUS_JWT_SECRET is not set and fallback persistence failed.")
        return secrets.token_hex(32)
JWT_SECRET=_load_jwt_secret()
JWT_TTL_BY_ROLE={"commander":2*3600,"domain_controller":4*3600,"analyst":8*3600,"integrator":8*3600}
JWT_TTL_SECONDS=8*3600
_bearer=HTTPBearer(auto_error=False)

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),PBKDF2_ITERATIONS)
    return digest.hex(),salt

def verify_password(password,password_hash,salt):
    digest,_=hash_password(password,salt); return hmac.compare_digest(digest,password_hash)

def new_totp_secret(): return base64.b32encode(secrets.token_bytes(20)).decode()
def totp_code(secret_b32,for_time=None):
    key=base64.b32decode(secret_b32.upper()); counter=int((for_time or time.time())//30); msg=struct.pack(">Q",counter)
    digest=hmac.new(key,msg,hashlib.sha1).digest(); offset=digest[-1]&0x0F
    code=(struct.unpack(">I",digest[offset:offset+4])[0]&0x7FFFFFFF)%1_000_000
    return f"{code:06d}"
def verify_totp(secret_b32,code,window=1):
    now=time.time()
    return any(hmac.compare_digest(totp_code(secret_b32,now+step*30),code) for step in range(-window,window+1))
def generate_backup_codes(count=BACKUP_CODE_COUNT): return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]
def store_backup_codes(conn,user_id,codes):
    conn.execute("DELETE FROM mfa_backup_codes WHERE user_id=?",(user_id,))
    for code in codes:
        code_hash,salt=hash_password(code); conn.execute("INSERT INTO mfa_backup_codes (user_id, code_hash, salt, used, created_at) VALUES (?, ?, ?, 0, ?)",(user_id,code_hash,salt,time.time()))
    conn.commit()
def consume_backup_code(conn,user_id,code):
    rows=conn.execute("SELECT id, code_hash, salt FROM mfa_backup_codes WHERE user_id=? AND used=0",(user_id,)).fetchall()
    for row in rows:
        if verify_password(code,row["code_hash"],row["salt"]):
            conn.execute("UPDATE mfa_backup_codes SET used=1, used_at=? WHERE id=?",(time.time(),row["id"])); conn.commit(); return True
    return False

def _b64url(data): return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def _b64url_decode(s): return base64.urlsafe_b64decode(s+"="*(-len(s)%4))
def issue_token(user_row):
    ttl=JWT_TTL_BY_ROLE.get(user_row["role"],JWT_TTL_SECONDS); header={"alg":"HS256","typ":"JWT"}; payload={"sub":user_row["email"],"role":user_row["role"],"uid":user_row["id"],"iat":int(time.time()),"exp":int(time.time())+ttl}
    signing_input=f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"; sig=hmac.new(JWT_SECRET.encode(),signing_input.encode(),hashlib.sha256).digest(); return f"{signing_input}.{_b64url(sig)}"
def decode_token(token):
    try:
        header_b64,payload_b64,sig_b64=token.split("."); signing_input=f"{header_b64}.{payload_b64}"; expected=hmac.new(JWT_SECRET.encode(),signing_input.encode(),hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url(expected),sig_b64): raise ValueError()
        payload=json.loads(_b64url_decode(payload_b64));
        if payload["exp"]<time.time(): raise ValueError()
        return payload
    except Exception: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired token")

class CurrentUser:
    def __init__(self,uid,email,role,domains): self.uid=uid; self.email=email; self.role=role; self.domains=domains
    def can_see(self,domain): return self.role=="commander" or domain in self.domains
    def can_task(self,domain): return self.role in ("commander","domain_controller") and self.can_see(domain)
def get_current_user(creds:HTTPAuthorizationCredentials=Depends(_bearer)):
    if creds is None: raise HTTPException(status_code=401,detail="Missing bearer token")
    payload=decode_token(creds.credentials); conn=get_db()
    try: domains=[r["domain"] for r in conn.execute("SELECT domain FROM user_domains WHERE user_id=?",(payload["uid"],)).fetchall()]
    finally: conn.close()
    return CurrentUser(payload["uid"],payload["sub"],payload["role"],domains)
def require_role(*roles):
    def checker(user:CurrentUser=Depends(get_current_user)):
        if user.role not in roles: raise HTTPException(status_code=403,detail="Insufficient role")
        return user
    return checker

def bootstrap_admin_if_empty():
    conn=get_db()
    try:
        if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]>0: return
        email=os.environ.get("OLYMPUS_ADMIN_EMAIL","admin@ung-olympus.local"); password=os.environ.get("OLYMPUS_ADMIN_PASSWORD") or secrets.token_urlsafe(12); pw_hash,salt=hash_password(password)
        cur=conn.execute("INSERT INTO users (email,password_hash,salt,role,mfa_enabled,created_at) VALUES (?, ?, ?, 'commander', 0, ?)",(email,pw_hash,salt,time.time())); uid=cur.lastrowid
        for d in DOMAINS: conn.execute("INSERT INTO user_domains (user_id, domain) VALUES (?, ?)",(uid,d))
        conn.commit()
        if not os.environ.get("OLYMPUS_ADMIN_PASSWORD"): print(f"[OLYMPUS] Bootstrapped commander account {email} / {password} — change this immediately.")
    finally: conn.close()
