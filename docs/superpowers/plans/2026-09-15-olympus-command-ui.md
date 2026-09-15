# OLYMPUS Command UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deployable, authenticated National Operations Command UI on the existing UNG-OLYMPUS FastAPI service.

**Architecture:** Serve a same-origin HTML/CSS/JavaScript command interface from FastAPI and bind it to existing OLYMPUS authentication, COP, alerts, communications, adapters, and persistence. Keep authorization server-authoritative and use narrow dashboard API adapters only where existing modules lack web-facing contracts.

**Tech Stack:** Python 3.12, FastAPI 0.115, Starlette, vanilla HTML/CSS/JavaScript, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-09-15-olympus-command-ui-design.md`

## Global Constraints
- Existing OLYMPUS authentication remains authoritative.
- Do not fabricate operational data when an API is unavailable.
- Administrative controls require server-provided authorization.
- Desktop command-center layout must remain usable on iPad/tablet and small screens.
- Existing smoke and communications tests remain release gates.
- Report a live URL only after the actual UI route responds successfully.

---

### Task 1: Restore deployable application entry point

**Files:**
- Create or modify: `main.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: importable `main.app: FastAPI`
- Consumes: existing routers/modules in the repository

- [ ] Write/confirm a failing smoke test that imports `from main import app` and requests the health/root application route.
- [ ] Run `pytest -q tests/test_smoke.py` and confirm the current `ModuleNotFoundError: No module named 'main'` failure.
- [ ] Implement the minimal FastAPI composition root, including existing routers without duplicating their business logic.
- [ ] Run `pytest -q tests/test_smoke.py` and confirm PASS.
- [ ] Commit with `fix: restore OLYMPUS application entry point`.

### Task 2: Add authenticated command-shell route

**Files:**
- Create: `static/index.html`
- Create: `static/olympus.css`
- Create: `static/olympus.js`
- Modify: `main.py`
- Create: `tests/test_command_ui.py`

**Interfaces:**
- Produces: `GET /` command shell and static assets
- Consumes: existing authentication/session contract

- [ ] Add failing tests asserting `/` serves the OLYMPUS shell, includes the approved primary navigation labels, and static assets resolve.
- [ ] Run `pytest -q tests/test_command_ui.py` and confirm RED.
- [ ] Implement semantic shell markup, responsive command-center styling, navigation, header, degraded/loading states, and same-origin JS bootstrap.
- [ ] Run `pytest -q tests/test_command_ui.py` and confirm GREEN.
- [ ] Commit with `feat: add OLYMPUS command center shell`.

### Task 3: Bind dashboard to real operational data

**Files:**
- Modify: `main.py` or create focused `dashboard_routes.py`
- Modify: `static/olympus.js`
- Modify: `static/index.html`
- Create: `tests/test_dashboard_api.py`

**Interfaces:**
- Produces: `GET /api/dashboard/summary` with explicit status, alerts, COP/activity, and integration health fields
- Consumes: existing `alerts.py`, `cop.py`, adapters, and database access

- [ ] Add failing API contract tests covering authenticated success, explicit empty data, and degraded dependency state.
- [ ] Run the focused tests and confirm RED.
- [ ] Implement a thin server adapter that reads existing OLYMPUS modules and never synthesizes unavailable records.
- [ ] Bind summary cards, priority queue, activity, system health, and COP workspace to the response.
- [ ] Run focused tests and confirm GREEN.
- [ ] Commit with `feat: connect OLYMPUS dashboard data`.

### Task 4: Enforce role-aware administration UI

**Files:**
- Modify: `static/olympus.js`
- Modify: `static/index.html`
- Modify: relevant auth/dashboard route only if capability metadata is absent
- Create: `tests/test_command_ui_authz.py`

**Interfaces:**
- Consumes: authenticated identity and server-provided role/capabilities
- Produces: privileged controls only for authorized users

- [ ] Add failing tests proving ordinary operators do not receive administrative capability and authorized administrators do.
- [ ] Run focused tests and confirm RED.
- [ ] Implement capability-aware rendering without relying on hidden buttons as the authorization boundary.
- [ ] Run focused tests and confirm GREEN.
- [ ] Commit with `feat: enforce OLYMPUS UI capabilities`.

### Task 5: Release verification

**Files:**
- Modify CI only if required to execute the established test suite correctly.

**Interfaces:**
- Release gate: smoke + command UI + communications campaign tests all pass.

- [ ] Run `pytest -q tests/test_smoke.py tests/test_command_ui.py tests/test_dashboard_api.py tests/test_command_ui_authz.py tests/test_communications_campaigns.py`.
- [ ] Correct only failures attributable to this integration and rerun until all tests pass.
- [ ] Confirm application startup with `main:app` and verify `/` plus `/health` locally/CI.
- [ ] Commit any release-gate correction with a focused message.
- [ ] Deploy the verified branch to an OLYMPUS service, generate its public domain, and verify the actual `/` UI route before reporting the URL.