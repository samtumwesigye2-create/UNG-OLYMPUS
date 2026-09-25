import json,time
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from auth import CurrentUser,get_current_user
from db import get_db,log_event
from registry import ADAPTERS_BY_SUBSYSTEM
router=APIRouter(prefix="/directives",tags=["directives"])
class DirectiveIn(BaseModel):
    domain:str; subsystem:str; action:str; payload:dict={}; sensitive:bool=False
def _execute_on_subsystem(conn,directive_id,domain,subsystem,action,payload,actor_email):
    result=ADAPTERS_BY_SUBSYSTEM[subsystem].send_directive(action,payload); status_val="acknowledged" if result.accepted else "rejected"
    conn.execute("UPDATE directives SET status=?, subsystem_ack=?, ack_at=? WHERE id=?",(status_val,result.ack_message,time.time(),directive_id)); conn.commit()
    log_event(conn,domain,"directive_ack" if result.accepted else "directive_rejected",result.ack_message,subsystem=subsystem,severity="info" if result.accepted else "warning",actor_email=actor_email)
    return {"id":directive_id,"status":status_val,"ack_message":result.ack_message}
@router.post("")
def issue_directive(body:DirectiveIn,user:CurrentUser=Depends(get_current_user)):
    if not user.can_task(body.domain): raise HTTPException(status_code=403,detail="Not authorized to task this domain")
    adapter=ADAPTERS_BY_SUBSYSTEM.get(body.subsystem)
    if adapter is None or adapter.domain!=body.domain: raise HTTPException(status_code=400,detail=f"Unknown subsystem '{body.subsystem}' in domain '{body.domain}'")
    conn=get_db()
    try:
        initial="pending_approval" if body.sensitive else "pending"; cur=conn.execute("INSERT INTO directives (domain,subsystem,action,payload_json,issued_by,issued_at,status,requires_approval) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",(body.domain,body.subsystem,body.action,json.dumps(body.payload),user.email,time.time(),initial,int(body.sensitive))); did=cur.lastrowid; conn.commit()
        log_event(conn,body.domain,"directive_issued",f"{user.email} issued '{body.action}' to {body.subsystem}"+(" (awaiting second-person approval)" if body.sensitive else ""),subsystem=body.subsystem,actor_email=user.email,detail_json=json.dumps(body.payload))
        if body.sensitive: return {"id":did,"status":"pending_approval","ack_message":"Marked sensitive — needs approval from a different user before it's sent"}
        return _execute_on_subsystem(conn,did,body.domain,body.subsystem,body.action,body.payload,user.email)
    finally: conn.close()
@router.post("/{directive_id}/approve")
def approve_directive(directive_id:int,user:CurrentUser=Depends(get_current_user)):
    conn=get_db()
    try:
        row=conn.execute("SELECT * FROM directives WHERE id=?",(directive_id,)).fetchone()
        if row is None: raise HTTPException(status_code=404,detail="Directive not found")
        if row["status"]!="pending_approval": raise HTTPException(status_code=400,detail=f"Directive is not awaiting approval (status: {row['status']})")
        if not user.can_task(row["domain"]): raise HTTPException(status_code=403,detail="Not authorized to approve directives in this domain")
        if user.email==row["issued_by"]: raise HTTPException(status_code=403,detail="A directive cannot be approved by the same person who issued it")
        conn.execute("UPDATE directives SET status='pending', approved_by=?, approved_at=? WHERE id=?",(user.email,time.time(),directive_id)); conn.commit(); payload=json.loads(row["payload_json"] or "{}")
        return _execute_on_subsystem(conn,directive_id,row["domain"],row["subsystem"],row["action"],payload,user.email)
    finally: conn.close()
@router.get("")
def list_directives(user:CurrentUser=Depends(get_current_user),limit:int=50,offset:int=0):
    conn=get_db()
    try: return {"directives":[dict(r) for r in conn.execute("SELECT * FROM directives ORDER BY issued_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall() if user.can_see(r["domain"])],"limit":limit,"offset":offset}
    finally: conn.close()
