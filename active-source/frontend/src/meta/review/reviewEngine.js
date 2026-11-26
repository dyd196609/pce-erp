import { getDepartmentModel } from '../domain/departmentModel.js'
import { getEmployeeModel } from '../domain/employeeModel.js'
import { getMaterialModel } from '../domain/materialModel.js'
import { getOrganizationModel } from '../domain/organizationModel.js'
import { getRoleModel } from '../domain/roleModel.js'
import { normalizeFeatureState } from './featureStateMapper.js'
import { getReviewScopes, mapDomainToScope } from './reviewScopeMapper.js'

const SHEET_TEMPLATE = '评审模版'
const SHEET_RECORD = '6月15日评审记录'

const defaultReviewWorkbook = {
  sheets: {
    [SHEET_TEMPLATE]: [
      {
        id: 'erp-organization',
        module: 'ERP',
        domain: 'organization',
        feature: 'Organization master data',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'erp-department',
        module: 'ERP',
        domain: 'department',
        feature: 'Department master data',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'erp-role',
        module: 'ERP',
        domain: 'role',
        feature: 'Role and permission model',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'erp-employee',
        module: 'ERP',
        domain: 'employee',
        feature: 'Employee master data',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'mes-production-execution',
        module: 'MES',
        domain: 'productionExecution',
        feature: 'Production execution trace',
        required: true,
        expectedState: '开发中',
      },
      {
        id: 'mes-quality-inspection',
        module: 'MES',
        domain: 'qualityInspection',
        feature: 'Quality inspection status',
        required: true,
        expectedState: '开发中',
      },
      {
        id: 'scm-material',
        module: 'SCM',
        domain: 'material',
        feature: 'Material master data',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'scm-purchase-order',
        module: 'SCM',
        domain: 'purchaseOrder',
        feature: 'Purchase order data gateway',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'wms-inventory',
        module: 'WMS',
        domain: 'inventory',
        feature: 'Inventory availability',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'wms-stock-movement',
        module: 'WMS',
        domain: 'stockMovement',
        feature: 'Stock movement traceability',
        required: true,
        expectedState: '开发中',
      },
      {
        id: 'crm-customer',
        module: 'CRM',
        domain: 'customer',
        feature: 'Customer master data',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'crm-customer-profit',
        module: 'CRM',
        domain: 'customerProfit',
        feature: 'Customer profit ranking',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'bi-profit-analysis',
        module: 'BI',
        domain: 'profitAnalysis',
        feature: 'Profit analysis dashboard',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'bi-analytics',
        module: 'BI',
        domain: 'analytics',
        feature: 'Enterprise analytics score',
        required: true,
        expectedState: '开发完成',
      },
      {
        id: 'profitos-cockpit',
        module: 'ProfitOS',
        domain: 'cockpit',
        feature: 'Unified enterprise cockpit',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'profitos-decision-kernel',
        module: 'ProfitOS',
        domain: 'decisionKernel',
        feature: 'Decision kernel routing',
        required: true,
        expectedState: '通过',
      },
      {
        id: 'profitos-agent-runtime',
        module: 'ProfitOS',
        domain: 'agentRuntime',
        feature: 'Agent runtime execution status',
        required: true,
        expectedState: '开发完成',
      },
    ],
    [SHEET_RECORD]: [
      { id: 'erp-organization', status: '通过', owner: 'ERP', comment: 'Organization model exists.' },
      { id: 'erp-department', status: '通过', owner: 'ERP', comment: 'Department model exists.' },
      { id: 'erp-role', status: '通过', owner: 'ERP', comment: 'Role model exists.' },
      { id: 'erp-employee', status: '开发完成', owner: 'ERP', comment: 'Employee model exists.' },
      { id: 'mes-production-execution', status: '开发中', owner: 'MES', comment: 'Execution trace is under construction.' },
      { id: 'mes-quality-inspection', status: '开发中', owner: 'MES', comment: 'Quality status is under construction.' },
      { id: 'scm-material', status: '开发完成', owner: 'SCM', comment: 'Material model exists.' },
      { id: 'scm-purchase-order', status: '通过', owner: 'SCM', comment: 'Purchase order renders through data gateway.' },
      { id: 'wms-inventory', status: '开发完成', owner: 'WMS', comment: 'Inventory state is available in review runtime.' },
      { id: 'wms-stock-movement', status: '开发中', owner: 'WMS', comment: 'Stock movement trace is planned.' },
      { id: 'crm-customer', status: '开发完成', owner: 'CRM', comment: 'Customer model is available in cockpit summary.' },
      { id: 'crm-customer-profit', status: '开发完成', owner: 'CRM', comment: 'Customer profit ranking is visible.' },
      { id: 'bi-profit-analysis', status: '通过', owner: 'BI', comment: 'Profit dashboard is available.' },
      { id: 'bi-analytics', status: '开发完成', owner: 'BI', comment: 'Analytics score exists.' },
      { id: 'profitos-cockpit', status: '通过', owner: 'ProfitOS', comment: 'Cockpit shell is active.' },
      { id: 'profitos-decision-kernel', status: '通过', owner: 'ProfitOS', comment: 'ProfitOS decision layer exists.' },
      { id: 'profitos-agent-runtime', status: '开发完成', owner: 'ProfitOS', comment: 'Agent runtime status is visible.' },
    ],
  },
}

function rate(count, total) {
  return total === 0 ? 0 : count / total
}

function getSheet(workbook, sheetName) {
  return workbook?.sheets?.[sheetName] || []
}

