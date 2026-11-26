import {
  listBusinessModuleRelationships,
  listEmdProcessNodes,
  listBusinessProcessModules,
  listBusinessProcessNodes,
  listBusinessProcesses,
  listPdeProcessNodes,
} from '../process/businessProcessRegistry.js'
import { CRM_ORDER_PROCESS, CRM_ORDER_PROCESS_NODES } from './crmOrderProcessRegistry.js'

export const PROCESS_CENTER_RUNTIME_VERSION = 'V1.14.2.8.4.27.2.16'
export const PROCESS_CENTER_RUNTIME_CODE = 'ProcessCenterRuntime'
export const PROCESS_CENTER_RUNTIME_MODEL_TYPE = 'ProcessCenterRuntimeModel'
export const PROCESS_CENTER_CANONICAL_ROUTE = '/process-center'
export const PROCESS_CENTER_RUNTIME_COUNT = 1
export const PROCESS_CENTER_ENTRY_COUNT = 1
export const PROCESS_CENTER_ENTRY_RULE = 'PROCESS-CENTER-ENTRY-002'

export const PROCESS_CENTER_ENTRY_CONTRACT = Object.freeze({
  route: PROCESS_CENTER_CANONICAL_ROUTE,
  routeComponent: 'EnterpriseOSPage',
  runtimeCode: PROCESS_CENTER_RUNTIME_CODE,
  runtimeModelType: PROCESS_CENTER_RUNTIME_MODEL_TYPE,
  entryCount: PROCESS_CENTER_ENTRY_COUNT,
  runtimeCount: PROCESS_CENTER_RUNTIME_COUNT,
  modulePrivateRuntimeAllowed: false,
  rule: PROCESS_CENTER_ENTRY_RULE,
})

const freeze = value => Object.freeze(value)

function buildProcessCenterModules(modules, processes) {
  const byCode = new Map(modules.map(module => [module.moduleCode, { ...module }]))
  for (const process of processes) {
    if (!byCode.has(process.moduleCode)) {
      byCode.set(process.moduleCode, {
        moduleCode: process.moduleCode,
        moduleName: process.moduleName,
        description: `${process.processName}正式流程`,
        order: byCode.size + 1,
        status: process.status,
      })
    }
  }
  return Array.from(byCode.values()).map(freeze)
}

export function assertSingleFormalFlowPerModule(processes = []) {
  const counts = new Map()
  for (const process of processes) {
    if (process.enabled === false || process.status === 'inactive') continue
    counts.set(process.moduleCode, (counts.get(process.moduleCode) || 0) + 1)
  }
  const conflicts = Array.from(counts.entries()).filter(([, count]) => count > 1)
  if (conflicts.length) {
    throw new Error(`PROCESS_CENTER_FORMAL_FLOW_CONFLICT: ${conflicts.map(([code]) => code).join(', ')}`)
  }
  return true
}

export function loadProcessCenterRuntimeModel() {
  const processes = [
    CRM_ORDER_PROCESS,
    ...listBusinessProcesses().filter(process => process.processCode !== CRM_ORDER_PROCESS.processCode),
  ].filter(process => process.enabled !== false && process.status === 'active')
  assertSingleFormalFlowPerModule(processes)
  const modules = buildProcessCenterModules(listBusinessProcessModules(), processes)
  return freeze({
    runtimeCode: PROCESS_CENTER_RUNTIME_CODE,
    runtimeModelType: PROCESS_CENTER_RUNTIME_MODEL_TYPE,
    canonicalRoute: PROCESS_CENTER_CANONICAL_ROUTE,
    runtimeCount: PROCESS_CENTER_RUNTIME_COUNT,
    entryCount: PROCESS_CENTER_ENTRY_COUNT,
    entryContract: PROCESS_CENTER_ENTRY_CONTRACT,
    modules: freeze(modules),
    processes: freeze(processes),
    crmOrderNodes: CRM_ORDER_PROCESS_NODES,
    scmPurchaseNodes: freeze(listBusinessProcessNodes()),
    pdeNodes: freeze(listPdeProcessNodes()),
    emdNodes: freeze(listEmdProcessNodes()),
    relationships: freeze(listBusinessModuleRelationships()),
    factSource: 'businessProcessRegistry',
    businessWriteCount: 0,
  })
}

export function normalizeProcessCenterEntry({ moduleCode = '' } = {}) {
  const normalizedModule = String(moduleCode || '').trim().toUpperCase()
  return freeze({ path: PROCESS_CENTER_CANONICAL_ROUTE,
    query: normalizedModule ? freeze({ module: normalizedModule }) : freeze({}),
    runtimeCode: PROCESS_CENTER_RUNTIME_CODE })
}
