import * as legacy from './manufacturing/manufacturingFoundationStore.js?legacy'
import {
  LEGACY_LOCAL_COLLECTIONS,
  PRODUCTION_FOUNDATION_AUTHORITY_VERSION,
  assertFormalProductionWriteAllowed,
} from './productionFoundationAuthorityPolicy.js'

export * from './manufacturing/manufacturingFoundationStore.js?legacy'

const noFormalRows = () => []
const noFormalRecord = () => null
const blockedCreate = (collection) => (...args) => assertFormalProductionWriteAllowed(collection, ...args)

export function getFoundationState() {
  const next = legacy.getFoundationState()
  LEGACY_LOCAL_COLLECTIONS.forEach((collection) => { next[collection] = [] })
  next.storageClassification = {
    authorityVersion: PRODUCTION_FOUNDATION_AUTHORITY_VERSION,
    classification: 'LEGACY_DEMO_OR_UI_DRAFT_ONLY',
    formalFactSource: false,
  }
  return next
}

export function getLegacyManufacturingDemoAudit() {
  const snapshot = legacy.getFoundationState()
  return {
    authorityVersion: PRODUCTION_FOUNDATION_AUTHORITY_VERSION,
    storageKey: 'manufacturing-foundation-state-v1',
    classification: 'LEGACY_DEMO_OR_UI_DRAFT_ONLY',
    formalFactSource: false,
    collections: Object.fromEntries(
      LEGACY_LOCAL_COLLECTIONS.map((collection) => [collection, (snapshot[collection] || []).length]),
    ),
  }
}

export const getSkills = noFormalRows
export const getShifts = noFormalRows
export const getMaterials = noFormalRows
export const getMaterialById = noFormalRecord
export const getWorkCenters = noFormalRows
export const getProcesses = noFormalRows
export const getProcessById = noFormalRecord
export const getProcessesByIndustry = noFormalRows
export const getRoutings = noFormalRows
export const getRoutingById = noFormalRecord
export const getRoutingSteps = noFormalRows
export const getRoutingsByIndustry = noFormalRows
export const getEquipmentList = noFormalRows
export const getEquipmentById = noFormalRecord
export const getEquipmentByWorkCenter = noFormalRows
export const getProductCategories = noFormalRows
export const getProductCategoriesByIndustry = noFormalRows

export const createSkill = blockedCreate('skills')
export const updateSkill = blockedCreate('skills')
export const deleteSkill = blockedCreate('skills')
export const createShift = blockedCreate('shifts')
export const updateShift = blockedCreate('shifts')
export const deleteShift = blockedCreate('shifts')
export const createMaterial = blockedCreate('materials')
export const updateMaterial = blockedCreate('materials')
export const deleteMaterial = blockedCreate('materials')
export const createWorkCenter = blockedCreate('workCenters')
export const updateWorkCenter = blockedCreate('workCenters')
export const deleteWorkCenter = blockedCreate('workCenters')
export const createProcess = blockedCreate('processes')
export const updateProcess = blockedCreate('processes')
export const deleteProcess = blockedCreate('processes')
export const createRouting = blockedCreate('routings')
export const updateRouting = blockedCreate('routings')
export const deleteRouting = blockedCreate('routings')
export const addRoutingStep = blockedCreate('routingSteps')
export const updateRoutingStep = blockedCreate('routingSteps')
export const deleteRoutingStep = blockedCreate('routingSteps')
export const createEquipment = blockedCreate('equipment')
export const updateEquipment = blockedCreate('equipment')
export const deleteEquipment = blockedCreate('equipment')
export const createProductCategory = blockedCreate('productCategories')
export const updateProductCategory = blockedCreate('productCategories')
export const deleteProductCategory = blockedCreate('productCategories')
