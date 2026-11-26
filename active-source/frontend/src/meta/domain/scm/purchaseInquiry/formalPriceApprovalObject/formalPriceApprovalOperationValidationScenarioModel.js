export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO_VERSION = 'V1.14.2.8.7.0'

const scenario = (scenarioCode, title, businessQuestion, evidence, expectedOutcome) => Object.freeze({
  scenarioCode,
  title,
  businessQuestion,
  evidence: Object.freeze(evidence),
  expectedOutcome,
  scenarioStatus: 'ready_for_validation',
  validationMode: 'read_only',
  productionOperation: false,
  businessExecution: false,
  businessWriteCount: 0,
})

export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIOS = Object.freeze([
  scenario('quotation_evidence_review', '报价证据核对', '报价、供应商、币种、交期证据是否完整？', ['supplierQuotation', 'priceApprovalEvidencePackage'], '证据完整性可读，不生成审批对象'),
  scenario('comparison_and_preparation_review', '报价比较与核价准备核对', '报价比较和核价准备是否满足人工评审条件？', ['quotationComparison', 'priceReviewPreparation'], '只给出验证结论，不自动选择供应商'),
  scenario('approval_entry_boundary_review', '审批准入边界核对', '准入、创建冻结和治理门禁是否全部有效？', ['priceApprovalEntryAssessment', 'priceApprovalCreationAssessment'], '仅显示准入状态，不启动审批流程'),
  scenario('zero_write_safety_review', '零写入安全核对', '验证过程是否保持零业务写入和零生产执行？', ['governanceSummary', 'operationReadiness'], '验证通过仍不创建任务或写入数据库'),
])

export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO',
  version: FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO_VERSION,
  scenarioCount: FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIOS.length,
  scenarios: FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIOS,
  operationValidationMeansProductionOperation: false,
  productionOperationEnabled: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalOperationValidationScenario(model = FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO'
    && model.scenarioCount === 4 && model.scenarios.length === 4
    && model.scenarios.every((item) => item.scenarioStatus === 'ready_for_validation' && item.validationMode === 'read_only'
      && item.productionOperation === false && item.businessExecution === false && item.businessWriteCount === 0)
    && model.operationValidationMeansProductionOperation === false && model.productionOperationEnabled === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
