import os,random,time,requests
from .base import SubsystemAdapter,SubsystemStatus,DirectiveResult,save_cache,load_cache
TIMEOUT=4
class MercuryAdapter(SubsystemAdapter):
    name="MERCURY"; domain="logistics"; writable=True
    def __init__(self): self.base_url=os.environ.get("MERCURY_API_URL","").rstrip("/"); self.api_key=os.environ.get("MERCURY_API_KEY","")
    def _configured(self): return bool(self.base_url and self.api_key)
    def fetch_status(self):
        if self._configured():
            try:
                r=requests.get(f"{self.base_url}/api/status",headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); data=r.json(); status=SubsystemStatus("MERCURY",True,data.get("summary","MERCURY reporting normally"),data.get("metrics",{}),"live"); save_cache("MERCURY",status); return status
            except Exception as exc:
                cached=load_cache("MERCURY")
                if cached:
                    d=cached["data"]; return SubsystemStatus("MERCURY",d["healthy"],f"{d['summary']} (cached — live link down: {exc.__class__.__name__})",d["metrics"],"cached",cached["cached_at"])
                return SubsystemStatus("MERCURY",False,f"MERCURY configured but unreachable ({exc.__class__.__name__}), no cached reading yet",{},"live")
        random.seed(int(time.time()//300)); throughput=random.randint(180,420); exceptions=random.randint(0,12); return SubsystemStatus("MERCURY",exceptions<10,f"{throughput} packages/hr sorted, {exceptions} exceptions flagged (demo data)",{"throughput_per_hr":throughput,"exceptions":exceptions,"active_lanes":random.randint(4,9)},"demo")
    def fetch_events(self,since):
        if not self._configured(): return [{"subsystem":"MERCURY","summary":"Demo mode — connect MERCURY_API_URL/MERCURY_API_KEY for live events","severity":"info","occurred_at":time.time()}]
        try:
            r=requests.get(f"{self.base_url}/api/events",params={"since":since},headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); return r.json().get("events",[])
        except Exception: return []
    def send_directive(self,action,payload):
        if not self._configured(): return DirectiveResult(True,f"Demo mode: directive '{action}' logged but not sent — configure MERCURY_API_URL/KEY to task the real system")
        try:
            r=requests.post(f"{self.base_url}/api/directives",json={"action":action,"payload":payload},headers={"X-Service-Key":self.api_key},timeout=TIMEOUT); r.raise_for_status(); return DirectiveResult(True,r.json().get("ack","accepted"))
        except Exception as exc: return DirectiveResult(False,f"MERCURY rejected/unreachable: {exc}")
