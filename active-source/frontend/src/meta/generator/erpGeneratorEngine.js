import { registerSchema } from '../core/schemaRegistry.js'
import { generateIndustryModel } from '../ai/industryModelEngine.js'
import { generateUI } from '../runtime/uiGeneratorEngine.js'
import { UIControlRuntimeKernel } from '../runtime/uiControlRuntimeKernel.js'
import { registerCockpitNavigation } from '../navigation/cockpitRegistry.js'
import { registerModule } from '../registry/moduleRegistry.js'
import { registerPlatformModule } from '../platform/moduleHub.js'

const defaultWorkflow = {
  entity: 'generatedEntity',
  stateField: 'workflow_state',
  states: ['DRAFT', 'ACTIVE', 'CLOSED'],
  transitions: [
    { from: 'DRAFT', to: 'ACTIVE' },
    { from: 'ACTIVE', to: 'CLOSED' },
  ],
  actions: {
    ACTIVATE: ['DRAFT'],
    CLOSE: ['ACTIVE'],
  },
}

const moduleProfiles = {
  purchase: {
    key: 'purchase',
    name: 'Purchase Module',
    icon: 'Tickets',
    apiNamespace: '/api/execution/purchase',
  },
  inventory: {
    key: 'inventoryGenerated',
    name: 'Inventory Module',
    icon: 'Box',
    apiNamespace: '/api/execution/inventory',
  },
  finance: {
    key: 'finance',
    name: 'Finance Module',
    icon: 'TrendCharts',
    apiNamespace: '/api/execution/finance',
  },
  crm: {
    key: 'crm',
    name: 'CRM Module',
    icon: 'UserFilled',
    apiNamespace: '/api/execution/crm',
  },
}

function pascalToWords(value = '') {
  return String(value)
    .replace(/([A-Z])/g, ' $1')
    .replace(/[_-]+/g, ' ')
    .trim()
}

function isIndustryInput(input) {
  return typeof input === 'string' || Boolean(input?.industryInput || input?.industryPrompt)
}

function resolveIndustryModel(input) {
  if (!isIndustryInput(input)) return input?.industryModel || null

  return generateIndustryModel(
    typeof input === 'string'
      ? input
      : input.industryInput || input.industryPrompt
  )
}

function inferModuleType(schema = {}) {
  const source = `${schema.name || ''} ${schema.api?.module || ''} ${schema.meta?.module || ''}`.toLowerCase()

  if (source.includes('purchase') || source.includes('order') || source.includes('采购')) return 'purchase'
  if (source.includes('inventory') || source.includes('warehouse') || source.includes('stock') || source.includes('库存')) return 'inventory'
  if (source.includes('finance') || source.includes('invoice') || source.includes('payment') || source.includes('财务')) return 'finance'
  if (source.includes('crm') || source.includes('customer') || source.includes('客户')) return 'crm'

  return 'purchase'
}

function normalizeWorkflow(schema = {}) {
  if (schema.workflow?.states?.length && schema.workflow?.transitions?.length && schema.workflow?.actions) {
    return {
      ...schema.workflow,
      entity: schema.workflow.entity || schema.name || schema.api?.module || 'generatedEntity',
      stateField: schema.workflow.stateField || schema.workflow.statusField || 'workflow_state',
    }
  }

  return {
    ...defaultWorkflow,
    entity: schema.name || schema.api?.module || defaultWorkflow.entity,
  }
}

function ensureColumns(schema = {}) {
  const columns = schema?.ui?.list?.columns || []
  if (columns.length > 0) return columns

  return [
    { key: 'index', label: '序号', type: 'index' },
    { key: 'name', label: '名称', sortable: true, filter: true, filterType: 'text' },
    { key: 'workflow_state', label: '流程状态', sortable: true, filter: true, filterType: 'select' },
  ]
}

function ensureActions(schema = {}, workflow) {
  const actions = schema?.ui?.list?.actions || []
  const workflowActions = Object.keys(workflow.actions || {}).map((action) => ({
    key: action,
    label: action,
    type: 'workflow',
    workflowAction: action,
  }))

  return [
    { key: 'detail', label: '详情', type: 'route', to: `${schema.route || `/${schema.name || 'generated'}`}/:id` },
    ...actions,
    ...workflowActions.filter((action) => !actions.some((existing) => existing.key === action.key)),
  ]
}

