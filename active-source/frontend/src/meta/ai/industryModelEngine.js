let latestIndustryModel = null

function normalizeInput(input = '') {
  if (typeof input === 'string') return input.toLowerCase()
  return JSON.stringify(input || {}).toLowerCase()
}

export function detectIndustry(input = '') {
  const source = normalizeInput(input)

  if (source.includes('manufacturing') || source.includes('factory') || source.includes('mes') || source.includes('制造') || source.includes('生产')) {
    return 'manufacturing'
  }

  if (source.includes('logistics') || source.includes('delivery') || source.includes('transport') || source.includes('物流') || source.includes('运输')) {
    return 'logistics'
  }

  if (source.includes('finance') || source.includes('cash') || source.includes('ar aging') || source.includes('财务') || source.includes('金融')) {
    return 'finance'
  }

  if (source.includes('retail') || source.includes('pos') || source.includes('store') || source.includes('零售') || source.includes('门店')) {
    return 'retail'
  }

  if (source.includes('crm') || source.includes('customer') || source.includes('客户')) {
    return 'crm'
  }

  if (source.includes('scm') || source.includes('supply') || source.includes('procurement') || source.includes('供应链') || source.includes('采购')) {
    return 'scm'
  }

  return 'manufacturing'
}

export function generateKPIs(industry) {
  switch (industry) {
    case 'manufacturing':
      return ['OEE', 'Yield', 'Downtime']
    case 'finance':
      return ['CashFlow', 'ProfitMargin', 'AR Aging']
    case 'logistics':
      return ['DeliveryTime', 'InventoryTurnover']
    case 'retail':
      return ['GMV', 'SellThroughRate', 'StoreMargin']
    case 'crm':
      return ['CustomerRetention', 'LeadConversion', 'CustomerLTV']
    case 'scm':
      return ['SupplierOTD', 'PurchaseCycleTime', 'CostSaving']
    default:
      return ['SystemScore']
  }
}

function purchaseWorkflow() {
  return {
    entity: 'purchaseOrder',
    stateField: 'workflow_state',
    states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'RECEIVED', 'CLOSED'],
    transitions: [
      { from: 'DRAFT', to: 'SUBMITTED' },
      { from: 'SUBMITTED', to: 'APPROVED' },
      { from: 'APPROVED', to: 'RECEIVED' },
      { from: 'RECEIVED', to: 'CLOSED' },
    ],
    actions: {
      SUBMIT: ['DRAFT'],
      APPROVE: ['SUBMITTED'],
      RECEIVE: ['APPROVED'],
      CLOSE: ['RECEIVED'],
    },
  }
}

function approvalWorkflow(entity = 'approvalFlow') {
  return {
    entity,
    stateField: 'workflow_state',
    states: ['REQUESTED', 'REVIEWING', 'APPROVED', 'CLOSED'],
    transitions: [
      { from: 'REQUESTED', to: 'REVIEWING' },
      { from: 'REVIEWING', to: 'APPROVED' },
      { from: 'APPROVED', to: 'CLOSED' },
    ],
    actions: {
      REVIEW: ['REQUESTED'],
      APPROVE: ['REVIEWING'],
      CLOSE: ['APPROVED'],
    },
  }
}

function inventoryWorkflow() {
  return {
    entity: 'inventoryItem',
    stateField: 'workflow_state',
    states: ['PLANNED', 'INBOUND', 'STOCKED', 'ALLOCATED', 'CLOSED'],
    transitions: [
      { from: 'PLANNED', to: 'INBOUND' },
      { from: 'INBOUND', to: 'STOCKED' },
      { from: 'STOCKED', to: 'ALLOCATED' },
      { from: 'ALLOCATED', to: 'CLOSED' },
    ],
    actions: {
      RECEIVE: ['PLANNED'],
      STOCK: ['INBOUND'],
      ALLOCATE: ['STOCKED'],
      CLOSE: ['ALLOCATED'],
    },
  }
}

function financeWorkflow() {
  return {
    entity: 'financeFlow',
    stateField: 'workflow_state',
    states: ['OPEN', 'CHECKING', 'SETTLED', 'CLOSED'],
    transitions: [
      { from: 'OPEN', to: 'CHECKING' },
      { from: 'CHECKING', to: 'SETTLED' },
      { from: 'SETTLED', to: 'CLOSED' },
    ],
    actions: {
      CHECK: ['OPEN'],
      SETTLE: ['CHECKING'],
      CLOSE: ['SETTLED'],
    },
  }
}

