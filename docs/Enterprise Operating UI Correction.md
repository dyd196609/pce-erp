# Enterprise Operating UI Correction

## V1.6 UI Structure Fix

V1.6 restores the Enterprise Operating UI priority model:

```text
1. Action Area
2. Business Area
3. Workflow Panel
4. Dashboard Panel
```

## Rules

- Operational content appears first.
- Tables, forms, workflow actions, and process execution have highest priority.
- Dashboard, KPI, AI, analytics, and runtime panels are secondary.
- Secondary panels are collapsed by default.
- Dashboard never owns the main page body.

## Runtime Flags

```json
{
  "uiPriorityMode": "OPERATION_FIRST",
  "dashboardMode": "SECONDARY"
}
```

## Updated Surfaces

- `pageRenderer.js`: list pages now render action area, business table, workflow panel, then collapsed dashboard panels.
- `EnterpriseOSPage.vue`: default view is Process Center; Dashboard is a secondary panel.
- `MetaPage.vue`: business operations stay primary; runtime dashboards are collapsed below.