function buildGeneratedSchema(schema = {}, industryModel = null) {
  const workflow = normalizeWorkflow(schema)

  return {
    ...schema,
    name: schema.name || schema.api?.module || 'generatedModule',
    industry: schema.industry || industryModel?.industry,
    labels: schema.labels || {
      en: pascalToWords(schema.name || 'Generated Module'),
      'zh-CN': schema.meta?.title || schema.title || '生成模块',
    },
    api: {
      module: schema.api?.module || schema.name || 'generatedModule',
      ...(schema.api || {}),
    },
    kpis: schema.kpis || industryModel?.kpis || ['SystemScore'],
    controlRules: schema.controlRules || industryModel?.rules || {},
    ui: {
      ...(schema.ui || {}),
      list: {
        ...(schema?.ui?.list || {}),
        columns: ensureColumns(schema),
        actions: ensureActions(schema, workflow),
      },
      detail: schema?.ui?.detail || {},
      form: schema?.ui?.form || {},
    },
    workflow,
  }
}

function buildModules(schema = {}) {
  const type = inferModuleType(schema)
  const profile = moduleProfiles[type]
  const key = schema.moduleKey || schema.name || schema.api?.module || profile.key
  const route = schema.route || `/${type}/${key}`

  return [
    {
      ...profile,
      key,
      route,
      type,
      industry: schema.industry,
      generated: true,
      schema,
      kpis: schema.kpis || [],
      responsibility: `${profile.name} Runtime Module`,
    },
  ]
}

function buildWorkflows(schema = {}) {
  return {
    [schema.name || schema.api?.module || 'generatedModule']: normalizeWorkflow(schema),
  }
}

function buildUI(schema = {}) {
  const runtime = UIControlRuntimeKernel(schema, {
    workflow_state: schema.workflow?.states?.[0] || 'DRAFT',
  })

  return {
    listPage: generateUI(schema, runtime),
    detailPage: {
      layout: 'detail',
      labels: schema.labels || {},
    },
    cockpitMetrics: (schema.kpis || ['SystemScore']).map((kpi) => ({
      key: kpi,
      label: kpi,
      source: 'industry',
    })),
  }
}

function buildControl(schema = {}) {
  const runtime = UIControlRuntimeKernel(schema)

  return {
    permissionRules: {
      module: schema.api?.module || schema.name,
      actions: runtime.uiControl.allowedActions,
    },
    reviewRules: {
      controlMode: runtime.controlMode,
      restrictions: runtime.loop.restrictions,
    },
    industryRules: schema.controlRules || {},
    optimizationRules: runtime.optimization.optimization,
  }
}

function mergeObjects(items) {
  return items.reduce((merged, item) => ({
    ...merged,
    ...item,
  }), {})
}

export function generateERP(input = {}) {
  const industryModel = resolveIndustryModel(input)
  const sourceSchemas = industryModel?.schemas?.length
    ? industryModel.schemas
    : [input]
  const schemas = sourceSchemas.map((schema) => buildGeneratedSchema(schema, industryModel))
  const moduleGroups = schemas.map(buildModules)
  const modules = moduleGroups.flat()
  const workflows = mergeObjects(schemas.map(buildWorkflows))
  const uiByModule = schemas.reduce((map, schema) => {
    map[schema.name] = buildUI(schema)
    return map
  }, {})
  const controlByModule = schemas.reduce((map, schema) => {
    map[schema.name] = buildControl(schema)
    return map
  }, {})

  return {
    mode: industryModel ? 'INDUSTRY_AWARE_ERP_GENERATION' : 'SCHEMA_ERP_GENERATION',
    industryModel,
    schema: schemas[0],
    schemas,
    modules,
    workflows,
    ui: {
      ...uiByModule[schemas[0]?.name],
      byModule: uiByModule,
      cockpitDashboard: {
        industry: industryModel?.industry || schemas[0]?.industry || 'general',
        kpis: industryModel?.kpis || schemas[0]?.kpis || ['SystemScore'],
      },
    },
    control: {
      ...controlByModule[schemas[0]?.name],
      byModule: controlByModule,
    },
  }
}

export function registerGeneratedERP(input = {}) {
  const generated = generateERP(input)
  const registeredModules = generated.modules.map((module) => {
    const registered = registerPlatformModule(module)
    registerModule(module)

    registerSchema(module.route, module.schema)
    registerCockpitNavigation({
      key: module.key,
      label: module.schema?.labels?.['zh-CN'] || module.name,
      path: module.route,
      icon: module.icon,
    })

    return registered
  })

  return {
    ...generated,
    registeredModules,
  }
}

export function generateIndustryERP(input = '') {
  return generateERP(input)
}

export function registerGeneratedIndustryERP(input = '') {
  return registerGeneratedERP(input)
}
