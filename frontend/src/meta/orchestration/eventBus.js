const handlers = new Map()
const eventStream = []
const maxEvents = 100

function normalizeEvent(event = {}) {
  return {
    id: event.id || `${event.type || 'event'}-${Date.now()}-${eventStream.length}`,
    type: event.type || 'unknown.event',
    payload: event.payload || {},
    source: event.source || event.payload?.module || 'system',
    timestamp: event.timestamp || Date.now(),
    correlationId: event.correlationId || event.payload?.correlationId || `corr-${Date.now()}`,
    depth: Number(event.depth || 0),
  }
}

export function subscribeEvent(type, handler) {
  if (!handlers.has(type)) {
    handlers.set(type, new Set())
  }

  handlers.get(type).add(handler)
  return () => handlers.get(type)?.delete(handler)
}

export function dispatch(type, payload = {}, event = {}) {
  const listeners = [
    ...(handlers.get(type) || []),
    ...(handlers.get('*') || []),
  ]

  listeners.forEach((handler) => {
    handler({
      ...event,
      type,
      payload,
    })
  })
}

export function emitEvent(event = {}) {
  const normalized = normalizeEvent(event)
  eventStream.unshift(normalized)
  if (eventStream.length > maxEvents) {
    eventStream.length = maxEvents
  }

  dispatch(normalized.type, normalized.payload, normalized)
  return normalized
}

export function getEventStream() {
  return [...eventStream]
}

export function clearEventStream() {
  eventStream.length = 0
}
