import { getTrace } from './runtimeTracer.js'

function groupByEvent(traces) {
  const map = {}

  for (const trace of traces) {
    if (!map[trace.event]) map[trace.event] = []
    map[trace.event].push(trace)
  }

  return map
}

function calculateDurations(traces) {
  const durations = []

  for (let i = 1; i < traces.length; i++) {
    durations.push({
      from: traces[i - 1].event,
      to: traces[i].event,
      delta: traces[i].time - traces[i - 1].time,
    })
  }

  return durations
}

function extractErrors(traces) {
  const clusters = {}

  for (const trace of traces) {
    if (!trace.event.includes('error')) continue

    clusters[trace.event] = clusters[trace.event] || {
      event: trace.event,
      count: 0,
      samples: [],
    }
    clusters[trace.event].count += 1
    clusters[trace.event].samples.push(trace)
  }

  return Object.values(clusters)
}

function buildChain(traces) {
  return traces.map((trace) => trace.event).join(' -> ')
}

function summarizePerformance(durations) {
  const max = durations.reduce(
    (slowest, item) => (item.delta > slowest.delta ? item : slowest),
    { from: '', to: '', delta: 0 }
  )
  const total = durations.reduce((sum, item) => sum + item.delta, 0)

  return {
    slowestStep: max,
    average: durations.length ? total / durations.length : 0,
    max: max.delta,
  }
}

export function analyzeTrace() {
  const traces = getTrace()
  const durations = calculateDurations(traces)

  return {
    total: traces.length,
    grouped: groupByEvent(traces),
    durations,
    errors: extractErrors(traces),
    chain: buildChain(traces),
    performance: summarizePerformance(durations),
  }
}
