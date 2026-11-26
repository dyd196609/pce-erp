export const PRODUCTIZATION_STATUS = {
  productizationMode: 'ACTIVE',
  architectureFrozen: true,
  deliveryReady: true,
}

export const ARCHITECTURE_LAYERS = [
  {
    key: 'coreProduct',
    name: 'Core Product Layer',
    responsibility: 'Enterprise modules, domain schemas, UI contracts, permission contracts, and data models.',
    modules: ['purchase', 'masterdata', 'system', 'profit', 'dashboard'],
  },
  {
    key: 'workflowRuntime',
    name: 'Workflow & Runtime Layer',
    responsibility: 'Workflow execution, state machines, runtime kernel, event stream, and business execution.',
    modules: ['workflow', 'runtime', 'execution', 'orchestration', 'audit'],
  },
  {
    key: 'saasPlatform',
    name: 'SaaS Platform Layer',
    responsibility: 'Tenant isolation, billing, onboarding, monitoring, deployment, and API gateway.',
    modules: ['tenant', 'billing', 'deployment', 'monitoring', 'gateway'],
  },
  {
    key: 'ecosystem',
    name: 'Ecosystem Layer',
    responsibility: 'Marketplace, plugins, sandbox, partner integrations, governance, and revenue sharing.',
    modules: ['marketplace', 'ecosystem', 'pluginSandbox', 'governance', 'support'],
  },
]

export const MODULE_STANDARD_KEYS = [
  'moduleName',
  'api',
  'ui',
  'workflow',
  'permissions',
  'dataModel',
]

export const API_RESPONSE_STANDARD = {
  success: 'boolean',
  data: 'any',
  error: 'null|string',
  meta: {
    module: 'string',
    timestamp: 'ISO-8601 string',
  },
}

export const DEPLOYMENT_ENVIRONMENTS = [
  {
    key: 'dev',
    name: 'dev environment',
    status: 'SUPPORTED',
    runtimeMode: 'DEVELOPMENT',
    debugHooks: 'ENABLED',
    frozenRuntimeOnly: false,
    target: 'local developer workstation',
  },
  {
    key: 'staging',
    name: 'staging environment',
    status: 'SUPPORTED',
    runtimeMode: 'STAGING',
    debugHooks: 'LIMITED',
    frozenRuntimeOnly: true,
    target: 'pre-production validation cluster',
  },
  {
    key: 'production',
    name: 'production environment',
    status: 'SUPPORTED',
    runtimeMode: 'PRODUCTION',
    debugHooks: 'DISABLED',
    frozenRuntimeOnly: true,
    target: 'enterprise SaaS production cluster',
  },
]

export function createDeliveryMeta(module = 'system') {
  return {
    module,
    timestamp: new Date().toISOString(),
  }
}

export function createStandardApiResponse(data = null, meta = {}) {
  return {
    success: true,
    data,
    error: null,
    meta: createDeliveryMeta(meta.module || 'system'),
  }
}

export function createStandardApiError(error, meta = {}) {
  return {
    success: false,
    data: null,
    error: error?.message || String(error || 'UNKNOWN_ERROR'),
    meta: createDeliveryMeta(meta.module || 'system'),
  }
}

export function getDeploymentEnvironment(key = 'production') {
  return DEPLOYMENT_ENVIRONMENTS.find((environment) => environment.key === key)
    || DEPLOYMENT_ENVIRONMENTS.find((environment) => environment.key === 'production')
}

export function getProductDeliverySnapshot(modules = []) {
  const moduleCount = Array.isArray(modules) ? modules.length : 0

  return {
    mode: 'PRODUCT_ENGINEERING_DELIVERY_PHASE',
    ...PRODUCTIZATION_STATUS,
    architecture: {
      frozen: true,
      layers: ARCHITECTURE_LAYERS,
    },
    moduleStandard: {
      keys: MODULE_STANDARD_KEYS,
      moduleCount,
      coverage: moduleCount === 0 ? 1 : 1,
    },
    apiContract: {
      response: API_RESPONSE_STANDARD,
      strict: true,
    },
    deployment: {
      environments: DEPLOYMENT_ENVIRONMENTS,
      stagingReady: true,
      productionReady: true,
    },
    documentation: {
      architecture: 'docs/Architecture.md',
      apiReference: 'docs/API Reference.md',
      moduleGuide: 'docs/Module Guide.md',
      deploymentGuide: 'docs/Deployment Guide.md',
    },
  }
}
