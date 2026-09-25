import time
from fastapi import APIRouter,Depends
from auth import CurrentUser,require_role
from db import get_db
router=APIRouter(prefix="/metrics",tags=["metrics"]); START_TIME=time.time()
@router.get("")
def get_metrics(user:CurrentUser=Depends(require_role("commander","integrator"))):
    conn=get_db()
    try:
        day_ago=time.time()-86400
        return {"uptime_seconds":round(time.time()-START_TIME,1),"users_total":conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],"active_alerts":conn.execute("SELECT COUNT(*) c FROM alerts WHERE resolved=0").fetchone()["c"],"directives_pending_approval":conn.execute("SELECT COUNT(*) c FROM directives WHERE status='pending_approval'").fetchone()["c"],"directives_last_24h":conn.execute("SELECT COUNT(*) c FROM directives WHERE issued_at >= ?",(day_ago,)).fetchone()["c"],"events_last_24h":conn.execute("SELECT COUNT(*) c FROM events WHERE occurred_at >= ?",(day_ago,)).fetchone()["c"],"accounts_currently_locked_out":conn.execute("SELECT COUNT(*) c FROM login_attempts WHERE locked_until > ?",(time.time(),)).fetchone()["c"]}
    finally: conn.close()
