import { defineProcess } from './processDefinitionEngine.js'
import { runWorkflow } from './workflowStateEngine.js'

export function generateProcessTimeline(type = 'purchase', history = []) {
  const process = defineProcess(type)
  const source = history.length
    ? history
    : runWorkflow(type, process.transitions.map((transition) => transition.action)).history

  return source.map((entry, index) => ({
    id: `${type}:timeline:${index + 1}`,
    order: index + 1,
    processType: type,
    from: entry.from,
    to: entry.to,
    action: entry.action,
    role: process.roles[entry.to],
    status: entry.executed ? 'COMPLETED' : 'BLOCKED',
    reason: entry.reason,
    durationMs: entry.executed ? 1000 + index * 250 : 0,
    audit: {
      actor: process.roles[entry.to] || process.roles[entry.from] || 'Process Owner',
      stateChange: `${entry.from}->${entry.to}`,
      consistency: entry.executed ? 'CONSISTENT' : 'BLOCKED',
    },
    timestamp: new Date(Date.now() + index * 1000).toISOString(),
  }))
}

export function buildAuditTrail(type = 'purchase', timeline = generateProcessTimeline(type)) {
  return timeline.map((item) => ({
    auditId: `${item.id}:audit`,
    processType: type,
    action: item.action,
    actor: item.audit.actor,
    stateChange: item.audit.stateChange,
    status: item.status,
    timestamp: item.timestamp,
  }))
}

export function replayTimeline(timeline = []) {
  return timeline.map((item, index) => ({
    replayOrder: index + 1,
    from: item.from,
    to: item.to,
    action: item.action,
    role: item.role,
    replayStatus: item.status === 'COMPLETED' ? 'REPLAYED' : 'BLOCKED',
  }))
}

export function trackTimelinePerformance(timeline = []) {
  const totalDurationMs = timeline.reduce((total, item) => total + Number(item.durationMs || 0), 0)

  return {
    totalDurationMs,
    averageStepDurationMs: timeline.length ? Math.round(totalDurationMs / timeline.length) : 0,
    completedSteps: timeline.filter((item) => item.status === 'COMPLETED').length,
    blockedSteps: timeline.filter((item) => item.status === 'BLOCKED').length,
  }
}

export function trackStateChanges(type = 'purchase', actions = ['SUBMIT', 'APPROVE']) {
  const runtime = runWorkflow(type, actions)

  return {
    type,
    currentState: runtime.currentState,
    blocked: runtime.blocked,
    history: runtime.history,
    timeline: generateProcessTimeline(type, runtime.history),
  }
}

export function visualizeProcessHistory(type = 'purchase', actions = ['SUBMIT', 'APPROVE']) {
  const tracked = trackStateChanges(type, actions)

  return {
    ...tracked,
    auditTrail: buildAuditTrail(type, tracked.timeline),
    replay: replayTimeline(tracked.timeline),
    performance: trackTimelinePerformance(tracked.timeline),
    graph: tracked.timeline.map((item) => `${item.from}->${item.to}`).join(' / '),
  }
}
