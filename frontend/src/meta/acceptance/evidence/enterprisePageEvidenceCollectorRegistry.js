export const COLLECTOR_REGISTRY_VERSION = 'PCE-PAGE-EVIDENCE-COLLECTORS-V1.0'
const registry = new Map()
const forbiddenActions = /^(create|update|delete|submit|approve|execute|post)$/i

export function registerEvidenceCollector(collector) {
  if (!collector?.collectorCode || !collector?.evidenceType || !Array.isArray(collector.supportedChecks) || typeof collector.collect !== 'function') throw new Error('INVALID_EVIDENCE_COLLECTOR')
  if (registry.has(collector.collectorCode)) throw new Error(`DUPLICATE_COLLECTOR:${collector.collectorCode}`)
  if (collector.executionMode !== 'read_only' || collector.supportedActions?.some(action => forbiddenActions.test(action))) throw new Error(`COLLECTOR_NOT_READ_ONLY:${collector.collectorCode}`)
  registry.set(collector.collectorCode, Object.freeze({ ...collector, supportedChecks: Object.freeze([...collector.supportedChecks]) }))
  return collector
}
export const listEvidenceCollectors = () => Object.freeze([...registry.values()])
export const findCollectorForCheck = checkId => [...registry.values()].find(item => item.supportedChecks.includes(checkId)) || null
export const clearEvidenceCollectorRegistryForTests = () => registry.clear()
