import { foundationCanonicalModules } from './foundationEntryUnificationRegistry.js'
import { LATEST_BASE_DATA_TEMPLATE_VERSION } from '../contracts/latestBaseDataTemplateContract.js'

const HISTORICAL_PROTECTED_MODULES = new Set(['routing', 'routing-version', 'routing-step', 'operation'])
const WAVE1_MODULES = new Set([
  'customer', 'supplier', 'material', 'product-definition',
  'workshop', 'operation', 'work-center', 'equipment', 'capacity',
])
const PROVIDER_CORRECTIVE_DOMAINS = new Set(['product-engineering', 'manufacturing-resource'])
const USER_VALIDATED_MODULES = new Set(WAVE1_MODULES)

export const ORDER_PRODUCTION_BASE_DATA_TEMPLATE_ADOPTION_VERSION = 'ORDER-PRODUCTION-BASE-DATA-ADOPTION-V1.0'

export const orderProductionBaseDataTemplateAdoption = Object.freeze(
  foundationCanonicalModules.map(item => Object.freeze({
    moduleId: item.moduleId,
    entityKey: item.entityKey,
    businessDomain: item.businessDomain,
    routePath: item.routePath,
    component: item.component,
    formalModel: item.dataSource,
    api: item.api,
    templateVersion: LATEST_BASE_DATA_TEMPLATE_VERSION,
    wave: WAVE1_MODULES.has(item.moduleId) ? 'WAVE1' : 'BACKLOG',
    adoptionStatus: USER_VALIDATED_MODULES.has(item.moduleId)
      ? 'ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED'
      : item.moduleId === 'supplier'
      ? 'DATA_PROVIDER_BLOCKED'
      : WAVE1_MODULES.has(item.moduleId)
        ? 'ADOPTING_DATA_PROVIDER_BLOCKED'
        : HISTORICAL_PROTECTED_MODULES.has(item.moduleId)
          ? 'ADOPTING_PROTECTED_BASELINE'
          : PROVIDER_CORRECTIVE_DOMAINS.has(item.businessDomain)
            ? 'ADOPTING_DATA_PROVIDER_BLOCKED'
            : 'ADOPTING',
    importApplicability: item.moduleId === 'engineering-calculation'
      ? 'NOT_APPLICABLE_READ_ONLY'
      : 'FORMAL_IMPORT_CHAIN_READY',
    protectedBaseline: HISTORICAL_PROTECTED_MODULES.has(item.moduleId),
    userManualValidation: USER_VALIDATED_MODULES.has(item.moduleId) ? 'PASS' : 'NOT_ASSERTED',
    formalImportManualValidation: USER_VALIDATED_MODULES.has(item.moduleId) ? 'BLOCKED_ACTOR_CONTEXT' : 'NOT_APPLICABLE',
    legacyFallbackAllowed: false,
  })),
)

export function findOrderProductionTemplateAdoption(moduleId) {
  return orderProductionBaseDataTemplateAdoption.find(item => item.moduleId === moduleId) || null
}

export const orderProductionNonRegressionScope = Object.freeze({
  historicalProtectedModules: Object.freeze([...HISTORICAL_PROTECTED_MODULES]),
  wave1Modules: Object.freeze([...WAVE1_MODULES]),
  userValidatedModules: Object.freeze([...USER_VALIDATED_MODULES]),
  excludedDriftRepair: Object.freeze(['procurement']),
  productionWritesAuthorized: false,
  recoveryAuthorized: false,
})
