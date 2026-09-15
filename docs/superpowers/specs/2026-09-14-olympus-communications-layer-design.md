# OLYMPUS Communications Layer — Design Specification

**System:** UNG-OLYMPUS — Operational Linkage, Yield Management, Planning & Unified Systems

**Status:** Approved design

## Purpose

Add a dedicated national-scale communications execution layer controlled by OLYMPUS. The layer supports SMS, email, automated voice broadcasts, outbound live operator calls, inbound callbacks, and multilingual delivery. It is designed to scale from individual communications to campaigns involving millions of recipients without placing provider-scale delivery workload or the national contact directory inside the OLYMPUS core.

## Architecture

OLYMPUS remains the command, authorization, planning, and aggregate-status plane. A dedicated Communications Service performs audience resolution, language selection, queueing, dispatch, provider integration, voice-center operations, delivery reconciliation, and communications-specific auditing.

Primary flow:

`OLYMPUS -> Communications Gateway -> Audience/Language Engine -> channel queues -> provider adapters -> recipients`

Delivery receipts and operational summaries flow back through the Communications Gateway to OLYMPUS.

## Components

### Communications Gateway

The authenticated boundary between OLYMPUS and the Communications Service. It exposes campaign creation, validation, audience estimation, approval, scheduling, pause/resume/cancel controls, emergency stop, and status retrieval.

### Audience Manager

Stores and resolves recipient groups, contact points, geographic/audience membership, language preferences, and applicable suppression/consent records. OLYMPUS normally references audiences by identifier rather than importing the complete contact directory.

### Language Engine

Maintains an approved master message and versioned multilingual variants. Recipient language is selected automatically from stored preferences, with an authorized campaign-level override. SMS, email, TTS/audio, and live-operator scripts derive from the same approved campaign version. Any content change after final approval invalidates approval and returns the campaign to review.

### Dispatch Engine

Partitions campaigns into independently recoverable batches and feeds separate durable queues for SMS, email, and automated voice. Horizontally scalable workers consume those queues subject to channel, provider, priority, throughput, quota, and spending controls.

### Provider Adapters

SMS, email, and voice use common internal provider interfaces. Multiple authorized providers may be configured for each channel. Routing can account for availability, destination, provider health, capacity, throughput, and cost. Circuit breakers isolate unhealthy providers. Failover only reroutes unsent or confirmed-failed work.

### Voice Center

Supports prerecorded and text-to-speech automated broadcasts, outbound live operator calls, and inbound callbacks. Authorized operators receive campaign context, the approved language-specific script, caller context permitted by role, and call-disposition controls. Operator actions and call sessions are audited.

### Delivery Monitor

Reconciles provider receipts and tracks queued, processing, delivered, failed, suppressed, retried, and pending work. It provides OLYMPUS aggregate campaign status, throughput, provider health, estimated completion, active voice calls, operator availability, and callback queue state.

## Campaign lifecycle

Campaigns progress through:

`Draft -> Audience Validation -> Translation -> Approval -> Scheduled/Ready -> Sending -> Completed/Partially Failed`

A nationwide broadcast requires two independently authenticated authorized approvers. Composing and nationwide authorization are separated by role. Final-approved campaign content is immutable; editing it creates a new version requiring approval again.

## Scale and queue behavior

OLYMPUS never attempts millions of synchronous sends. Campaign recipients are partitioned into controlled batches. SMS, email, and voice have separate queues and capacity controls so one channel cannot exhaust another. Priority classes allow authorized emergency communications to advance ahead of routine work without bypassing approval requirements.

Each intended delivery has a stable idempotency key. Worker restarts, retries, webhook duplication, and provider failover must not intentionally create duplicate delivery for work already confirmed successful. Back-pressure slows dispatch when provider or infrastructure capacity is reached instead of allowing queues or APIs to collapse.

No fixed messages-per-second capacity is claimed until measured against the actual deployment and contracted provider limits.

## Data model

The Communications Service owns communications-specific storage for Campaigns, Audiences, Recipients, Contact Points, Language Preferences, Message Variants, Approvals, Dispatch Batches, Delivery Attempts, Provider Receipts, Call Sessions, Operator Actions, Suppression/Consent Records, and Audit Events.

Sensitive contact information is encrypted at rest and access is role-scoped. OLYMPUS normally stores campaign/audience identifiers and aggregate operational results rather than duplicating the complete recipient directory.

## API boundary

OLYMPUS may create and validate campaigns, request audience estimates, submit content and language variants, request approval, schedule approved campaigns, pause/resume/cancel unsent work, trigger emergency stop, and retrieve campaign status.

Provider callbacks terminate at dedicated authenticated webhook endpoints. Voice Center APIs separately manage operator availability, inbound/outbound call sessions, approved scripts, and call disposition.

## Security and governance

The subsystem requires MFA and RBAC for privileged operations, service-to-service authentication, encrypted transport, encryption of sensitive stored data, verified provider webhooks, immutable audit records, rate controls, provider quotas, spending controls, and recipient suppression controls.

Nationwide broadcasts require two different authorized approvers. The emergency-stop control prevents workers from claiming additional unsent batches while preserving records needed to reconcile transactions already accepted by external providers.

The subsystem is for authorized communications and coordination. It does not alter OLYMPUS's existing safety boundary around weapon-target pairing, automated engagement prioritization, fire-control, sensor-to-shooter functionality, target development, threat neutralization, or direct weapon commands.

## Failure handling and degraded operation

Provider failures trip circuit breakers and stop new work from being assigned to the unhealthy adapter. Eligible unsent or confirmed-failed work can be rerouted to another configured provider. Ambiguous provider outcomes are reconciled before retry where possible to reduce duplicate delivery.

Worker crashes leave durable queue state recoverable. Retries use bounded policies and retain attempt history. A partial provider outage must not make the OLYMPUS core unavailable. Aggregate campaign state distinguishes pending, confirmed delivered, confirmed failed, suppressed, and unresolved deliveries.

## Testing

Implementation follows test-driven development. Coverage includes campaign lifecycle, RBAC/MFA authorization, two-person nationwide approval, language/version integrity, audience validation, idempotency and duplicate prevention, batching, worker recovery, provider circuit breaking/failover, webhook verification, SMS/email/automated voice dispatch, inbound and outbound live-operator calling, suppression handling, emergency stop, audit events, and load simulations representing millions of recipients.

Provider-specific integration tests use test/sandbox facilities where available. Production-scale throughput claims require measured acceptance testing against the actual deployment and provider contracts.

## Acceptance criteria

The feature is accepted when OLYMPUS can safely create and authorize a campaign; select recipient languages automatically with authorized override; distribute SMS, email, and automated voice through independently scalable queues; support inbound and outbound live operators; recover from worker/provider failures without uncontrolled duplicate dispatch; display aggregate delivery and provider status; halt unsent traffic through emergency stop; enforce two-person nationwide authorization; and retain a complete auditable record of campaign, approval, dispatch, provider, and operator actions.