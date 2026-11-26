import { generateApprovalDecision } from './autoApprovalEngine.js'
import { enforceEnterpriseRules } from './policyDecisionEngine.js'
import { controlRiskDecision } from './riskDecisionController.js'
import { optimizeWorkflowPath, selectBusinessPath } from './businessRoutingAI.js'
import { allocateResources as allocateRuntimeResources } from '../optimization/resourceAllocationAI.js'

export function allocateResources(context = {}) {
  const executionData = context.executionClosedLoop || context.executionData || context
  const currentAllocation = context.optimizationRuntime?.resources || allocateRuntimeResources(executionData)

  return {
    resourceDecision: 'ACTIVE',
    allocationMode: currentAllocation.workloadDistribution?.balanced ? 'KEEP_CURRENT_ALLOCATION' : 'AUTO_REBALANCE',
    resources: currentAllocation,
    recommendation: currentAllocation.workloadDistribution?.recommendation || 'Resource allocation ready',
  }
}

export function autoDecide(context = {}) {
  const approvalDecision = generateApprovalDecision(context)
  const workflowDecision = optimizeWorkflowPath(context)
  const resourceDecision = allocateResources(context)
  const businessDecision = selectBusinessPath(context)
  const policyDecision = enforceEnterpriseRules({
    ...context,
    approvalDecision,
    workflowDecision,
    resourceDecision,
    businessDecision,
  })
  const riskDecision = controlRiskDecision(context)

  return {
    decisionMode: 'ON',
    autoDecision: 'ACTIVE',
    policyDecision: 'ENABLED',
    riskDecisionControl: 'ACTIVE',
    approvalDecision,
    workflowDecision,
    resourceDecision,
    businessDecision,
    policyDecisionResult: policyDecision,
    riskDecision,
    autoExecution: policyDecision.canAutoExecute && riskDecision.action === 'ALLOW_LOW_RISK_EXECUTION'
      ? 'READY'
      : 'CONTROLLED',
    trace: [
      approvalDecision.action,
      workflowDecision.pathStrategy,
      resourceDecision.allocationMode,
      businessDecision.selectedBusinessPath,
      riskDecision.action,
    ],
  }
}
