# Enterprise OS UI Model

## V1.1 UI Redesign

The product UI is now organized as an enterprise operating system. The entry model is based on organization, business process, and role-based work instead of traditional ERP modules.

## Primary Navigation

```text
/Enterprise OS
  /dashboard
  /organization
  /process-center
  /work-center
  /analytics
  /admin
```

## Deprecated Independent Module Homes

These are no longer independent menus or home pages:

- CRM
- SCM
- Finance
- Inventory

They are mapped to Process Center nodes:

| Legacy Module | Enterprise OS Process Node |
| --- | --- |
| CRM | Plan |
| SCM | Purchase |
| Inventory | Warehouse |
| Finance | Finance |

## Runtime Flags

```json
{
  "enterpriseOSMode": "ON",
  "moduleUI": "DISABLED",
  "processUI": "ACTIVE",
  "organizationUI": "ACTIVE"
}
```

## Validation Rules

- CRM, SCM, Finance, and Inventory do not appear as independent navigation entries.
- Business work starts from Process Center.
- Work Center presents task queues by role.
- Organization binds departments, roles, and users to process ownership.
- Dashboard reflects enterprise-level health, KPI, capacity, cost, and risk.