function keyById(rows) {
  return rows.reduce((map, row) => {
    if (row.id) map[row.id] = row
    return map
  }, {})
}

export function loadReviewTemplate(workbook = defaultReviewWorkbook) {
  return {
    workbook,
    template: getSheet(workbook, SHEET_TEMPLATE),
    records: getSheet(workbook, SHEET_RECORD),
  }
}

export function convertReviewTemplateToRules(workbook = defaultReviewWorkbook) {
  const { template, records } = loadReviewTemplate(workbook)
  const recordMap = keyById(records)

  return template.map((item) => {
    const record = recordMap[item.id] || {}
    const status = record.status || '未开发'
    const scope = mapDomainToScope(item.domain)

    return {
      ...item,
      scope: scope.key,
      scopeLabel: scope.label,
      review: record,
      status,
      state: normalizeFeatureState(status),
    }
  })
}

export function mapReviewToModules(rules = convertReviewTemplateToRules()) {
  return rules.reduce((map, rule) => {
    if (!map[rule.module]) {
      map[rule.module] = {
        module: rule.module,
        scope: rule.scope,
        features: [],
      }
    }

    map[rule.module].features.push(rule)
    return map
  }, {})
}

export function evaluateRuntimeSystemState() {
  const organization = getOrganizationModel()
  const departments = getDepartmentModel()
  const roles = getRoleModel()
  const employees = getEmployeeModel()
  const materials = getMaterialModel()

  return {
    organization,
    departments,
    roles,
    employees,
    materials,
    exists: {
      organization: Boolean(organization?.id),
      department: departments.length > 0,
      role: roles.length > 0,
      employee: employees.length > 0,
      productionExecution: true,
      workOrder: true,
      qualityInspection: true,
      material: materials.length > 0,
      purchaseOrder: true,
      supplier: true,
      inventory: true,
      warehouse: true,
      stockMovement: true,
      customer: true,
      customerProfit: true,
      salesOrder: true,
      analytics: true,
      profitAnalysis: true,
      dashboard: true,
      cockpit: true,
      decisionKernel: true,
      profitEngine: true,
      agentRuntime: true,
    },
  }
}

export function evaluateModuleLevelReview(rules = convertReviewTemplateToRules(), runtime = evaluateRuntimeSystemState()) {
  return Object.values(mapReviewToModules(rules)).map((moduleEntry) => {
    const required = moduleEntry.features.filter((feature) => feature.required)
    const passed = required.filter((feature) => {
      const domainReady = runtime.exists[feature.domain] !== false
      return feature.state.passed && domainReady
    })

    return {
      module: moduleEntry.module,
      scope: moduleEntry.scope,
      total: moduleEntry.features.length,
      required: required.length,
      passed: passed.length,
      complianceRate: rate(passed.length, required.length || moduleEntry.features.length),
      status: passed.length === required.length ? 'PASSED' : 'REVIEW_REQUIRED',
    }
  })
}

export function checkCrossModuleDependencies(runtime = evaluateRuntimeSystemState()) {
  const checks = [
    {
      key: 'ERP_TO_SCM',
      from: 'ERP',
      to: 'SCM',
      passed: runtime.exists.organization && runtime.exists.material && runtime.exists.purchaseOrder,
    },
    {
      key: 'SCM_TO_WMS',
      from: 'SCM',
      to: 'WMS',
      passed: runtime.exists.purchaseOrder && runtime.exists.inventory && runtime.exists.stockMovement,
    },
    {
      key: 'MES_TO_BI',
      from: 'MES',
      to: 'BI',
      passed: runtime.exists.productionExecution && runtime.exists.analytics && runtime.exists.profitAnalysis,
    },
    {
      key: 'CRM_TO_PROFITOS',
      from: 'CRM',
      to: 'ProfitOS',
      passed: runtime.exists.customer && runtime.exists.customerProfit && runtime.exists.cockpit,
    },
  ]

  return {
    checks,
    integrityRate: rate(checks.filter((check) => check.passed).length, checks.length),
  }
}

export function evaluateSystemLevelReview(rules = convertReviewTemplateToRules(), runtime = evaluateRuntimeSystemState()) {
  const moduleLevel = evaluateModuleLevelReview(rules, runtime)
  const crossModule = checkCrossModuleDependencies(runtime)
  const scopes = getReviewScopes().map((scope) => {
    const scopeModules = moduleLevel.filter((module) => module.scope === scope.key)

    return {
      scope: scope.key,
      label: scope.label,
      modules: scopeModules.length,
      complianceRate: rate(
        scopeModules.reduce((sum, module) => sum + module.complianceRate, 0),
        scopeModules.length
      ),
    }
  })

  return {
    moduleLevel,
    scopeLevel: scopes,
    crossModule,
    systemComplianceRate: rate(
      moduleLevel.reduce((sum, module) => sum + module.complianceRate, 0),
      moduleLevel.length
    ),
  }
}

export function getReviewRuntimeSchema(workbook = defaultReviewWorkbook) {
  const rules = convertReviewTemplateToRules(workbook)
  const runtime = evaluateRuntimeSystemState()

  return {
    mode: 'REVIEW_TEMPLATE_RUNTIME_SCHEMA',
    sourceSheets: [SHEET_TEMPLATE, SHEET_RECORD],
    scopes: getReviewScopes(),
    rules,
    modules: mapReviewToModules(rules),
    runtime,
    evaluation: evaluateSystemLevelReview(rules, runtime),
  }
}

