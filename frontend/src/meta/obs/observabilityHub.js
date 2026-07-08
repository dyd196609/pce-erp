const events = []

export function logEvent(event = {}) {
  const entry = {
    ...event,
    timestamp: Date.now(),
  }

  events.push(entry)
  console.log('[ProfitOS OBS]', entry)

  return entry
}

export function emit(event = {}) {
  return logEvent(event)
}

export function traceRequest(req = {}) {
  return {
    latency: Date.now(),
    request: req,
  }
}

export function getObservabilityEvents() {
  return events
}
