export const FORMAL_PRICE_APPROVAL_SCENARIO_VERSION = 'V1.14.2.8.7.3'

const scenario = ({ scenarioCode, scenarioType, title, inquiryNo, supplierCount, quotationCount, currency,
  evidenceComplete, specialPurchase, missingFields = [], expectedStatus, expectedExplanation }) => Object.freeze({
  scenarioCode, scenarioType, title,
  scenarioData: Object.freeze({ inquiryNo, supplierCount, quotationCount, currency, evidenceComplete,
    specialPurchase, missingFields: Object.freeze(missingFields) }),
  expectedResult: Object.freeze({ status: expectedStatus, explanation: expectedExplanation }),
  dataMode: 'synthetic_acceptance_data', productionData: false, autoDecisionEnabled: false,
  businessObjectCreated: false, approvalObjectCreated: false, workflowStarted: false, businessWriteCount: 0,
})

export const FORMAL_PRICE_APPROVAL_SCENARIOS = Object.freeze([
  scenario({ scenarioCode: 'normal_complete_quotes', scenarioType: 'normal', title: '正常场景：多供应商完整报价',
    inquiryNo: 'SIM-PI-NORMAL-001', supplierCount: 3, quotationCount: 3, currency: 'CNY', evidenceComplete: true,
    specialPurchase: false, expectedStatus: 'ready_for_manual_review', expectedExplanation: '报价证据完整，可进入人工价格评审验证' }),
  scenario({ scenarioCode: 'special_single_supplier', scenarioType: 'special', title: '特殊场景：单一供应商采购',
    inquiryNo: 'SIM-PI-SPECIAL-001', supplierCount: 1, quotationCount: 1, currency: 'CNY', evidenceComplete: true,
    specialPurchase: true, expectedStatus: 'manual_confirmation_required', expectedExplanation: '允许特殊采购验证，但必须人工确认单一来源原因' }),
  scenario({ scenarioCode: 'exception_incomplete_evidence', scenarioType: 'exception', title: '异常场景：报价证据缺失',
    inquiryNo: 'SIM-PI-EXCEPTION-001', supplierCount: 2, quotationCount: 2, currency: null, evidenceComplete: false,
    specialPurchase: false, missingFields: ['currency', 'deliveryDays'], expectedStatus: 'blocked', expectedExplanation: '币种和交期缺失，必须阻断并补充证据' }),
])

export const FORMAL_PRICE_APPROVAL_SCENARIO_MODEL = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_SCENARIO',
  version: FORMAL_PRICE_APPROVAL_SCENARIO_VERSION,
  scenarioStatus: 'ready_for_user_acceptance',
  scenarios: FORMAL_PRICE_APPROVAL_SCENARIOS,
  scenarioCount: 3,
  normalScenarioCount: 1,
  specialScenarioCount: 1,
  exceptionScenarioCount: 1,
  scenarioDataMeansProductionData: false,
  expectedResultMeansAutoDecision: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalScenarioModel(model = FORMAL_PRICE_APPROVAL_SCENARIO_MODEL) {
  const types = model.scenarios.map((item) => item.scenarioType).sort().join('|')
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_SCENARIO'
    && model.scenarioStatus === 'ready_for_user_acceptance' && model.scenarioCount === 3
    && model.normalScenarioCount === 1 && model.specialScenarioCount === 1 && model.exceptionScenarioCount === 1
    && types === 'exception|normal|special'
    && model.scenarios.every((item) => item.dataMode === 'synthetic_acceptance_data' && item.productionData === false
      && item.autoDecisionEnabled === false && item.businessObjectCreated === false && item.approvalObjectCreated === false
      && item.workflowStarted === false && item.businessWriteCount === 0)
    && model.scenarioDataMeansProductionData === false && model.expectedResultMeansAutoDecision === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
