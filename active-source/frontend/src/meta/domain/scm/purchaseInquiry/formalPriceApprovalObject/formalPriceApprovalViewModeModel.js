export const FORMAL_PRICE_APPROVAL_VIEW_MODE_VERSION = 'V1.14.2.8.7.4'

export const FORMAL_PRICE_APPROVAL_VIEW_MODES = Object.freeze([
  Object.freeze({ modeCode: 'business_view', label: '业务视图', audience: 'purchase_business_user',
    description: '展示询价、报价、比较、核价准备、业务导航和场景案例', executionPermission: false }),
  Object.freeze({ modeCode: 'acceptance_view', label: '开发验收视图', audience: 'developer_acceptance_user',
    description: '展示模型、规则、Guard、治理状态和验收证据', executionPermission: false }),
])

export const FORMAL_PRICE_APPROVAL_VIEW_MODE = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_MODE',
  version: FORMAL_PRICE_APPROVAL_VIEW_MODE_VERSION,
  defaultMode: 'business_view',
  modes: FORMAL_PRICE_APPROVAL_VIEW_MODES,
  modeCount: 2,
  businessViewMeansAcceptanceView: false,
  hiddenMeansDeleted: false,
  governanceModelCountPreserved: true,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalViewMode(model = FORMAL_PRICE_APPROVAL_VIEW_MODE) {
  const codes = model.modes.map((item) => item.modeCode).sort().join('|')
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_VIEW_MODE'
    && model.defaultMode === 'business_view' && model.modeCount === 2
    && codes === 'acceptance_view|business_view'
    && model.modes.every((mode) => mode.executionPermission === false)
    && model.businessViewMeansAcceptanceView === false && model.hiddenMeansDeleted === false
    && model.governanceModelCountPreserved === true
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
