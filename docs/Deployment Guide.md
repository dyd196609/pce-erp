# Deployment Guide

## Supported Environments

| Environment | Runtime Mode | Debug Hooks | Frozen Runtime | Target |
| --- | --- | --- | --- | --- |
| dev | DEVELOPMENT | ENABLED | false | local developer workstation |
| staging | STAGING | LIMITED | true | pre-production validation cluster |
| production | PRODUCTION | DISABLED | true | enterprise SaaS production cluster |

## Service Boundary

The deployment package is split into these services:

- frontend
- api-gateway
- nginx
- kernel-service
- agent-service
- business-service
- redis
- postgres

## Local Dev

Use the frontend dev server and backend API for local development. Debug hooks are allowed, but API responses still use the standard response envelope.

## Staging

Staging must run frozen runtime behavior and validate:

- module standardization
- API envelope compliance
- tenant isolation
- billing and onboarding flows
- deployment pipeline status
- monitoring and SLA panels

## Production

Production must run frozen runtime behavior with debug hooks disabled. Required readiness gates:

- `productizationMode = ACTIVE`
- `architectureFrozen = true`
- `deliveryReady = true`
- `deployment.productionReady = true`
- standard API envelope enabled
- module catalog standardized

## Docker Compose

The existing deployment entry is:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

## Kubernetes

Kubernetes service definitions live under `deploy/k8s`. Production images should be versioned, scanned, and promoted from staging after readiness validation.
