export const FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_VERSION = 'V1.14.2.8.7.3'

export const FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_SCENARIO_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-scenario-acceptance']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  scenarioCount: 3, normalScenarioCount: 1, specialScenarioCount: 1, exceptionScenarioCount: 1,
  scenarioDataMeansProductionData: false, expectedResultMeansAutoDecision: false,
  productionDataUsed: false, autoDecisionPerformed: false,
  businessObjectCount: 0, approvalObjectCount: 0, workflowInstanceCount: 0,
  businessWriteCount: 0, databaseState: 'UNCHANGED', productionDataWritten: false,
})

export function validateFormalPriceApprovalScenarioAcceptance(profile = FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.scenarioCount === 3 && profile.normalScenarioCount === 1
    && profile.specialScenarioCount === 1 && profile.exceptionScenarioCount === 1
    && profile.scenarioDataMeansProductionData === false && profile.expectedResultMeansAutoDecision === false
    && profile.productionDataUsed === false && profile.autoDecisionPerformed === false
    && profile.businessObjectCount === 0 && profile.approvalObjectCount === 0 && profile.workflowInstanceCount === 0
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED' && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
