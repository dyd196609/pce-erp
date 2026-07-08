# Enterprise Decision Automation Layer

## Goal

The Enterprise Decision Automation Layer converts predictive results into controlled business decisions. It supports semi-autonomous ERP behavior by approving low-risk work, rejecting dangerous operations, rerouting medium-risk flows, and selecting an optimized business path.

## Runtime Flags

- `decisionMode: ON`
- `autoDecision: ACTIVE`
- `policyDecision: ENABLED`
- `riskDecisionControl: ACTIVE`

## Engine Structure

- `frontend/src/meta/decision/decisionAutomationEngine.js`
- `frontend/src/meta/decision/autoApprovalEngine.js`
- `frontend/src/meta/decision/policyDecisionEngine.js`
- `frontend/src/meta/decision/riskDecisionController.js`
- `frontend/src/meta/decision/businessRoutingAI.js`

## Decision Contract

```js
{
  approvalDecision,
  workflowDecision,
  resourceDecision,
  businessDecision
}
```

## UI Surfaces

- Decision Automation Dashboard
- Auto Approval Monitor
- Business Routing View
- Risk Decision Panel

## Control Model

Low-risk operations can be marked ready for auto execution. Medium-risk operations are downgraded to supervised review. High-risk operations are blocked before execution. Every automated decision includes a trace so the decision path is auditable.
