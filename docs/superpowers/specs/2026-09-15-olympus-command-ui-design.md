# OLYMPUS Command UI Design

## Goal
Build a professional National Operations Command interface on the existing UNG-OLYMPUS FastAPI backend, exposing real OLYMPUS capabilities rather than a disconnected mock dashboard.

## Approved experience
The authenticated application opens into an executive command overview with a persistent left navigation rail and operational-status header. Primary workspaces are Command Overview, Common Operating Picture, Incidents & Alerts, Operational Coordination, Communications, Resources & Assets, Inter-System Feeds, Reports & Audit, and Administration.

## Command Overview
The landing workspace provides national operational status, a central situational-awareness map/COP, priority incident queue, system connectivity/health, active operations, and recent activity. The layout is dense enough for command use while remaining readable on laptops and iPads.

## Security and roles
Existing OLYMPUS authentication remains authoritative. The UI must not invent client-side authorization. Administrative navigation and controls are rendered only when server-provided role/capability data permits them. Operators receive operational functions without privileged administration controls.

## Integration
The UI is served by the same FastAPI application. It consumes existing OLYMPUS authentication, alerts, COP, communications, adapters, and database-backed capabilities through same-origin endpoints. Where an existing backend capability is not yet exposed through a suitable endpoint, a narrow API adapter may be added rather than duplicating business logic in the frontend.

## Responsive behavior
Desktop is the primary command-center layout. Tablet/iPad retains all operational functions with collapsible navigation and reflowed panels. Small screens use stacked panels and preserve incident acknowledgement and essential situational awareness.

## Visual language
Professional command-center presentation: dark operational workspace, high-contrast typography, restrained status colors, compact information cards, clear severity/state indicators, and map-first situational awareness. Avoid decorative effects that interfere with operational readability.

## Error handling
API failures display explicit degraded/unavailable states rather than fabricated data. Empty states distinguish no records from connection failure. Authentication expiry returns the user to the secure login flow.

## Testing
Add route/render smoke coverage, authentication/authorization coverage for privileged UI elements, and API contract tests for dashboard data. Existing OLYMPUS smoke and communications tests remain part of the release gate. The current CI import-path failure must be corrected as part of making the integrated application deployable.

## Deployment
The completed application is deployed as one OLYMPUS service. A live URL is only reported after the service starts successfully and the actual UI route responds.