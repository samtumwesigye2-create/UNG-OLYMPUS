import json,time
from abc import ABC,abstractmethod
from db import get_db
class SubsystemStatus:
    def __init__(self,subsystem,healthy,summary,metrics,mode="demo",stale_since=None): self.subsystem=subsystem; self.healthy=healthy; self.summary=summary; self.metrics=metrics; self.mode=mode; self.stale_since=stale_since
    def to_dict(self): return {"subsystem":self.subsystem,"healthy":self.healthy,"summary":self.summary,"metrics":self.metrics,"source":self.mode,"stale_since":self.stale_since}
def save_cache(subsystem,status):
    conn=get_db()
    try: conn.execute("INSERT INTO subsystem_cache (subsystem,status_json,cached_at) VALUES (?, ?, ?) ON CONFLICT(subsystem) DO UPDATE SET status_json=excluded.status_json,cached_at=excluded.cached_at",(subsystem,json.dumps(status.to_dict()),time.time())); conn.commit()
    finally: conn.close()
def load_cache(subsystem):
    conn=get_db()
    try:
        row=conn.execute("SELECT status_json,cached_at FROM subsystem_cache WHERE subsystem=?",(subsystem,)).fetchone(); return None if row is None else {"data":json.loads(row["status_json"]),"cached_at":row["cached_at"]}
    finally: conn.close()
class DirectiveResult:
    def __init__(self,accepted,ack_message): self.accepted=accepted; self.ack_message=ack_message
class SubsystemAdapter(ABC):
    name:str; domain:str; writable=False
    @abstractmethod
    def fetch_status(self): ...
    def fetch_events(self,since): return []
    def send_directive(self,action,payload):
        if not self.writable: return DirectiveResult(False,f"{self.name} adapter is read-only in this phase")
        raise NotImplementedError
