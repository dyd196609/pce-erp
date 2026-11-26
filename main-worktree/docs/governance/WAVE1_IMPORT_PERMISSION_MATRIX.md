# Wave 1 Import Permission Matrix

| Actor | Read | Template | Preview | Commit |
|---|---|---|---|---|
| Anonymous | DENY | DENY | DENY | DENY |
| Isolated read-only user | ALLOW | ALLOW | ALLOW through `production.master_data.view` | DENY by entity maintain permission |
| Isolated authorized import user | ALLOW | ALLOW | ALLOW | ALLOW through existing entity maintain permission and formal execution chain |

Template/preview are non-write validation actions and use `AuthorizationService` with `production.master_data.view`. Commit does not invent an import super-permission: every CREATE is authorized by `ProductionFoundationService.write` using the existing entity maintain permission. A valid employee → position → responsibility chain remains mandatory.

Isolated runtime result: read-only preview ALLOW; read-only commit HTTP 403; zero denied-row writes. No Production user, role, permission or session was modified.

`PERMISSION SEPARATION = PASS`
