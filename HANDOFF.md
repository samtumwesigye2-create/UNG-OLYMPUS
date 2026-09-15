# UNG-OLYMPUS — Phase 1 Handoff

Working name, Phase 1 of the design in `UNG-OLYMPUS-Design.docx`: core
platform (auth/RBAC, Common Operating Picture, Tasking & Directives
engine, alerting/correlation, incident timeline) plus the Logistics
domain (MERCURY + VECTOR adapters).

## Scope boundary

During design, additional "C2 capabilities" were requested that included
weapon-target pairing, automated target prioritization for engagement,
and related fire-control functions (sensor-to-shooter mesh, automated
target development, threat neutralization). None of that is in this
build, and none of it will be — OLYMPUS is a coordination and
situational-awareness platform (logistics, IT/infra, emergency dispatch,
ISR *status*, not ISR *targeting*), not a weapons system. Everything
else requested — Zero Trust posture, degraded-ops caching, SBOM, NIST
800-53-style control mapping, doctrine tiering — is reflected below and
in `SECURITY.md`.

## File map

```
main.py            FastAPI app entrypoint, mounts all routers, serves the dashboard
db.py               SQLite schema + connection helper (users, events, directives, alerts, subsystem_cache)
auth.py             Auth *library*: PBKDF2 hashing, stdlib HS256 JWT (persisted secret + startup warning if unset), stdlib TOTP MFA, backup/recovery codes, RBAC helpers
auth_routes.py      Auth *HTTP routes*: /auth/login (rate-limited), /auth/mfa/* (incl. backup-code regeneration), /users (commander-only admin)
registry.py         Maps each domain to its wired adapters (only Logistics has any in Phase 1)
cop.py              GET /cop — the Common Operating Picture
tasking.py          POST/GET /directives + /directives/{id}/approve — Tasking & Directives engine, with sensitive-directive dual-approval (separation of duties)
alerts.py           Rule-based alerting + cross-domain correlation; POST /alerts/{id}/resolve; GET /events (incident timeline, paginated)
metrics.py          GET /metrics — basic operational counts (commander/integrator only); not full Prometheus, see note below
adapters/base.py    Shared adapter interface + last-known-good cache helpers (degraded ops)
adapters/mercury.py MERCURY adapter — live API with demo-data and cached-data fallback
adapters/vector.py  VECTOR adapter — same pattern
static/index.html   Single-page dashboard: login (+ backup code), Operating Picture, Logistics/directives (+ sensitive flag, approve), alerts (+ resolve), Timeline, Admin
sbom.json           Hand-built direct-dependency SBOM (see SECURITY.md — regenerate properly once a build env has registry access)
SECURITY.md         Zero Trust / NIST 800-53-style posture: built vs. partial vs. explicitly out of scope
requirements.txt    fastapi, uvicorn[standard], requests — pinned versions
railway.toml        Railway deploy config, healthcheck at /health
.env.example        Every environment variable the app reads, with notes on which matter before a real deploy
tests/test_smoke.py Basic smoke tests (login, COP, directive flow) — see verification note below
```

## Gaps closed after the first Phase 1 pass

These six were flagged as missing and are now built:

1. **JWT secret persistence** — `OLYMPUS_JWT_SECRET` should be set explicitly (see `.env.example`); if it isn't, the app now persists a generated one to `.jwt_secret` and warns loudly in the logs instead of silently minting a new one (and invalidating every session) on each restart.
2. **Alert resolution** — `POST /alerts/{id}/resolve` + a Resolve button in the dashboard.
3. **Login rate limiting** — 5 failed attempts within 15 minutes locks that email out for 15 minutes (`login_attempts` table, enforced in `auth_routes.py`).
4. **Account recovery** — 10 one-time backup codes are issued when MFA is enabled (`POST /auth/mfa/enable`) and can be regenerated (`POST /auth/mfa/backup-codes/regenerate`); a backup code works in place of a TOTP code at login and logs a warning event when used.
5. **Dual-approval for sensitive directives** — `DirectiveIn.sensitive: bool`; a sensitive directive sits in `pending_approval` until a *different* user calls `POST /directives/{id}/approve` — self-approval is rejected.
6. **`.env.example`** — every variable the app reads, flagged by whether it matters before a real deploy.

Plus the two smaller ones: `/directives` and `/events` now take `limit`/`offset` for pagination, and `GET /metrics` gives commander/integrator roles a basic operational summary (uptime, active alerts, pending approvals, 24h directive/event counts, locked-out accounts). `/metrics` is deliberately simple JSON, not a Prometheus exporter — worth upgrading if real monitoring tooling gets wired up later.

## What's real vs. what's a stub

- **Core platform (auth, RBAC, JWT+MFA, Tasking engine, event timeline, alerting)** — fully implemented, no stubs.
- **MERCURY / VECTOR adapters** — the adapter code is real and will talk to the actual systems the moment `MERCURY_API_URL`/`MERCURY_API_KEY` (and the VECTOR equivalents) are set as environment variables, pointed at each system's own service-API endpoint. Until then, they degrade gracefully: demo data if never configured, cached last-known-good data if configured but the live call fails.
- **Defense/ISR, Emergency, IT/Infra domains** — present in the data model and RBAC (a user can be scoped to them) but carry zero adapters — this is intentional, matching the phased rollout (Phase 2 = IT/Infra, Phase 3 = Defense/ISR, Phase 4 = Emergency, native build).
- **Field-level encryption at rest** — not implemented. Flagged honestly in `SECURITY.md` rather than faked with a hand-rolled cipher; needs the `cryptography` package, which this build environment couldn't install (no package-registry access in this sandbox — see Verification note).

## Verification note

This build environment's network egress does not currently allow
`pip install` from PyPI (`pypi.org` is not in the allowlist here), so the
app could not be run live end-to-end in this sandbox — the same
situation as the tax-filing app build. Verification here was:

- Every module compiles cleanly (`python3 -m py_compile`, all green).
- `sbom.json` is valid JSON.
- Manual trace of the request flow (login → JWT → RBAC check → adapter call → cache write/read → directive logging → event timeline) against the code as written.

Once this runs somewhere with registry access (e.g. `pip install -r
requirements.txt` on Railway, which is what `railway.toml` targets),
run `tests/test_smoke.py` to confirm end-to-end before treating it as
verified live.

## Bootstrapping a first login

On first startup with an empty `users` table, the app creates one
`commander` account automatically (see `bootstrap_admin_if_empty` in
`auth.py`). Set `OLYMPUS_ADMIN_EMAIL` / `OLYMPUS_ADMIN_PASSWORD` as
environment variables before first boot, or read the generated password
out of the startup logs if you don't. That account still needs
`/auth/mfa/setup` + `/auth/mfa/enable` before it can log in, since
commander is an MFA-required role — this is deliberate, not a bug.

## Suggested next steps

1. Deploy to Railway (own repo, matching ecosystem convention) and confirm `tests/test_smoke.py` passes against the live instance.
2. Point `MERCURY_API_URL`/`MERCURY_API_KEY` and `VECTOR_API_URL`/`VECTOR_API_KEY` at the real services to move Logistics from demo to live data.
3. Decide the SQLite → Postgres trigger before real usage, per the design doc.
4. When ready for Phase 2 (IT/Infra), reuse the exact same adapter interface (`adapters/base.py`) for ZEUS/NOC/MDM/IAM.
