# Architecture

## Product Engineering Delivery Phase

The V17-V30 runtime is finalized as an enterprise SaaS product architecture. Experimental capabilities remain available behind frozen contracts, while the deliverable product surface is organized into four stable layers.

## Four-Layer Architecture

### 1. Core Product Layer

Owns enterprise product modules, domain schemas, UI contracts, permission contracts, and data models.

Included module families:

- purchase
- masterdata
- system
- profit
- dashboard

### 2. Workflow & Runtime Layer

Owns workflow execution, state machines, runtime kernel, event stream, and business execution.

Included module families:

- workflow
- runtime
- execution
- orchestration
- audit

### 3. SaaS Platform Layer

Owns tenant isolation, billing, onboarding, monitoring, deployment, and the API gateway.

Included module families:

- tenant
- billing
- deployment
- monitoring
- gateway

### 4. Ecosystem Layer

Owns marketplace, plugins, sandbox, partner integrations, governance, support, and revenue sharing.

Included module families:

- marketplace
- ecosystem
- pluginSandbox
- governance
- support

## Productization State

```json
{
  "productizationMode": "ACTIVE",
  "architectureFrozen": true,
  "deliveryReady": true
}
```

## Runtime Boundary

The `UIControlRuntimeKernel` exposes the delivery state and product delivery snapshot. This makes product readiness visible to runtime consumers, MetaPage dashboards, module catalogs, and deployment checks.

## Change Policy

- Product architecture is frozen.
- New modules must follow the standard module envelope.
- APIs must use the standard response envelope.
- Experimental engines must be hidden behind production contracts before release.
- Staging and production must run with frozen runtime behavior.
