# OLYMPUS Communications Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved OLYMPUS Communications Layer for national-scale SMS, email, automated voice, inbound/outbound live operator calling, multilingual campaigns, resilient provider dispatch, and auditable nationwide authorization.

**Architecture:** OLYMPUS remains the command/authorization plane while a focused `communications/` package owns campaign state, audiences, language variants, dispatch batches, provider adapters, voice sessions, receipts, and audit events. Durable channel queues are represented by database-backed dispatch batches first, with provider-neutral adapters so external SMS/email/voice providers can be attached without changing campaign logic; production throughput remains provider/deployment dependent.

**Tech Stack:** Python 3.10+, FastAPI 0.115.0, stdlib sqlite3/crypto primitives, requests 2.32.3, pytest/FastAPI TestClient, provider-neutral HTTP adapters.

**Spec:** `docs/superpowers/specs/2026-09-14-olympus-communications-layer-design.md`

## Global Constraints

- Support SMS, email, automated voice broadcasts, outbound live operator calls, inbound callbacks, and multilingual delivery.
- OLYMPUS stores campaign/audience identifiers and aggregate results; communications-specific recipient/contact state belongs to the Communications Service boundary.
- Nationwide broadcasts require two different authenticated authorized approvers.
- Approved content is immutable; changing content creates a new version and invalidates prior approval.
- SMS, email, and voice have separate queues/capacity controls.
- Every intended delivery has a stable idempotency key.
- Failover may reroute only unsent or confirmed-failed work; ambiguous outcomes are reconciled before retry where possible.
- Emergency stop prevents workers from claiming additional unsent batches while preserving reconciliation records.
- Sensitive contact information must be encrypted at rest before production recipient data is accepted.
- No fixed messages-per-second capacity claim is permitted until measured against actual deployment and contracted provider limits.
- Existing OLYMPUS weapon/engagement safety boundary remains unchanged.

---

## File structure

- `communications/__init__.py` — package boundary.
- `communications/db.py` — separate communications database connection/schema.
- `communications/models.py` — lifecycle/channel constants and validation helpers.
- `communications/audiences.py` — recipient/contact/language/suppression operations.
- `communications/campaigns.py` — campaign/version/approval lifecycle.
- `communications/dispatch.py` — batching, idempotency, queue claiming, pause/stop semantics.
- `communications/providers/base.py` — provider-neutral result/interface types.
- `communications/providers/mock.py` — deterministic test provider.
- `communications/providers/router.py` — health/circuit/failover selection.
- `communications/voice.py` — automated/live inbound/outbound call-session state.
- `communications/webhooks.py` — signed provider receipt verification/reconciliation.
- `communications/audit.py` — append-only communications audit events.
- `communications/routes.py` — OLYMPUS-facing FastAPI gateway.
- `communications/worker.py` — one bounded dispatch-worker iteration suitable for horizontal workers.
- `main.py` — mount communications router/startup initialization.
- `.env.example` — communications DB, encryption, webhook, provider configuration names.
- `tests/test_communications_*.py` — focused TDD suites.

---

### Task 1: Communications database boundary and campaign lifecycle

**Files:**
- Create: `communications/__init__.py`
- Create: `communications/db.py`
- Create: `communications/models.py`
- Create: `communications/campaigns.py`
- Test: `tests/test_communications_campaigns.py`

**Interfaces:**
- Produces: `get_comm_db()`, `init_comm_db()`, `create_campaign(...) -> dict`, `add_variant(...) -> dict`, `submit_for_approval(...) -> dict`, `approve_campaign(...) -> dict`, `get_campaign(campaign_id: str) -> dict`.
- Campaign states: `draft`, `audience_validation`, `translation`, `approval`, `ready`, `sending`, `completed`, `partially_failed`, `paused`, `cancelled`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
from communications.campaigns import create_campaign, add_variant, approve_campaign, get_campaign


