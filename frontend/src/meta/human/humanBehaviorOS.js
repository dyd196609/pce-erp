function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, Math.round(value)))
}

function getCivilization(context = {}) {
  return context.civilization || context.runtime?.civilization || {}
}

function getDecision(context = {}) {
  return context.decision || context.runtime?.decision || {}
}

export function simulateCognitiveDecision(context = {}) {
  const decision = getDecision(context)
  const civilization = getCivilization(context)
  const workflowRisk = decision.risk?.score ?? (decision.risk?.level === 'HIGH' ? 70 : 25)
  const policyStability = civilization.governance?.stabilityControl ?? 75
  const civilizationHealth = civilization.economy?.civilizationKpi?.civilizationHealthIndex ?? 80
  const urgency = Number(context.urgency || context.record?.urgencyScore || 40)
  const decisionIndex = clamp(55 + civilizationHealth * 0.22 + policyStability * 0.15 + urgency * 0.12 - workflowRisk * 0.28)

  let predictedDecision = 'APPROVE'
  if (decisionIndex < 42) predictedDecision = 'REJECT'
  else if (decisionIndex < 58) predictedDecision = 'DELAY'
  else if (decisionIndex > 82) predictedDecision = 'PRIORITIZE'

  return {
    mode: 'COGNITIVE_DECISION_MODEL',
    decisionIndex,
    predictedDecision,
    approveLikelihood: clamp(decisionIndex),
    delayLikelihood: clamp(100 - decisionIndex + workflowRisk * 0.25),
    rejectLikelihood: clamp(workflowRisk - civilizationHealth * 0.2),
    priorityLikelihood: clamp(decisionIndex + urgency * 0.2 - 45),
  }
}

export function simulateEmotionState(context = {}) {
  const civilization = getCivilization(context)
  const societyStability = civilization.society?.stabilityIndex ?? 78
  const migrationPressure = civilization.population?.migrationPressure ?? 20
  const workload = Number(context.workload || context.record?.workload || 55)
  const kpiPressure = Number(context.kpiPressure || context.record?.kpiPressure || 60)
  const stressLevel = clamp(workload * 0.35 + kpiPressure * 0.28 + migrationPressure * 0.2 - societyStability * 0.18 + 32)
  const fatigue = clamp(workload * 0.45 + stressLevel * 0.25 - 12)
  const motivation = clamp(92 - stressLevel * 0.35 + kpiPressure * 0.1)
  const confidence = clamp(societyStability * 0.45 + motivation * 0.35 - fatigue * 0.12 + 20)

  return {
    mode: 'EMOTION_STATE_MODEL',
    stressLevel,
    motivation,
    fatigue,
    confidence,
    emotionalLoad: stressLevel > 70 ? 'HIGH' : stressLevel > 45 ? 'MEDIUM' : 'LOW',
  }
}

export function simulateIncentiveModel(context = {}) {
  const emotion = context.emotion || simulateEmotionState(context)
  const kpiPressure = Number(context.kpiPressure || context.record?.kpiPressure || 60)
  const rewardStrength = Number(context.rewardStrength || context.record?.rewardStrength || 55)
  const riskPreference = clamp(48 + rewardStrength * 0.25 - emotion.stressLevel * 0.18 + emotion.confidence * 0.15)

  return {
    mode: 'INCENTIVE_MODEL',
    kpiPressure,
    rewardStrength,
    riskPreference,
    behaviorShift: riskPreference > 65 ? 'SPEED_UP_DECISION' : riskPreference < 40 ? 'AVOID_RISK' : 'BALANCED',
  }
}

export function simulateGroupDynamics(context = {}) {
  const emotion = context.emotion || simulateEmotionState(context)
  const incentive = context.incentive || simulateIncentiveModel({ ...context, emotion })
  const teamSize = Number(context.teamSize || context.record?.teamSize || 8)
  const collaborationEfficiency = clamp(82 - emotion.fatigue * 0.25 + incentive.rewardStrength * 0.12 - Math.max(0, teamSize - 8) * 1.5)
  const decisionConsistency = clamp(75 + emotion.confidence * 0.2 - emotion.stressLevel * 0.18)
  const polarization = clamp(emotion.stressLevel * 0.32 + teamSize * 1.2 - decisionConsistency * 0.18)
  const managementPattern = collaborationEfficiency > 75
    ? 'COORDINATED'
    : polarization > 45
      ? 'FRAGMENTED'
      : 'DIRECTIVE'

  return {
    mode: 'GROUP_DYNAMICS_MODEL',
    collaborationEfficiency,
    decisionConsistency,
    polarization,
    managementPattern,
    kpiImpact: clamp(collaborationEfficiency * 0.45 + decisionConsistency * 0.35 - polarization * 0.18),
  }
}

export function simulateHumanBehavior(context = {}) {
  const emotion = simulateEmotionState(context)
  const incentive = simulateIncentiveModel({ ...context, emotion })
  const cognition = simulateCognitiveDecision({ ...context, emotion, incentive })
  const group = simulateGroupDynamics({ ...context, emotion, incentive, cognition })

  return {
    mode: 'V13.8_HUMAN_OPERATING_SYSTEM',
    cognition,
    emotion,
    incentive,
    group,
    workflowImpact: {
      predictedDelay: cognition.predictedDecision === 'DELAY' || emotion.fatigue > 70,
      autoPriority: cognition.predictedDecision === 'PRIORITIZE',
      humanRisk: emotion.emotionalLoad === 'HIGH' || group.polarization > 55 ? 'HIGH' : 'NORMAL',
      kpiImpact: group.kpiImpact,
    },
  }
}
