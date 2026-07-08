function normalizeTenantId(context = {}) {
  return context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'demo_company'
}

export function isolateData(context = {}) {
  const tenantId = normalizeTenantId(context)

  return {
    tenantId,
    dataScope: context.dataScope || context.tenant?.dataScope || context.runtimeState?.tenant?.dataScope || tenantId,
    rowFilter: {
      tenantId,
    },
    isolated: true,
  }
}

export function isolateWorkflow(context = {}) {
  const tenantId = normalizeTenantId(context)

  return {
    tenantId,
    workflowNamespace: `workflow:${tenantId}`,
    statePrefix: tenantId,
    isolated: true,
  }
}

export function isolateSchema(context = {}) {
  const tenantId = normalizeTenantId(context)

  return {
    tenantId,
    schemaNamespace: `schema:${tenantId}`,
    modulePrefix: tenantId,
    isolated: true,
  }
}

export function isolateRuntime(context = {}) {
  const tenantId = normalizeTenantId(context)

  return {
    tenantId,
    runtimeNamespace: `runtime:${tenantId}`,
    cachePrefix: tenantId,
    isolated: true,
  }
}

export function isolateTenant(context = {}) {
  const tenantId = normalizeTenantId(context)

  return {
    mode: 'TENANT_ISOLATION',
    tenantId,
    dataScope: isolateData(context),
    workflowScope: isolateWorkflow(context),
    schemaScope: isolateSchema(context),
    runtimeScope: isolateRuntime(context),
  }
}
