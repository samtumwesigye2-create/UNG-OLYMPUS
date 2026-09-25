import json,time
from fastapi import APIRouter,Depends,HTTPException
from auth import CurrentUser,get_current_user
from db import get_db,log_event
from registry import ADAPTERS_BY_DOMAIN
router=APIRouter(prefix="/alerts",tags=["alerts"]); CORRELATION_WINDOW_SECONDS=900; VECTOR_CAPACITY_WARN_PCT=90; MERCURY_EXCEPTION_WARN_COUNT=8
def _evaluate_logistics_rules(conn):
    fired=[]
    for adapter in ADAPTERS_BY_DOMAIN.get("logistics",[]):
        status=adapter.fetch_status(); metrics=status.metrics
        if adapter.name=="VECTOR" and metrics.get("capacity_pct",0)>=VECTOR_CAPACITY_WARN_PCT: fired.append({"domain":"logistics","rule":"capacity_trend","severity":"warning","summary":f"VECTOR warehouse capacity at {metrics['capacity_pct']}% (threshold {VECTOR_CAPACITY_WARN_PCT}%)"})
        if adapter.name=="MERCURY" and metrics.get("exceptions",0)>=MERCURY_EXCEPTION_WARN_COUNT: fired.append({"domain":"logistics","rule":"exception_rate_anomaly","severity":"warning","summary":f"MERCURY exception count at {metrics['exceptions']} (threshold {MERCURY_EXCEPTION_WARN_COUNT})"})
    return fired
def _correlate(conn,new_alerts):
    now=time.time(); inserted=[]
    for alert in new_alerts:
        recent=conn.execute("SELECT DISTINCT domain FROM alerts WHERE resolved=0 AND created_at >= ? AND domain != ?",(now-CORRELATION_WINDOW_SECONDS,alert["domain"])).fetchall(); correlated=",".join(r["domain"] for r in recent) or None
        conn.execute("INSERT INTO alerts (domain,rule,severity,summary,correlated_domains,created_at,resolved) VALUES (?, ?, ?, ?, ?, ?, 0)",(alert["domain"],alert["rule"],alert["severity"],alert["summary"],correlated,now)); alert["correlated_domains"]=correlated; inserted.append(alert); log_event(conn,alert["domain"],"alert",alert["summary"],severity=alert["severity"],detail_json=json.dumps({"rule":alert["rule"],"correlated_domains":correlated}))
    conn.commit(); return inserted
@router.post("/refresh")
def refresh_alerts(user:CurrentUser=Depends(get_current_user)):
    conn=get_db()
    try: return {"new_alerts":_correlate(conn,_evaluate_logistics_rules(conn) if user.can_see("logistics") else [])}
    finally: conn.close()
@router.get("")
def list_alerts(user:CurrentUser=Depends(get_current_user),include_resolved:bool=False,limit:int=50,offset:int=0):
    conn=get_db()
    try:
        q="SELECT * FROM alerts"+("" if include_resolved else " WHERE resolved=0")+" ORDER BY created_at DESC LIMIT ? OFFSET ?"; rows=conn.execute(q,(limit,offset)).fetchall(); return {"alerts":[dict(r) for r in rows if user.can_see(r["domain"])],"limit":limit,"offset":offset}
    finally: conn.close()
@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id:int,user:CurrentUser=Depends(get_current_user)):
    conn=get_db()
    try:
        row=conn.execute("SELECT * FROM alerts WHERE id=?",(alert_id,)).fetchone()
        if row is None: raise HTTPException(status_code=404,detail="Alert not found")
        if not user.can_task(row["domain"]): raise HTTPException(status_code=403,detail="Not authorized to resolve alerts in this domain")
        conn.execute("UPDATE alerts SET resolved=1 WHERE id=?",(alert_id,)); conn.commit(); log_event(conn,row["domain"],"system",f"{user.email} resolved alert #{alert_id}: {row['summary']}",actor_email=user.email); return {"id":alert_id,"resolved":True}
    finally: conn.close()
events_router=APIRouter(prefix="/events",tags=["events"])
@events_router.get("")
def list_events(user:CurrentUser=Depends(get_current_user),limit:int=100,offset:int=0):
    conn=get_db()
    try: return {"events":[dict(r) for r in conn.execute("SELECT * FROM events ORDER BY occurred_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall() if user.can_see(r["domain"])],"limit":limit,"offset":offset}
    finally: conn.close()
