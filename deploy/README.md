# ProfitOS SaaS Deployment Boundary

This directory defines the productized service boundaries for ProfitOS:

- frontend
- backend-api
- kernel-service
- agent-service
- business-service
- nginx

The current implementation runs in the frontend meta runtime. These folders mark the deployment-ready split for the SaaS architecture.

## Supported Environments

Environment profiles are defined in `environments.yml`.

- dev environment: local development, debug hooks enabled, standard API envelope enforced.
- staging environment: frozen runtime, limited diagnostics, production rehearsal.
- production environment: frozen runtime, debug hooks disabled, enterprise SaaS release target.

## API First Entry

```text
POST /api/profitos/run
```

Request shape:

```json
{
  "tenantId": "company_a",
  "role": "manager",
  "action": "EXECUTE",
  "input": "优化采购系统",
  "context": {
    "load": "high"
  }
}
```

Runtime adapter:

```js
window.__TRACE__.profitOS.request(req)
```

## Architecture Freeze

The production architecture is frozen in:

- `PROFITOS_PRODUCTION_ARCHITECTURE_V1.md`
- `ARCHITECTURE_LOCK.md`

Final ownership model:

- ProfitOS = Decision Layer
- PalmCloud = Execution Layer
- ERP / MES / SCM / WMS = PalmCloud execution modules

Approved API namespaces:

- `/api/core/*`
- `/api/profit/*`
- `/api/execution/*`
