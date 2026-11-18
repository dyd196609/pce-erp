import { evaluateEnterprisePageAcceptance } from '../enterprisePageAcceptanceTemplateLibrary.js'
import { createEvidence, assertUniqueEvidenceIds } from './enterprisePageEvidenceModel.js'
import { listEvidenceCollectors } from './enterprisePageEvidenceCollectorRegistry.js'
import { createEvidenceCollectionPlan as buildPlan } from './enterprisePageEvidencePlan.js'

export const ENTERPRISE_PAGE_EVIDENCE_ENGINE_VERSION = 'V1.14.2.8.4.21'
const sourceByType = Object.freeze({ route: 'router', page_identity: 'registry', browser: 'browser', database_protection: 'database_hash' })

export const createEvidenceCollectionPlan = buildPlan

export async function collectEnterprisePageEvidence(plan, runtimeContext = {}) {
  const evidence = []
  for (const planned of plan.checks) {
    const collector = listEvidenceCollectors().find(item => item.collectorCode === planned.collectorCode)
    let collected
    try {
      collected = collector ? await collector.collect(runtimeContext, planned) : { result: 'UNKNOWN', error: { code: 'COLLECTOR_MISSING', message: planned.collectorCode || '未登记采集器' } }
    } catch (error) {
      collected = { result: 'UNKNOWN', error: { code: 'COLLECTOR_ERROR', message: error instanceof Error ? error.message : String(error) } }
    }
    const evidenceRef = `${plan.acceptanceRunId}/${planned.checkId}.json`
    evidence.push(createEvidence({
      evidenceId: `${plan.acceptanceRunId}:${planned.checkId}`,
      acceptanceRunId: plan.acceptanceRunId,
      pageCode: plan.pageIdentity.pageCode,
      checkId: planned.checkId,
      evidenceType: planned.evidenceType,
      source: sourceByType[planned.evidenceType] || (planned.evidenceType === 'api' || planned.evidenceType === 'server_facts' ? 'server' : 'browser'),
      collectorCode: planned.collectorCode || 'UNREGISTERED_COLLECTOR',
      result: collected?.result || 'UNKNOWN',
      value: collected?.value ?? null,
      expectedValue: collected?.expectedValue ?? null,
      evidenceRefs: collected?.evidenceRefs?.length ? collected.evidenceRefs : [evidenceRef],
      error: collected?.error || null,
      metadata: { dataMode: plan.dataMode, readOnly: true, ...(collected?.metadata || {}) },
      naReason: collected?.naReason,
      confirmedBy: collected?.confirmedBy,
    }))
  }
  assertUniqueEvidenceIds(evidence)
  return Object.freeze({ plan, evidence: Object.freeze(evidence), collectedAt: new Date().toISOString() })
}

export function evaluateCollectedEvidence(collection) {
  const submitted = collection.evidence.map(item => ({
    id: item.checkId,
    result: item.result,
    evidenceRefs: item.evidenceRefs,
    reason: item.error?.message || '',
    naReason: item.naReason,
    confirmedBy: item.confirmedBy,
  }))
  const acceptance = evaluateEnterprisePageAcceptance(collection.plan.run, submitted)
  return Object.freeze({ ...collection, acceptance, status: acceptance.status })
}

export async function archiveEnterprisePageEvidence(evaluated, options = {}) {
  if (typeof options.archiveWriter !== 'function') throw new Error('ARCHIVE_WRITER_REQUIRED')
  return options.archiveWriter(evaluated, options)
}
