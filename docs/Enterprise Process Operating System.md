# Enterprise Process Operating System

## V1.2 Runtime Upgrade

V1.2 upgrades the Enterprise OS from a structure-oriented system to a process-driven operating system.

## Process Engines

| Engine | File | Responsibility |
| --- | --- | --- |
| Process Definition Engine | `frontend/src/meta/process/processDefinitionEngine.js` | Defines steps, roles, and transitions. |
| Workflow State Engine | `frontend/src/meta/process/workflowStateEngine.js` | Executes state machines and blocks invalid transitions. |
| Task Engine | `frontend/src/meta/process/taskEngine.js` | Assigns tasks to roles, tracks execution, and validates completion. |
| Process Router | `frontend/src/meta/process/processRouterEngine.js` | Determines the next step and next role. |
| Execution Timeline Engine | `frontend/src/meta/process/executionTimelineEngine.js` | Builds process history and execution timelines. |

## Purchase Process Validation

```text
draft -> submitted -> approved
```

Roles:

- `draft`: Requester
- `submitted`: Procurement Manager
- `approved`: Finance Controller

Invalid jump protection:

```text
draft -> approved = BLOCKED
```

## Runtime Flags

```json
{
  "processMode": "ACTIVE",
  "workflowEngine": "ENABLED",
  "taskEngine": "ACTIVE",
  "processRouting": "ON"
}
```

## UI Surfaces

MetaPage now includes:

- Process Execution Dashboard
- Workflow State Viewer
- Task Assignment Panel
- Execution Timeline View

Process Center now displays the purchase workflow runtime summary directly from the process engines.
