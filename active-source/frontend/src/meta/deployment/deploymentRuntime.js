import {
  deploySaasProduct,
  packageProductionBuild,
  provisionTenantForDeployment,
} from './saasDeploymentEngine.js'
import { rollbackModule } from '../saas/ops/opsControlCenter.js'
import { getAllSchemas } from '../core/schemaRegistry.js'

function resolveTenantId(context = {}) {
  return context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'commercial_demo'
}

function resolvePlan(context = {}) {
  return context.plan || context.tenant?.plan || context.runtimeState?.plan || 'enterprise'
}

export function deployStaging(context = {}) {
  const schemas = context.schemas || getAllSchemas()
  const packaging = packageProductionBuild({
    ...context,
    schemas,
    packageName: context.stagingPackageName || 'profitos-commercial-staging',
  })

  return {
    mode: 'COMMERCIAL_STAGING_DEPLOY',
    status: 'STAGING_READY',
    environment: 'staging',
    packaging,
  }
}

export function deployProduction(context = {}) {
  return deploySaasProduct({
    ...context,
    tenantId: resolveTenantId(context),
    plan: resolvePlan(context),
    packageName: context.packageName || 'profitos-commercial-v1',
  })
}

export function provisionTenantDeployment(context = {}) {
  return provisionTenantForDeployment({
    ...context,
    tenantId: resolveTenantId(context),
    plan: resolvePlan(context),
    companyName: context.companyName || 'Commercial Demo',
  })
}

export function rollbackDeployment(context = {}) {
  return rollbackModule(
    resolveTenantId(context),
    context.module || 'dashboard',
    context.version || 'previous'
  )
}

export function initDeploymentSystem(context = {}) {
  const staging = deployStaging(context)
  const tenant = provisionTenantDeployment(context)
  const production = deployProduction({
    ...context,
    tenant,
  })
  const rollback = rollbackDeployment({
    ...context,
    module: context.rollbackModule || 'dashboard',
    version: context.rollbackVersion || 'stable-v1',
  })

  return {
    mode: 'COMMERCIAL_DEPLOYMENT_RUNTIME',
    status: production.status,
    staging,
    production,
    tenant,
    rollbackSupport: rollback,
  }
}