def test_nationwide_campaign_needs_two_distinct_approvers(comm_db):
    campaign = create_campaign(comm_db, title="Flood warning", scope="nationwide", created_by="author@ung")
    add_variant(comm_db, campaign["id"], "en", sms="Flood warning", email="Flood warning", voice="Flood warning")
    approve_campaign(comm_db, campaign["id"], "approver1@ung")
    assert get_campaign(comm_db, campaign["id"])["status"] == "approval"
    approve_campaign(comm_db, campaign["id"], "approver2@ung")
    assert get_campaign(comm_db, campaign["id"])["status"] == "ready"


def test_approver_cannot_approve_twice(comm_db):
    campaign = create_campaign(comm_db, title="Test", scope="nationwide", created_by="author@ung")
    add_variant(comm_db, campaign["id"], "en", sms="x", email="x", voice="x")
    approve_campaign(comm_db, campaign["id"], "approver1@ung")
    try:
        approve_campaign(comm_db, campaign["id"], "approver1@ung")
        assert False, "duplicate approval accepted"
    except ValueError as exc:
        assert "distinct" in str(exc).lower()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_campaigns.py -v`
Expected: FAIL because `communications.campaigns` does not exist.

- [ ] **Step 3: Implement minimal schema/lifecycle**

Create a separate SQLite schema with `campaigns`, `message_variants`, and `campaign_approvals`; use UUID campaign IDs, unique `(campaign_id, approver_email)`, and transition nationwide campaigns to `ready` only after two distinct approvals.

```python
CAMPAIGN_STATES = {"draft", "audience_validation", "translation", "approval", "ready", "sending", "completed", "partially_failed", "paused", "cancelled"}
CHANNELS = {"sms", "email", "voice"}

def approval_threshold(scope: str) -> int:
    return 2 if scope == "nationwide" else 1
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_campaigns.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications tests/test_communications_campaigns.py
git commit -m "feat: add communications campaign lifecycle"
```

### Task 2: Audience, language preference, suppression, and encrypted contact storage

**Files:**
- Create: `communications/audiences.py`
- Modify: `communications/db.py`
- Test: `tests/test_communications_audiences.py`

**Interfaces:**
- Produces: `create_audience(conn, name) -> str`, `add_recipient(conn, audience_id, external_id, phone, email, language) -> str`, `resolve_recipients(conn, audience_id, language_override=None) -> list[dict]`, `suppress_contact(conn, recipient_id, channel) -> None`.

- [ ] **Step 1: Write failing audience tests**

```python
def test_language_preference_and_override(comm_db):
    aid = create_audience(comm_db, "Central")
    add_recipient(comm_db, aid, "citizen-1", "+256700000001", "a@example.test", "lg")
    assert resolve_recipients(comm_db, aid)[0]["language"] == "lg"
    assert resolve_recipients(comm_db, aid, language_override="en")[0]["language"] == "en"


