# Module Guide

## Standard Module Shape

Every deliverable module must resolve to this structure:

```json
{
  "moduleName": "purchase",
  "api": {},
  "ui": {},
  "workflow": {},
  "permissions": {},
  "dataModel": {}
}
```

## Field Responsibilities

| Field | Responsibility |
| --- | --- |
| `moduleName` | Stable product module identifier. |
| `api` | Endpoint contract, request format, response format, and error format. |
| `ui` | List/detail form structure, columns, actions, and schema-driven UI rules. |
| `workflow` | State field, states, transitions, workflow actions, and runtime isolation. |
| `permissions` | RBAC, tenant boundary, plan scope, action scope, and execution gates. |
| `dataModel` | Business fields, schema fields, model definition, and persistence contract. |

## Compatibility

The productized module standard keeps legacy contract fields such as `apiContract`, `uiContract`, `workflowContract`, and `permissionContract` for existing callers. New delivery-facing code should read the normalized fields listed above.

## Standardization Flow

1. Resolve the module name from `schema.api.module`, `schema.name`, or `schema.meta.module`.
2. Build API, UI, workflow, permissions, and tenant contracts.
3. Attach `dataModel` from `schema.dataModel`, `schema.model`, or `schema.fields`.
4. Mark the module as production ready.
5. Register it in the product delivery snapshot.

## Readiness Rules

- API strict mode must be enabled.
- Workflow runtime must be tenant scoped.
- Permissions must enforce tenant boundaries.
- Data model must be explicit or derived from schema fields.
- Production modules must hide experimental controls and debug panels.
