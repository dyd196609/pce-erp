import purchaseOrderSchema from '../schema/purchase/purchaseOrder.js'
import { financeFields } from '../data/models/financeModel.js'
import { crmFields } from '../data/models/crmModel.js'
import { scmFields } from '../data/models/scmModel.js'
import { inventoryFields } from '../data/models/inventoryModel.js'

function createWorkflow(entity) {
  const workflows = {
    finance: {
      states: ['created', 'reviewed', 'posted', 'settled'],
      transitions: [
        { from: 'created', to: 'reviewed' },
        { from: 'reviewed', to: 'posted' },
        { from: 'posted', to: 'settled' },
      ],
      actions: {
        REVIEW: ['created'],
        POST: ['reviewed'],
        SETTLE: ['posted'],
      },
    },
    crm: {
      states: ['lead', 'opportunity', 'quotation', 'deal'],
      transitions: [
        { from: 'lead', to: 'opportunity' },
        { from: 'opportunity', to: 'quotation' },
        { from: 'quotation', to: 'deal' },
      ],
      actions: {
        QUALIFY: ['lead'],
        QUOTE: ['opportunity'],
        CLOSE_DEAL: ['quotation'],
      },
    },
    scm: {
      states: ['order', 'in_stock', 'in_transit', 'delivered'],
      transitions: [
        { from: 'order', to: 'in_stock' },
        { from: 'in_stock', to: 'in_transit' },
        { from: 'in_transit', to: 'delivered' },
      ],
      actions: {
        STOCK: ['order'],
        SHIP: ['in_stock'],
        DELIVER: ['in_transit'],
      },
    },
    inventory: {
      states: ['order', 'in_stock', 'in_transit', 'delivered'],
      transitions: [
        { from: 'order', to: 'in_stock' },
        { from: 'in_stock', to: 'in_transit' },
        { from: 'in_transit', to: 'delivered' },
      ],
      actions: {
        STOCK: ['order'],
        SHIP: ['in_stock'],
        DELIVER: ['in_transit'],
      },
    },
  }
  const definition = workflows[entity] || {
    states: ['draft', 'submitted', 'approved', 'received', 'closed'],
    transitions: [
      { from: 'draft', to: 'submitted' },
      { from: 'submitted', to: 'approved' },
      { from: 'approved', to: 'received' },
      { from: 'received', to: 'closed' },
    ],
    actions: {
      SUBMIT: ['draft'],
      APPROVE: ['submitted'],
      RECEIVE: ['approved'],
      CLOSE: ['received'],
    },
  }

  return {
    entity,
    stateField: 'workflow_state',
    ...definition,
  }
}

function createListSchema({ name, title, module, columns }) {
  return {
    name,
    labels: {
      en: title,
      'zh-CN': title,
    },
    meta: {
      title,
      module,
    },
    api: {
      module,
    },
    ui: {
      list: {
        columns: [
          { key: 'index', label: '序号', type: 'index' },
          ...columns,
          { key: 'workflow_state', label: '流程状态', sortable: true, filter: true, filterType: 'select' },
        ],
        actions: [
          { key: 'detail', label: '详情', type: 'route', to: `/${module}/:id` },
          { key: 'edit', label: '编辑', type: 'route', to: `/${module}/:id/edit` },
          ...Object.keys(createWorkflow(module).actions).map((action) => ({
            key: action,
            label: action,
            type: 'workflow',
            workflowAction: action,
          })),
        ],
      },
      detail: {},
      form: {},
    },
    workflow: createWorkflow(module),
  }
}

const defaultModules = [
  {
    key: 'orders',
    domain: 'purchase',
    name: 'Purchase Orders',
    label: 'Orders',
    route: '/purchase/order',
    icon: 'Tickets',
    layer: 'executionLayer',
    apiNamespace: '/api/execution/purchase',
    schema: purchaseOrderSchema,
  },
  {
    key: 'inventory',
    domain: 'inventory',
    name: 'Inventory',
    label: 'Inventory',
    route: null,
    icon: 'Box',
    layer: 'executionLayer',
    enterpriseOS: {
      legacyModule: 'Inventory',
      processNode: 'Warehouse',
      menuVisible: false,
    },
    apiNamespace: '/api/execution/inventory',
    schema: createListSchema({
      name: 'inventory',
      title: '库存',
      module: 'inventory',
      columns: inventoryFields,
    }),
  },
  {
    key: 'finance',
    domain: 'finance',
    name: 'Finance',
    label: 'Finance',
    route: null,
    icon: 'TrendCharts',
    layer: 'executionLayer',
    enterpriseOS: {
      legacyModule: 'Finance',
      processNode: 'Finance',
      menuVisible: false,
    },
    apiNamespace: '/api/execution/finance',
    schema: createListSchema({
      name: 'finance',
      title: '财务',
      module: 'finance',
      columns: financeFields,
    }),
  },
  {
    key: 'crm',
    domain: 'crm',
    name: 'CRM',
    label: 'CRM',
    route: null,
    icon: 'UserFilled',
    layer: 'executionLayer',
    enterpriseOS: {
      legacyModule: 'CRM',
      processNode: 'Plan',
      menuVisible: false,
    },
    apiNamespace: '/api/execution/crm',
    schema: createListSchema({
      name: 'crm',
      title: 'CRM',
      module: 'crm',
      columns: crmFields,
    }),
  },
  {
    key: 'scm',
    domain: 'scm',
    name: 'SCM',
    label: 'SCM',
    route: null,
    icon: 'Box',
    layer: 'executionLayer',
    enterpriseOS: {
      legacyModule: 'SCM',
      processNode: 'Purchase',
      menuVisible: false,
    },
    apiNamespace: '/api/execution/scm',
    schema: createListSchema({
      name: 'scm',
      title: 'SCM',
      module: 'scm',
      columns: scmFields,
    }),
  },
]

const moduleMap = new Map(defaultModules.map((module) => [module.key, module]))

export function registerGlobalModule(module) {
  const normalized = {
    generated: false,
    layer: 'executionLayer',
    ...module,
  }

  moduleMap.set(normalized.key, normalized)
  return normalized
}

export function getGlobalModule(key) {
  return moduleMap.get(key)
}

export function getAllGlobalModules() {
  return Array.from(moduleMap.values())
}

export function getGlobalModuleSchemas() {
  return getAllGlobalModules()
    .filter((module) => module.schema && module.route)
    .map((module) => ({
      route: module.route,
      schema: module.schema,
      module,
    }))
}
