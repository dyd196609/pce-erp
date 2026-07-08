# ProfitOS Architecture Lock

## Status

```text
ARCHITECTURE: FROZEN
VERSION: ProfitOS Production Architecture v1.0
```

## Locked Layer Contract

- ProfitOS = Decision Layer
- PalmCloud = Execution Layer
- ERP / MES / SCM / WMS = Execution modules owned by PalmCloud

## Allowed Changes

- Feature implementation
- Module-specific business functions
- API endpoint implementation under approved namespaces
- UI/dashboard improvements
- Deployment and observability improvements

## Disallowed Changes

- New core layers
- New versioned meta expansion stacks
- New V7/V8/V9/V10/V11 architectural abstractions
- Parallel decision kernels
- Parallel agent loops
- Parallel runtime systems

## Approved API Namespaces

- `/api/core/*`
- `/api/profit/*`
- `/api/execution/*`