def test_suppressed_sms_is_not_dispatchable(comm_db):
    aid = create_audience(comm_db, "Test")
    rid = add_recipient(comm_db, aid, "r1", "+256700000002", None, "en")
    suppress_contact(comm_db, rid, "sms")
    recipient = resolve_recipients(comm_db, aid)[0]
    assert "sms" in recipient["suppressed_channels"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_audiences.py -v`
Expected: FAIL on missing audience APIs.

- [ ] **Step 3: Implement encrypted contacts and audience resolution**

Use an authenticated encryption provider behind `encrypt_contact(str)->str` / `decrypt_contact(str)->str`; require `OLYMPUS_COMM_CONTACT_KEY` outside test mode and never log plaintext contact values. Store `external_id`, encrypted phone/email, language, audience membership, and channel suppression separately.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_audiences.py -v`
Expected: PASS and database rows do not contain the plaintext phone/email.

- [ ] **Step 5: Commit**

```bash
git add communications/audiences.py communications/db.py tests/test_communications_audiences.py
git commit -m "feat: add encrypted communications audiences"
```

### Task 3: Immutable multilingual message versions

**Files:**
- Modify: `communications/campaigns.py`
- Test: `tests/test_communications_languages.py`

**Interfaces:**
- Produces: `revise_campaign_content(conn, campaign_id, variants, actor) -> dict`, `select_variant(conn, campaign_id, language, fallback="en") -> dict`.

- [ ] **Step 1: Write failing version tests**

```python
def test_edit_after_approval_creates_new_version_and_clears_approvals(comm_db, ready_campaign):
    before = get_campaign(comm_db, ready_campaign["id"])
    revised = revise_campaign_content(comm_db, before["id"], {"en": {"sms": "Updated", "email": "Updated", "voice": "Updated"}}, "author@ung")
    assert revised["version"] == before["version"] + 1
    assert revised["status"] == "approval"
    assert revised["approval_count"] == 0
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_languages.py -v`
Expected: FAIL because revision/version API is absent.

- [ ] **Step 3: Implement immutable versioning**

Never update an approved `message_variants` row in place. Insert the next campaign version, copy/replace supplied language variants, invalidate approvals for the new version, and retain old variants for audit.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_languages.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/campaigns.py tests/test_communications_languages.py
git commit -m "feat: version multilingual campaign content"
```

### Task 4: Durable per-channel batching, idempotency, and emergency stop

**Files:**
- Create: `communications/dispatch.py`
- Modify: `communications/db.py`
- Test: `tests/test_communications_dispatch.py`

**Interfaces:**
- Produces: `materialize_dispatch(conn, campaign_id, audience_id, channels, batch_size=1000) -> dict`, `claim_batch(conn, channel, worker_id) -> dict | None`, `record_delivery(...)`, `pause_campaign(...)`, `resume_campaign(...)`, `emergency_stop(conn, actor)`, `clear_emergency_stop(conn, actor)`.

- [ ] **Step 1: Write failing dispatch tests**

```python
def test_idempotency_survives_rematerialization(comm_db, ready_campaign_with_audience):
    first = materialize_dispatch(comm_db, ready_campaign_with_audience["campaign_id"], ready_campaign_with_audience["audience_id"], ["sms", "email"])
    second = materialize_dispatch(comm_db, ready_campaign_with_audience["campaign_id"], ready_campaign_with_audience["audience_id"], ["sms", "email"])
    assert second["delivery_count"] == first["delivery_count"]


def test_emergency_stop_blocks_new_claims(comm_db, queued_campaign):
    emergency_stop(comm_db, "commander@ung")
    assert claim_batch(comm_db, "sms", "worker-1") is None
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_dispatch.py -v`
Expected: FAIL on missing dispatch module.

- [ ] **Step 3: Implement durable queue records**

Create `dispatch_batches` and `delivery_attempts`. Derive idempotency as SHA-256 of `campaign_id:version:recipient_id:channel`. Enforce a UNIQUE constraint on that key. Claim batches transactionally and never claim when global emergency stop or campaign pause is active.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/dispatch.py communications/db.py tests/test_communications_dispatch.py
git commit -m "feat: add durable communications dispatch"
```

### Task 5: Provider abstraction, health circuit, and safe failover

**Files:**
- Create: `communications/providers/__init__.py`
- Create: `communications/providers/base.py`
- Create: `communications/providers/mock.py`
- Create: `communications/providers/router.py`
- Test: `tests/test_communications_providers.py`

**Interfaces:**
- Produces: `DeliveryRequest`, `DeliveryResult`, `Provider.send(request)`, `ProviderRouter.send(request)`, `ProviderRouter.mark_health(name, healthy)`.
- `DeliveryResult.status` is one of `accepted`, `delivered`, `confirmed_failed`, `ambiguous`.

- [ ] **Step 1: Write failing failover tests**

```python
def test_confirmed_failure_can_fail_over():
    primary = MockProvider("p1", result="confirmed_failed")
    secondary = MockProvider("p2", result="accepted")
    result = ProviderRouter([primary, secondary]).send(sample_request())
    assert result.provider == "p2"


def test_ambiguous_result_does_not_blindly_fail_over():
    primary = MockProvider("p1", result="ambiguous")
    secondary = MockProvider("p2", result="accepted")
    result = ProviderRouter([primary, secondary]).send(sample_request())
    assert result.provider == "p1"
    assert secondary.calls == 0
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_providers.py -v`
Expected: FAIL because provider interfaces do not exist.

- [ ] **Step 3: Implement provider-neutral routing**

Use small dataclasses for requests/results. Skip unhealthy/open-circuit providers; try a secondary only for pre-send/unavailable or `confirmed_failed` outcomes. Return `ambiguous` without automatic resend.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_providers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/providers tests/test_communications_providers.py
git commit -m "feat: add communications provider routing"
```

### Task 6: Signed receipts and delivery reconciliation

**Files:**
- Create: `communications/webhooks.py`
- Modify: `communications/db.py`
- Test: `tests/test_communications_webhooks.py`

**Interfaces:**
- Produces: `verify_webhook(body: bytes, signature: str, secret: str) -> bool`, `reconcile_receipt(conn, provider, provider_message_id, status, raw_receipt) -> dict`.

- [ ] **Step 1: Write failing webhook tests**

```python
def test_invalid_webhook_signature_is_rejected():
    assert verify_webhook(b'{"id":"1"}', "bad", "secret") is False


def test_duplicate_receipt_is_idempotent(comm_db, accepted_delivery):
    first = reconcile_receipt(comm_db, "mock", accepted_delivery["provider_message_id"], "delivered", {"id": "r1"})
    second = reconcile_receipt(comm_db, "mock", accepted_delivery["provider_message_id"], "delivered", {"id": "r1"})
    assert first["delivery_id"] == second["delivery_id"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_webhooks.py -v`
Expected: FAIL on missing webhook module.

- [ ] **Step 3: Implement HMAC verification and receipt uniqueness**

Use `hmac.compare_digest` over an HMAC-SHA256 body signature. Store provider receipt identifiers uniquely and reconcile state monotonically so duplicate callbacks cannot create duplicate delivery attempts.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_webhooks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/webhooks.py communications/db.py tests/test_communications_webhooks.py
git commit -m "feat: reconcile signed delivery receipts"
```

### Task 7: Automated voice and two-way operator call sessions

**Files:**
- Create: `communications/voice.py`
- Modify: `communications/db.py`
- Test: `tests/test_communications_voice.py`

**Interfaces:**
- Produces: `create_automated_call(...)`, `create_outbound_operator_call(...)`, `register_inbound_callback(...)`, `assign_operator(...)`, `complete_call(...)`, `list_waiting_callbacks(...)`.

- [ ] **Step 1: Write failing voice tests**

```python
def test_inbound_callback_can_be_assigned_to_operator(comm_db):
    call = register_inbound_callback(comm_db, provider_call_id="c1", caller_ref="recipient-1", campaign_id="cmp1", language="lg")
    assigned = assign_operator(comm_db, call["id"], "operator@ung")
    assert assigned["direction"] == "inbound"
    assert assigned["operator_email"] == "operator@ung"
    assert assigned["status"] == "active"


def test_outbound_operator_call_uses_approved_campaign_version(comm_db, ready_campaign):
    call = create_outbound_operator_call(comm_db, ready_campaign["id"], "recipient-1", "operator@ung", "en")
    assert call["campaign_version"] == ready_campaign["version"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_voice.py -v`
Expected: FAIL because voice session APIs do not exist.

- [ ] **Step 3: Implement call-session state**

Store direction (`automated_outbound`, `operator_outbound`, `inbound`), campaign/version, language, operator, provider call ID, timestamps, status, and disposition. Reject operator outbound calls against unapproved campaign versions.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_voice.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/voice.py communications/db.py tests/test_communications_voice.py
git commit -m "feat: add two-way communications voice center"
```

### Task 8: Append-only audit and privileged API gateway

**Files:**
- Create: `communications/audit.py`
- Create: `communications/routes.py`
- Modify: `main.py`
- Test: `tests/test_communications_routes.py`

**Interfaces:**
- Produces FastAPI routes under `/api/communications`: campaigns, variants, audience estimate, approval, schedule, pause, resume, cancel, emergency-stop, status, voice callbacks/operator sessions.
- Consumes existing `CurrentUser`, `get_current_user`, `require_role` from `auth.py`.

- [ ] **Step 1: Write failing authorization tests**

```python
def test_analyst_cannot_release_nationwide_campaign(client, analyst_token, nationwide_campaign_id):
    response = client.post(f"/api/communications/campaigns/{nationwide_campaign_id}/approve", headers={"Authorization": f"Bearer {analyst_token}"})
    assert response.status_code == 403


def test_commander_action_creates_audit_event(client, commander_token, comm_db):
    response = client.post("/api/communications/emergency-stop", headers={"Authorization": f"Bearer {commander_token}"})
    assert response.status_code == 200
    row = comm_db.execute("SELECT action FROM comm_audit_events ORDER BY id DESC LIMIT 1").fetchone()
    assert row["action"] == "emergency_stop"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_routes.py -v`
Expected: FAIL because communications router is absent.

- [ ] **Step 3: Implement gateway and audit**

Mount `communications.routes.router` in `main.py`. Require authenticated OLYMPUS users on all gateway routes; restrict approvals, emergency stop, scheduling, and nationwide release to commander/domain-controller policy defined in the route dependency. Audit actor, action, object ID, timestamp, and JSON detail with INSERT-only application APIs.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/audit.py communications/routes.py main.py tests/test_communications_routes.py
git commit -m "feat: expose audited communications gateway"
```

### Task 9: Worker iteration, priority, back-pressure, and recovery

**Files:**
- Create: `communications/worker.py`
- Modify: `communications/dispatch.py`
- Test: `tests/test_communications_worker.py`

**Interfaces:**
- Produces: `run_once(conn, channel, worker_id, router, limit=100) -> dict` and lease recovery `requeue_expired_claims(conn, now) -> int`.

- [ ] **Step 1: Write failing worker tests**

```python
def test_emergency_priority_claimed_before_routine(comm_db, queued_priority_campaigns):
    batch = claim_batch(comm_db, "sms", "worker-1")
    assert batch["priority"] == "emergency"


def test_expired_worker_lease_is_recoverable(comm_db, expired_claim):
    assert requeue_expired_claims(comm_db, expired_claim["expired_at"] + 1) == 1
    assert claim_batch(comm_db, expired_claim["channel"], "worker-2")["id"] == expired_claim["batch_id"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_worker.py -v`
Expected: FAIL on missing worker/recovery behavior.

- [ ] **Step 3: Implement bounded worker iteration**

Claim by priority then creation time, use finite leases, process at most `limit`, persist every provider result, and stop claiming when emergency stop/campaign pause/provider back-pressure is active. Do not spin an unmanaged background thread from FastAPI startup; deploy workers independently/horizontally.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_worker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/worker.py communications/dispatch.py tests/test_communications_worker.py
git commit -m "feat: add recoverable communications workers"
```

### Task 10: Aggregate monitoring and million-recipient load simulation

**Files:**
- Create: `communications/monitoring.py`
- Test: `tests/test_communications_monitoring.py`
- Test: `tests/test_communications_scale.py`

**Interfaces:**
- Produces: `campaign_status(conn, campaign_id) -> dict`, `provider_health(router) -> list[dict]`, `voice_center_status(conn) -> dict`.

- [ ] **Step 1: Write failing monitoring and scale tests**

```python
def test_campaign_status_reports_channel_totals(comm_db, mixed_delivery_campaign):
    status = campaign_status(comm_db, mixed_delivery_campaign)
    assert status["sms"]["delivered"] == 2
    assert status["email"]["failed"] == 1
    assert "pending" in status["voice"]


def test_million_recipient_plan_is_batched_not_materialized_in_memory(fake_audience_count):
    plan = plan_batches(recipient_count=1_000_000, channels=["sms", "email", "voice"], batch_size=1000)
    assert plan["batches_per_channel"] == 1000
    assert plan["total_batches"] == 3000
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_monitoring.py tests/test_communications_scale.py -v`
Expected: FAIL because monitoring/scale planning APIs are absent.

- [ ] **Step 3: Implement SQL aggregate monitoring and arithmetic batch planning**

Aggregate counts in SQL rather than loading delivery rows into Python. `plan_batches()` computes counts mathematically and must not construct one million recipient objects. Do not encode an unmeasured throughput claim.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_communications_monitoring.py tests/test_communications_scale.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add communications/monitoring.py tests/test_communications_monitoring.py tests/test_communications_scale.py
git commit -m "feat: add communications monitoring and scale tests"
```

### Task 11: Configuration, full regression, and acceptance evidence

**Files:**
- Modify: `.env.example`
- Modify: `HANDOFF.md`
- Modify: `SECURITY.md`
- Modify: `requirements.txt` only if the authenticated-encryption implementation selected in Task 2 requires a reviewed dependency.
- Test: all `tests/test_communications_*.py` plus existing `tests/test_smoke.py`.

**Interfaces:**
- Produces documented environment names for communications DB path, contact encryption key, webhook secrets, and provider adapter configuration.

- [ ] **Step 1: Add configuration/security regression assertions**

```python
def test_production_contact_key_is_required(monkeypatch):
    monkeypatch.setenv("OLYMPUS_ENV", "production")
    monkeypatch.delenv("OLYMPUS_COMM_CONTACT_KEY", raising=False)
    with pytest.raises(RuntimeError):
        validate_communications_config()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_communications_config.py -v`
Expected: FAIL until production configuration validation exists.

- [ ] **Step 3: Implement config validation and document deployment boundary**

Document that API processes and dispatch workers are separate deployable processes sharing communications storage/queue infrastructure; production contact encryption key and webhook secrets are mandatory; provider credentials are environment secrets and never committed.

- [ ] **Step 4: Run complete verification**

Run:

```bash
python -m pytest -q
python -m py_compile main.py communications/*.py communications/providers/*.py
```

Expected: all existing OLYMPUS smoke tests and all communications tests PASS; compilation exits 0.

- [ ] **Step 5: Commit**

```bash
git add .env.example HANDOFF.md SECURITY.md requirements.txt communications tests
git commit -m "docs: finalize OLYMPUS communications deployment contract"
```

## Self-review

- Spec coverage: campaign lifecycle, multilingual variants, audience/contact boundary, suppression, separate channel dispatch, idempotency, provider failover, ambiguous-result handling, signed receipts, automated voice, inbound/outbound operators, two-person approval, audit, emergency stop, priority, back-pressure, worker recovery, aggregate monitoring, and million-recipient batching are each assigned to a task.
- Security coverage: production encryption-key validation, RBAC/MFA reuse, webhook authentication, immutable audit/application APIs, and secret configuration are explicit.
- Scale claim: the plan tests million-recipient batching behavior but intentionally does not claim a fixed messages-per-second rate.
- Type/interface consistency: campaign IDs are strings; versions are integers; delivery statuses are `accepted|delivered|confirmed_failed|ambiguous`; channel names are `sms|email|voice` throughout.
- No provider vendor is hard-coded into campaign logic; concrete production adapters can be added behind the provider interface after provider accounts/contracts are selected.
