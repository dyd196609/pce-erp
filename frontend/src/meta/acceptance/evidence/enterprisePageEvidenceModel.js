export const EVIDENCE_MODEL_VERSION = 'PCE-PAGE-EVIDENCE-V1.0'
export const EVIDENCE_RESULTS = Object.freeze(['PASS', 'FAIL', 'N/A', 'UNKNOWN'])
export const EVIDENCE_TYPES = Object.freeze(['route','page_identity','dom','api','server_facts','navigation','list_contract','filter','status','action','relationship','performance','security','database_protection','browser','screenshot','trace','manual'])
export const EVIDENCE_SOURCES = Object.freeze(['router','registry','server','browser','filesystem','database_hash','manual'])

export function createEvidence(input = {}) {
  const result = EVIDENCE_RESULTS.includes(input.result) ? input.result : 'UNKNOWN'
  const evidence = {
    evidenceId: String(input.evidenceId || ''), acceptanceRunId: String(input.acceptanceRunId || ''),
    pageCode: String(input.pageCode || ''), checkId: String(input.checkId || ''),
    evidenceType: EVIDENCE_TYPES.includes(input.evidenceType) ? input.evidenceType : 'manual',
    source: EVIDENCE_SOURCES.includes(input.source) ? input.source : 'manual',
    collectedAt: input.collectedAt || new Date().toISOString(), collectorCode: String(input.collectorCode || ''),
    result, value: input.value ?? null, expectedValue: input.expectedValue ?? null,
    evidenceRefs: Array.isArray(input.evidenceRefs) ? [...input.evidenceRefs] : [],
    error: input.error || null, metadata: { ...(input.metadata || {}) },
    naReason: String(input.naReason || ''), confirmedBy: String(input.confirmedBy || ''),
  }
  if (!evidence.evidenceId || !evidence.acceptanceRunId || !evidence.pageCode || !evidence.checkId || !evidence.collectorCode) throw new Error('EVIDENCE_REQUIRED_FIELD_MISSING')
  if (result === 'N/A' && (!evidence.naReason || !evidence.confirmedBy || evidence.evidenceRefs.length === 0)) {
    evidence.result = 'FAIL'; evidence.error = { code: 'INVALID_NA', message: 'N/A必须填写原因、确认人和证据引用' }
  }
  return Object.freeze(evidence)
}

export function assertUniqueEvidenceIds(evidence = []) {
  const ids = evidence.map(item => item.evidenceId)
  if (new Set(ids).size !== ids.length) throw new Error('DUPLICATE_EVIDENCE_ID')
  return evidence
}
