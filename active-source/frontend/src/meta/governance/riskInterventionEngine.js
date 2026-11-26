import { processRealWorldFeedback } from '../reality/realityFeedbackEngine.js'

export function detectBusinessAnomalies(context = {}) {
  const feedback = context.feedback || {}
  const anomalies = []

  if (Number(feedback.cashPressure || 0) > 0.5) anomalies.push('CASHFLOW_PRESSURE')
  if (Number(feedback.supplierDelayRate || 0) > 0.25) anomalies.push('SUPPLY_CHAIN_DELAY')
  if (Number(feedback.approvalDelayRate || 0) > 0.3) anomalies.push('APPROVAL_DELAY')
  if (context.decision?.risk?.level === 'HIGH') anomalies.push('HIGH_DECISION_RISK')

  return {
    anomalies,
    severity: anomalies.length >= 3 ? 'HIGH' : anomalies.length > 0 ? 'MEDIUM' : 'LOW',
  }
}

export function preventBadExecutionPaths(context = {}) {
  const anomaly = detectBusinessAnomalies(context)
  const reality = context.reality || processRealWorldFeedback(context)
  const blocked = anomaly.severity === 'HIGH' || reality.policyBridge?.behavioralRules?.allowed === false

  return {
    blocked,
    action: blocked ? 'PREVENT_EXECUTION_PATH' : 'MONITOR_EXECUTION_PATH',
    reason: blocked ? anomaly.anomalies.join(', ') || 'REALITY_POLICY_BLOCK' : 'NO_CRITICAL_PATH_RISK',
  }
}

export function autoRollbackRiskyActions(context = {}) {
  const prevention = preventBadExecutionPaths(context)

  return {
    rollbackRequired: prevention.blocked,
    rollbackPlan: prevention.blocked
      ? [
          { action: 'RESTORE_PREVIOUS_WORKFLOW_STATE' },
          { action: 'REVERSE_PENDING_EXECUTION' },
          { action: 'REQUIRE_MANUAL_REVIEW' },
        ]
      : [],
  }
}

export function detectAndIntervene(context = {}) {
  return {
    mode: 'V29_RISK_INTERVENTION',
    anomaly: detectBusinessAnomalies(context),
    prevention: preventBadExecutionPaths(context),
    rollback: autoRollbackRiskyActions(context),
  }
}
