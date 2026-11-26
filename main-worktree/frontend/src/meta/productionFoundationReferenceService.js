import * as legacy from './manufacturing/manufacturingReferenceService.js?legacy'

export * from './manufacturing/manufacturingReferenceService.js?legacy'

const noFormalOptions = () => []

export function getReferenceState() {
  const next = legacy.getReferenceState()
  ;['materials', 'skills', 'shifts', 'workCenters', 'processes', 'routings', 'routingSteps', 'equipment', 'productCategories']
    .forEach((collection) => { next[collection] = [] })
  next.productionFoundationFactSource = 'server_required_localStorage_rejected'
  return next
}

export const getSkillOptions = noFormalOptions
export const getShiftOptions = noFormalOptions
export const getWorkCenterOptions = noFormalOptions
export const getEnabledWorkCenters = noFormalOptions
export const validateWorkCenterExists = () => false
export const getProcessOptions = noFormalOptions
export const getProcessesByIndustry = noFormalOptions
export const getRoutingOptions = noFormalOptions
export const getRoutingSteps = noFormalOptions
export const getRoutingsByIndustry = noFormalOptions
export const getEquipmentOptions = noFormalOptions
export const getEquipmentByWorkCenter = noFormalOptions
export const getProductCategoryOptions = noFormalOptions
export const getProductCategoriesByIndustry = noFormalOptions
