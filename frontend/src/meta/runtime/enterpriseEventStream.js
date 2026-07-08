import { emitEvent, getEventStream } from '../orchestration/eventBus.js'

const enterpriseEvents = []

function normalizeBusinessEvent(event = {}) {
  return {
    id: event.id || `biz-${Date.now()}-${enterpriseEvents.length}`,
    type: event.type || 'business.transaction',
    module: event.module || event.payload?.module || 'enterprise',
    payload: event.payload || {},
    status: event.status || 'EMITTED',
    consistency: event.consistency || 'CONSISTENT',
    correlationId: event.correlationId || event.payload?.correlationId || `runtime-${Date.now()}`,
    timestamp: event.timestamp || Date.now(),
  }
}

export function emitBusinessEvent(event = {}) {
  const normalized = normalizeBusinessEvent(event)
  enterpriseEvents.unshift(normalized)
  if (enterpriseEvents.length > 120) enterpriseEvents.length = 120

  emitEvent({
    type: normalized.type,
    payload: {
      ...normalized.payload,
      module: normalized.module,
      businessEventId: normalized.id,
    },
    source: normalized.module,
    correlationId: normalized.correlationId,
  })

  return normalized
}

export function propagateCrossModuleActions(result = {}) {
  const updates = result.stateUpdates || []
  return updates.map((update) => emitBusinessEvent({
    type: `${update.module}.stateCommitted`,
    module: update.module,
    payload: update,
    correlationId: result.correlationId,
  }))
}

export function maintainEventConsistency() {
  const stream = getEventStream()
  const missingCorrelation = enterpriseEvents.filter((event) => !event.correlationId).length

  return {
    eventStream: 'ACTIVE',
    totalEvents: enterpriseEvents.length,
    orchestrationEvents: stream.length,
    consistency: missingCorrelation === 0 ? 'CONSISTENT' : 'NEEDS_REVIEW',
  }
}

export function getEnterpriseEventStreamSnapshot() {
  return {
    eventStream: 'ACTIVE',
    events: [...enterpriseEvents],
    consistency: maintainEventConsistency(),
  }
}
