import { reactive, readonly } from 'vue'
import { purchaseRequestApi } from '@/api/purchaseRequest.js'

export const PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY = Symbol('purchase-request-provider-runtime')

const providerDefinitions = Object.freeze({
  employeeProvider: { referenceType: 'employees' },
  departmentProvider: { referenceType: 'organization-tree' },
  projectProvider: { referenceType: 'projects' },
  costCenterProvider: { referenceType: 'cost-centers' },
  expenseCategoryProvider: { referenceType: 'expense-categories' },
  budgetCategoryProvider: { referenceType: 'budget-categories' },
  materialProvider: { referenceType: 'materials' },
  supplierProvider: { referenceType: 'suppliers' },
})

const providers = reactive(Object.fromEntries(Object.keys(providerDefinitions).map((code) => [code, []])))
const loading = reactive(Object.fromEntries(Object.keys(providerDefinitions).map((code) => [code, false])))
const errors = reactive(Object.fromEntries(Object.keys(providerDefinitions).map((code) => [code, ''])))
const httpStatus = reactive(Object.fromEntries(Object.keys(providerDefinitions).map((code) => [code, 0])))
const runtimeState = reactive({ initialized: false, ready: false, loadedAt: '', loadCount: 0 })
let pendingLoad = null

function resultRows(response) {
  return response?.data?.results || response?.data?.data?.results || []
}

async function loadProvider(code) {
  const definition = providerDefinitions[code]
  loading[code] = true
  errors[code] = ''
  httpStatus[code] = 0
  try {
    const response = await purchaseRequestApi.searchReference(definition.referenceType, '', 200)
    httpStatus[code] = Number(response?.meta?.status || response?.httpStatus || 0)
    if (response?.success === false || httpStatus[code] !== 200) {
      throw new Error(response?.error?.message || `Provider API HTTP ${httpStatus[code] || 0}`)
    }
    const rows = resultRows(response)
    providers[code] = rows
    if (!rows.length) errors[code] = '未读取到有效主数据'
    return rows
  } catch (error) {
    providers[code] = []
    errors[code] = error?.message || '主数据读取失败'
    return []
  } finally {
    loading[code] = false
  }
}

export const loadEmployeeProvider = () => loadProvider('employeeProvider')
export const loadDepartmentProvider = () => loadProvider('departmentProvider')
export const loadProjectProvider = () => loadProvider('projectProvider')
export const loadCostCenterProvider = () => loadProvider('costCenterProvider')
export const loadExpenseCategoryProvider = () => loadProvider('expenseCategoryProvider')
export const loadBudgetCategoryProvider = () => loadProvider('budgetCategoryProvider')
export const loadMaterialProvider = () => loadProvider('materialProvider')
export const loadSupplierProvider = () => loadProvider('supplierProvider')

export async function initPurchaseRequestProviders({ force = false } = {}) {
  if (runtimeState.ready && !force) return providers
  if (pendingLoad && !force) return pendingLoad
  pendingLoad = Promise.all([
    loadEmployeeProvider(),
    loadDepartmentProvider(),
    loadProjectProvider(),
    loadCostCenterProvider(),
    loadExpenseCategoryProvider(),
    loadBudgetCategoryProvider(),
    loadMaterialProvider(),
    loadSupplierProvider(),
  ]).then((results) => {
    runtimeState.initialized = true
    runtimeState.ready = results.every((rows) => rows.length > 0)
      && Object.values(errors).every((message) => !message)
      && Object.values(httpStatus).every((status) => status === 200)
    runtimeState.loadedAt = new Date().toISOString()
    runtimeState.loadCount += 1
    return providers
  }).finally(() => { pendingLoad = null })
  return pendingLoad
}

export const purchaseRequestProviders = Object.freeze({
  definitions: providerDefinitions,
  providers: readonly(providers),
  loading: readonly(loading),
  errors: readonly(errors),
  httpStatus: readonly(httpStatus),
  state: readonly(runtimeState),
  loadProvider,
  loadEmployeeProvider,
  loadDepartmentProvider,
  loadProjectProvider,
  loadCostCenterProvider,
  loadExpenseCategoryProvider,
  loadBudgetCategoryProvider,
  loadMaterialProvider,
  loadSupplierProvider,
  initPurchaseRequestProviders,
  loadAll: initPurchaseRequestProviders,
  refresh: () => initPurchaseRequestProviders({ force: true }),
})
