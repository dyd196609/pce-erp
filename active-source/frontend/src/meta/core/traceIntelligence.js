import { getTrace } from './runtimeTracer.js'

function calcCost(traces) {
  const map = {}

  for (const trace of traces) {
    if (trace.payload?.cost == null) continue

    if (!map[trace.event]) map[trace.event] = []
    map[trace.event].push(trace.payload.cost)
  }

  const result = {}

  for (const key in map) {
    const arr = map[key]
    result[key] = {
      avg: arr.reduce((a, b) => a + b, 0) / arr.length,
      max: Math.max(...arr),
      count: arr.length,
    }
  }

  return result
}

function detectBottlenecks(costMap) {
  const sorted = Object.entries(costMap).sort((a, b) => b[1].avg - a[1].avg)

  return sorted.slice(0, 3).map((item) => ({
    step: item[0],
    avgCost: item[1].avg,
  }))
}

function calculateHealth(costMap, errorCount = 0) {
  let score = 100

  Object.values(costMap).forEach((value) => {
    if (value.avg > 200) score -= 10
    if (value.avg > 500) score -= 20
  })

  score -= errorCount * 5

  return Math.max(0, score)
}

function extractErrors(traces) {
  return traces.filter((trace) => trace.event.includes('error'))
}

function buildInsight(costMap, bottlenecks, health) {
  return {
    summary:
      health > 80
        ? 'System stable'
        : health > 50
          ? 'Performance degradation detected'
          : 'Critical system stress',
    bottlenecks,
    health,
  }
}

export function analyzeIntelligence() {
  const traces = getTrace()
  const costMap = calcCost(traces)
  const errors = extractErrors(traces)
  const bottlenecks = detectBottlenecks(costMap)
  const health = calculateHealth(costMap, errors.length)

  return {
    costMap,
    errors,
    bottlenecks,
    health,
    insight: buildInsight(costMap, bottlenecks, health),
  }
}
