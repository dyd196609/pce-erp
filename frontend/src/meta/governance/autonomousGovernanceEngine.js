import { evaluateDecision } from '../ai/decisionEngine.js'
import { processRealWorldFeedback } from '../reality/realityFeedbackEngine.js'
import { enforcePolicies } from './policyEnforcementEngine.js'
import { optimizeWorkflow } from './workflowOptimizationAI.js'
import { detectAndIntervene } from './riskInterventionEngine.js'
import { runBusinessAutopilot } from './businessAutopilotEngine.js'

export function autoDecide(context = {}) {
  const decision = context.decision || evaluateDecision(context)

  return {
    mode: 'V29_AUTO_DECISION',
    recommendation: decision.recommendation,
    score: decision.score,
    risk: decision.risk,
    autoExecutable: decision.recommendation === 'AUTO_APPROVE' && decision.risk?.level === 'LOW',
  }
}

export function governEnterprise(context = {}) {
  const reality = context.reality || processRealWorldFeedback(context)
  const decisionContext = {
    ...context,
    reality,
  }
  const decisions = autoDecide(decisionContext)
  const policies = enforcePolicies({
    ...decisionContext,
    decision: decisions,
  })
  const workflowOptimizations = optimizeWorkflow(decisionContext)
  const riskInterventions = detectAndIntervene({
    ...decisionContext,
    decision: decisions,
  })
  const autopilot = runBusinessAutopilot({
    ...decisionContext,
    decision: decisions,
  })

  return {
    mode: 'V29_AUTONOMOUS_ENTERPRISE_GOVERNANCE',
    governanceMode: 'ACTIVE',
    autonomousDecisioning: 'ENABLED',
    workflowAutoOptimization: 'ON',
    riskIntervention: 'ACTIVE',
    businessAutopilot: 'ENABLED',
    decisions,
    policies,
    workflowOptimizations,
    riskInterventions,
    autopilot,
    metrics: {
      governanceEfficiencyIndex: Math.min(100, decisions.score + (policies.businessRules.allowed ? 4 : -20)),
      workflowOptimizationScore: workflowOptimizations.score,
      riskInterventionRate: riskInterventions.anomaly.anomalies.length
        ? Math.min(1, riskInterventions.anomaly.anomalies.length / 4)
        : 0,
      autopilotStability: autopilot.stability,
    },
  }
}
