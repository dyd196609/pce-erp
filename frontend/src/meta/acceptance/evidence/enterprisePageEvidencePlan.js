import { createEnterprisePageAcceptanceRun } from '../enterprisePageAcceptanceTemplateLibrary.js'
import { findCollectorForCheck, listEvidenceCollectors } from './enterprisePageEvidenceCollectorRegistry.js'
import { registerScmBusinessPageEvidenceCollectors } from './scmBusinessPageEvidenceCollectors.js'

export const ENTERPRISE_PAGE_EVIDENCE_PLAN_VERSION = 'V1.14.2.8.4.21'

export function createEvidenceCollectionPlan({ pageIdentity, pageCode, pageName, pageUrl, moduleCode, businessObject, pageVersion, templateCode, acceptanceRunId, dataMode = 'production' }) {
  registerScmBusinessPageEvidenceCollectors()
  const normalizedIdentity = pageIdentity || { pageCode, pageName, pageUrl, moduleCode, businessObject, pageVersion }
  const run = createEnterprisePageAcceptanceRun({ pageIdentity: normalizedIdentity, moduleCode, acceptanceRunId })
  const collectors = listEvidenceCollectors()
  const checks = run.checks.map((check, index) => {
    const collector = findCollectorForCheck(check.id)
    return Object.freeze({
      checkId: check.id,
      order: index + 1,
      collectorCode: collector?.collectorCode || '',
      evidenceType: collector?.evidenceType || 'manual',
      requiredEvidence: [...(check.requiredEvidence || [])],
      collectorRegistered: Boolean(collector),
    })
  })
  return Object.freeze({
    planVersion: ENTERPRISE_PAGE_EVIDENCE_PLAN_VERSION,
    acceptanceRunId: run.execution.acceptanceRunId,
    pageIdentity: Object.freeze({ ...run.pageIdentity }),
    dataMode,
    templateCode: templateCode || run.templateCode,
    run,
    collectors: Object.freeze(collectors.map(item => Object.freeze({ collectorCode: item.collectorCode, evidenceType: item.evidenceType, executionMode: item.executionMode }))),
    checks: Object.freeze(checks),
    executionOrder: Object.freeze(collectors.map(item => item.collectorCode)),
  })
}
