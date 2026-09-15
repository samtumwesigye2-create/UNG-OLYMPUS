from fastapi import APIRouter, Depends
from auth import CurrentUser, get_current_user
from registry import ADAPTERS_BY_DOMAIN, DOMAIN_LABELS, DOMAIN_PHASE
from db import DOMAINS
router = APIRouter(prefix="/cop", tags=["cop"])

@router.get("")
def get_cop(user: CurrentUser = Depends(get_current_user)):
    domains_out = []
    for domain in DOMAINS:
        if not user.can_see(domain): continue
        adapters = ADAPTERS_BY_DOMAIN.get(domain, [])
        if not adapters:
            domains_out.append({"domain":domain,"label":DOMAIN_LABELS[domain],"integrated":False,"phase":DOMAIN_PHASE[domain],"message":f"Not yet integrated — scheduled for Phase {DOMAIN_PHASE[domain]} of the rollout","subsystems":[]})
            continue
        statuses=[a.fetch_status().to_dict() for a in adapters]
        domains_out.append({"domain":domain,"label":DOMAIN_LABELS[domain],"integrated":True,"phase":DOMAIN_PHASE[domain],"healthy":all(s["healthy"] for s in statuses),"subsystems":statuses})
    return {"domains":domains_out,"role":user.role,"viewer":user.email}
