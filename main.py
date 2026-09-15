"""
UNG-OLYMPUS — Phase 1 entrypoint.

Phase 1 scope (per the design doc): core platform — auth/RBAC, Common
Operating Picture, Tasking & Directives engine, alerting/correlation,
incident timeline — plus the Logistics domain (MERCURY + VECTOR
adapters). Defense/ISR, Emergency and IT/Infra exist as domains for
RBAC purposes but carry no adapters until Phases 2-4.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from db import init_db
from auth import bootstrap_admin_if_empty
import auth_routes
import cop
import tasking
import alerts
import metrics

app = FastAPI(title="UNG-OLYMPUS", version="0.1.0-phase1")

app.include_router(auth_routes.router)
app.include_router(auth_routes.users_router)
app.include_router(cop.router)
app.include_router(tasking.router)
app.include_router(alerts.router)
app.include_router(alerts.events_router)
app.include_router(metrics.router)


@app.on_event("startup")
def on_startup():
    init_db()
    bootstrap_admin_if_empty()


@app.get("/health")
def health():
    return {"status": "ok", "service": "UNG-OLYMPUS", "phase": 1}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def dashboard():
    return FileResponse("static/index.html")
