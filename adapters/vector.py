import os,random,time,requests
from .base import SubsystemAdapter,SubsystemStatus,DirectiveResult,save_cache,load_cache
TIMEOUT=4
class VectorAdapter(SubsystemAdapter):
    name="VECTOR"; domain="logistics"; writable=True
    def __init__(self): self.base_url=os.environ.get("VECTOR_API_URL","").rstrip("/"); self.api_key=os.environ.get("VECTOR_API_KEY","")
    def _configured(self): return bool(self.base_url and self.api_key)
    def fetch_status(self):
        if self._configured():
            try:
                r=requests.get(f"{self.base_url}/api/status",headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); data=r.json(); status=SubsystemStatus("VECTOR",True,data.get("summary","VECTOR reporting normally"),data.get("metrics",{}),"live"); save_cache("VECTOR",status); return status
            except Exception as exc:
                cached=load_cache("VECTOR")
                if cached:
                    d=cached["data"]; return SubsystemStatus("VECTOR",d["healthy"],f"{d['summary']} (cached — live link down: {exc.__class__.__name__})",d["metrics"],"cached",cached["cached_at"])
                return SubsystemStatus("VECTOR",False,f"VECTOR configured but unreachable ({exc.__class__.__name__}), no cached reading yet",{},"live")
        random.seed(int(time.time()//300)+1); capacity_pct=random.randint(55,96); return SubsystemStatus("VECTOR",capacity_pct<92,f"Warehouse capacity at {capacity_pct}% (demo data)",{"capacity_pct":capacity_pct,"open_orders":random.randint(20,140)},"demo")
    def fetch_events(self,since):
        if not self._configured(): return [{"subsystem":"VECTOR","summary":"Demo mode — connect VECTOR_API_URL/VECTOR_API_KEY for live events","severity":"info","occurred_at":time.time()}]
        try:
            r=requests.get(f"{self.base_url}/api/events",params={"since":since},headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); return r.json().get("events",[])
        except Exception: return []
    def send_directive(self,action,payload):
        if not self._configured(): return DirectiveResult(True,f"Demo mode: directive '{action}' logged but not sent — configure VECTOR_API_URL/KEY to task the real system")
        try:
            r=requests.post(f"{self.base_url}/api/directives",json={"action":action,"payload":payload},headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); return DirectiveResult(True,r.json().get("ack","accepted"))
        except Exception as exc: return DirectiveResult(False,f"VECTOR rejected/unreachable: {exc}")
