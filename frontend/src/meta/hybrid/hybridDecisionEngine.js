import { evaluateDecision } from '../ai/decisionEngine.js'
import { simulateHumanBehavior } from '../human/humanBehaviorOS.js'

const trustHistory = []

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, Math.round(value)))
}

function normalizeHumanDecision(decision) {
  if (decision === 'PRIORITIZE') return 'APPROVE'
  if (decision === 'DELAY') return 'DEFER'
  return decision || 'DEFER'
}

function normalizeAiDecision(decision) {
  if (decision === 'AUTO_APPROVE') return 'APPROVE'
  return decision || 'DEFER'
}

function historicalAccuracy(actor) {
  const entries = trustHistory.filter((item) => item.actor === actor)
  if (entries.length === 0) return actor === 'AI' ? 72 : 68

  const success = entries.filter((item) => item.outcome === 'SUCCESS').length
  return clamp((success / entries.length) * 100)
}

export function calculateTrustWeights(context = {}) {
  const humanReliability = clamp(
    historicalAccuracy('HUMAN') +
    (context.human?.emotion?.confidence || 60) * 0.18 -
    (context.human?.emotion?.stressLevel || 50) * 0.12
  )
  const aiReliability = clamp(
    historicalAccuracy('AI') +
    (context.ai?.score || 60) * 0.16 -
    ((context.ai?.risk?.value || 0.2) * 100) * 0.14
  )
  const total = humanReliability + aiReliability || 1

  return {
    humanReliability,
    aiReliability,
    humanWeight: Number((humanReliability / total).toFixed(2)),
    aiWeight: Number((aiReliability / total).toFixed(2)),
    historicalAccuracy: {
      human: historicalAccuracy('HUMAN'),
      ai: historicalAccuracy('AI'),
    },
  }
}

export function resolveConflict({ humanDecision, aiDecision, risk, trustScore, historicalAccuracy: accuracy } = {}) {
  if (risk?.level === 'HIGH') {
    return {
      decision: 'DEFER',
      authority: 'RISK_CONTROL',
      reason: 'high risk requires human review',
    }
  }

  if (trustScore.aiWeight > trustScore.humanWeight + 0.12 && accuracy.ai >= accuracy.human) {
    return {
      decision: aiDecision,
      authority: 'AI_WEIGHTED',
      reason: 'AI reliability is higher for this decision',
    }
  }

  if (trustScore.humanWeight > trustScore.aiWeight + 0.12) {
    return {
      decision: humanDecision,
      authority: 'HUMAN_WEIGHTED',
      reason: 'human reliability is higher for this context',
    }
  }

  return {
    decision: humanDecision === 'APPROVE' && aiDecision === 'DEFER' ? 'DEFER' : aiDecision,
    authority: 'SHARED_GOVERNANCE',
    reason: 'balanced trust resolved through conservative shared decision',
  }
}

export function fuseDecisions(human, ai, trust = calculateTrustWeights({ human, ai })) {
  const humanDecision = normalizeHumanDecision(human?.cognition?.predictedDecision)
  const aiDecision = normalizeAiDecision(ai?.recommendation)
  const agreement = humanDecision === aiDecision
  const confidence = clamp(
    (human?.cognition?.decisionIndex || 60) * trust.humanWeight +
    (ai?.score || 60) * trust.aiWeight
  )

  if (agreement) {
    return {
      decision: humanDecision,
      agreement,
      confidence,
      authority: 'CONSENSUS',
      reason: 'human and AI decisions agree',
    }
  }

  const conflict = resolveConflict({
    humanDecision,
    aiDecision,
    risk: ai?.risk,
    trustScore: trust,
    historicalAccuracy: trust.historicalAccuracy,
  })

  return {
    ...conflict,
    agreement,
    confidence,
    humanDecision,
    aiDecision,
  }
}

export function buildCollaborativeExecution(human, ai, fused) {
  const timeline = [
    {
      actor: 'HUMAN',
      action: fused.decision === 'APPROVE' ? 'PARTIAL_APPROVAL' : 'REVIEW_DECISION',
      status: human?.workflowImpact?.predictedDelay ? 'SLOW_PATH' : 'READY',
    },
    {
      actor: 'AI',
      action: fused.decision === 'APPROVE' ? 'EXECUTE_SUB_ACTIONS' : 'PREPARE_OPTIONS',
      status: ai?.policy?.blocked ? 'GATED' : 'READY',
    },
    {
      actor: 'SHARED',
      action: 'UPDATE_WORKFLOW_STATE',
      status: fused.decision,
    },
  ]

  return {
    mode: 'COLLABORATIVE_EXECUTION_SIMULATION',
    sharedWorkflowState: fused.decision === 'APPROVE' ? 'READY_TO_EXECUTE' : 'WAITING_FOR_ALIGNMENT',
    timeline,
    sideEffect: 'NONE',
  }
}

export function recordHybridOutcome(actor, outcome, payload = {}) {
  trustHistory.push({
    actor,
    outcome,
    payload,
    timestamp: Date.now(),
  })
}

export function getHybridTrustHistory() {
  return trustHistory
}

export function hybridDecision(context = {}) {
  const ai = context.ai || evaluateDecision(context)
  const human = context.human || simulateHumanBehavior({
    ...context,
    decision: ai,
  })
  const trust = calculateTrustWeights({
    ...context,
    human,
    ai,
  })
  const fused = fuseDecisions(human, ai, trust)
  const execution = buildCollaborativeExecution(human, ai, fused)

  return {
    mode: 'V13.9_HUMAN_AI_HYBRID_CIVILIZATION_OS',
    human,
    ai,
    fused,
    trust,
    execution,
    conflict: {
      detected: fused.agreement === false,
      humanDecision: fused.humanDecision || normalizeHumanDecision(human?.cognition?.predictedDecision),
      aiDecision: fused.aiDecision || normalizeAiDecision(ai?.recommendation),
      resolver: fused.authority,
      reason: fused.reason,
    },
  }
}
