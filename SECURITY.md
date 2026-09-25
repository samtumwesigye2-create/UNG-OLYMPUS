# UNG-OLYMPUS — Security & Compliance Posture

This documents how Phase 1 maps onto the Zero Trust / NIST 800-53-style
requirements requested for the platform, what's actually implemented in
code today, and what's explicitly out of scope for a software project.

Scope note: OLYMPUS coordinates situational-awareness and logistics/IT
data across domains — it is not, and will not be built as, fire-control
or weapons-targeting software. Nothing below should be read as covering
that; see HANDOFF.md for the boundary as discussed with the requester.

## 1. Zero Trust Architecture

| Requirement | Status | Notes |
|---|---|---|
| Continuous MFA for privileged roles | **Built** | TOTP required for `commander`/`domain_controller` at login (`auth.py`, `auth_routes.py`) |
| Short-lived, role-scoped sessions | **Built** | JWTs expire in 2h (commander) / 4h (domain controller) / 8h (analyst, integrator) — `JWT_TTL_BY_ROLE` |
| Dynamic identity risk scoring | **Not built** | Needs behavioral/anomaly baselining (failed-login velocity, impossible-travel, device fingerprint drift) — a Phase 2+ addition once there's real login history to model against |
| Microsegmentation | **Built** | Every request is scoped by domain (`CurrentUser.can_see`/`can_task`) — an Analyst credential for Logistics has no path to Defense/IT-Infra data even if the token is stolen. Each subsystem adapter uses its own service API key, never a shared credential, so one leaked key exposes exactly one subsystem |
| Comply-to-connect (device health) | **Not built** | Requires endpoint/device posture management — naturally belongs to the IT/Infra domain's MDM integration (Phase 2), not something the web app itself can enforce |
| Data-centric tagging / encryption at rest & in transit (NSA-grade crypto) | **Partial** | In transit: HTTPS (enforced at the Railway/reverse-proxy layer). At rest: **not implemented** — this sandbox has no network access to install a vetted crypto library (`cryptography`/`pynacl`), and a hand-rolled cipher would be worse than none. Field-level encryption (same pattern as DRACO's identity protection and the tax app's TIN/SSN fields) should be added once a real crypto dependency can be installed — flagged, not faked |

## 2. Tactical/OT-style protections (reinterpreted for a coordination platform)

| Requirement | Status | Notes |
|---|---|---|
| Never write to a subsystem directly (IT/OT boundary) | **Built** | The Tasking & Directives engine is the *only* write path; every adapter call is logged with accept/reject status (`tasking.py`) |
| Fight-through / degraded operations | **Built** | Each adapter caches its last known-good live reading (`subsystem_cache` table). If the live link drops, OLYMPUS serves that cached data labeled `source: cached` with a staleness timestamp, instead of silently falling back to demo data |
| Hardware shielding (EMP/TEMPEST) | **Out of scope** | Physical facility/hardware engineering — not a software concern |

## 3. Supply chain / software factory

| Requirement | Status | Notes |
|---|---|---|
| SBOM | **Partial** | `sbom.json` lists direct dependencies by hand (network access to run a real resolver was unavailable in this build environment). Regenerate with `cyclonedx-py` or `pip-audit --format=cyclonedx-json` for a full transitive tree as part of CI |
| Secure DevSecOps pipeline | **Not built** | This is a CI/CD and hosting-platform concern (accredited build sandboxes, signed artifacts) — recommend wiring GitHub Actions + Railway's build pipeline with dependency scanning once the repo exists |
| Hardware supply chain attestation | **Out of scope** | Applies to physical hardware procurement, not this codebase |

## 4. Regulatory framing (NIST SP 800-53 control families, informally mapped)

| Family | How OLYMPUS addresses it today |
|---|---|
| **AC** (Access Control) | Role + domain-scoped RBAC on every endpoint (`auth.py`) |
| **IA** (Identification & Authentication) | PBKDF2 password hashing, TOTP MFA for elevated roles |
| **SC** (System & Communications Protection) | HTTPS transport, JWT-signed sessions, per-subsystem API keys |
| **AU** (Audit & Accountability) | The append-only `events` table — every login, alert, directive, and acknowledgment, immutable and attributable |
| **IR** (Incident Response) | The alerting/correlation engine (`alerts.py`) plus the event timeline give the raw material for an IR process; the *process* itself (who gets paged, runbooks) is organizational, not code |
| **CM** (Configuration Management) | `requirements.txt` pins exact versions; `sbom.json` tracks direct dependencies |

This is an informal mapping to guide the design, not a claim of NIST 800-53
compliance or an Authority to Operate — actual ATO/RMF authorization is a
government accreditation process that happens outside a codebase, run by
people with the authority to grant it.

## 5. Explicitly out of scope

Physical EMP/TEMPEST shielding, hardware chip attestation, jamming-resistant
RF/frequency-hopping design, Link 16-class tactical data link
implementation, and classified cross-domain security (CDS) guards between
classification levels are specialized, accredited engineering domains.
None of them are things this codebase attempts, and cross-domain guard
software in particular requires formal accreditation this project has no
path to obtain — OLYMPUS's domain/role scoping is a "need to know" access
control pattern, not a substitute for one.