export function generateWorkflows(input = '') {
  const industry = detectIndustry(input)

  return {
    purchase: purchaseWorkflow(),
    approval: approvalWorkflow(`${industry}Approval`),
    inventory: inventoryWorkflow(),
    finance: financeWorkflow(),
  }
}

function baseColumns(extra = []) {
  return [
    { key: 'index', label: '序号', type: 'index' },
    { key: 'name', label: '名称', sortable: true, filter: true, filterType: 'text' },
    { key: 'owner', label: '负责人', sortable: true, filter: true, filterType: 'select' },
    { key: 'workflow_state', label: '流程状态', sortable: true, filter: true, filterType: 'select' },
    ...extra,
  ]
}

function createSchema({ name, route, title, module, workflow, columns, kpis, industry }) {
  return {
    name,
    route,
    industry,
    meta: {
      title,
      module,
      industry,
    },
    labels: {
      en: title,
      'zh-CN': title,
    },
    api: {
      module: name,
    },
    kpis,
    ui: {
      list: {
        columns,
        actions: [
          { key: 'detail', label: '详情', type: 'route', to: `${route}/:id` },
        ],
      },
    },
    workflow,
  }
}

export function generateSchemas(input = '') {
  const industry = detectIndustry(input)
  const workflows = generateWorkflows(input)
  const kpis = generateKPIs(industry)

  const common = [
    createSchema({
      name: `${industry}Purchase`,
      route: `/${industry}/purchase`,
      title: '行业采购模块',
      module: 'purchase',
      industry,
      kpis,
      workflow: workflows.purchase,
      columns: baseColumns([
        { key: 'supplier', label: '供应商', sortable: true, filter: true, filterType: 'select' },
        { key: 'amount', label: '金额', sortable: true, filter: true, filterType: 'text' },
      ]),
    }),
    createSchema({
      name: `${industry}Inventory`,
      route: `/${industry}/inventory`,
      title: '行业库存模块',
      module: 'inventory',
      industry,
      kpis,
      workflow: workflows.inventory,
      columns: baseColumns([
        { key: 'warehouse', label: '仓库', sortable: true, filter: true, filterType: 'select' },
        { key: 'stock_qty', label: '库存数量', sortable: true, filter: true, filterType: 'text' },
      ]),
    }),
    createSchema({
      name: `${industry}Finance`,
      route: `/${industry}/finance`,
      title: '行业财务模块',
      module: 'finance',
      industry,
      kpis,
      workflow: workflows.finance,
      columns: baseColumns([
        { key: 'cashflow', label: '现金流', sortable: true, filter: true, filterType: 'text' },
        { key: 'margin', label: '利润率', sortable: true, filter: true, filterType: 'text' },
      ]),
    }),
  ]

  if (industry === 'crm' || industry === 'retail') {
    common.push(createSchema({
      name: `${industry}Customer`,
      route: `/${industry}/customer`,
      title: '行业客户模块',
      module: 'crm',
      industry,
      kpis,
      workflow: approvalWorkflow(`${industry}Customer`),
      columns: baseColumns([
        { key: 'customer_level', label: '客户等级', sortable: true, filter: true, filterType: 'select' },
        { key: 'ltv', label: '客户价值', sortable: true, filter: true, filterType: 'text' },
      ]),
    }))
  }

  return common
}

export function generateControlRules(input = '') {
  const industry = detectIndustry(input)
  const strictIndustries = ['finance', 'manufacturing']

  return {
    industry,
    reviewThreshold: strictIndustries.includes(industry) ? 0.85 : 0.75,
    allowAutoApproval: !strictIndustries.includes(industry),
    requireTraceability: true,
    controlMode: strictIndustries.includes(industry) ? 'MONITOR' : 'NORMAL',
  }
}

export function generateIndustryModel(input = '') {
  const industry = detectIndustry(input)
  const model = {
    mode: 'V12.9_INDUSTRY_MODEL',
    input,
    industry,
    schemas: generateSchemas(input),
    workflows: generateWorkflows(input),
    kpis: generateKPIs(industry),
    rules: generateControlRules(input),
  }

  latestIndustryModel = model
  return model
}

export function getLatestIndustryModel() {
  return latestIndustryModel
}
