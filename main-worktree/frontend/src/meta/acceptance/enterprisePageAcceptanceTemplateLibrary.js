import masterTemplate from './templates/enterprise_page_master_template.json' with { type: 'json' }
import commonChecklist from './templates/enterprise_page_common_checklist.json' with { type: 'json' }
import scmTemplate from './templates/scm_business_page_acceptance_template.json' with { type: 'json' }

export const ENTERPRISE_PAGE_ACCEPTANCE_TEMPLATE_LIBRARY_VERSION = 'V1.14.2.8.4.20.7'
export const ENTERPRISE_PAGE_ACCEPTANCE_RESULTS = Object.freeze(['PASS', 'FAIL', 'N/A', 'UNKNOWN'])

const clone = value => JSON.parse(JSON.stringify(value))

export function createEnterprisePageAcceptanceRun({ pageIdentity, moduleCode, acceptanceRunId }) {
  const template = clone(masterTemplate)
  template.pageIdentity = { ...template.pageIdentity, ...pageIdentity, moduleCode: moduleCode || pageIdentity?.moduleCode || '' }
  template.execution.acceptanceRunId = acceptanceRunId || ''
  template.checks = commonChecklist.checks.map(check => ({
    ...clone(check),
    result: 'UNKNOWN',
    evidenceRefs: [],
    reason: '尚未执行',
    naReason: '',
    confirmedBy: '',
  }))
  if (template.pageIdentity.moduleCode === 'SCM') {
    template.checks.push(...scmTemplate.scmChecks.map(check => ({
      ...clone(check),
      family: 'scm-business',
      result: 'UNKNOWN',
      evidenceRefs: [],
      reason: '尚未执行',
      naReason: '',
      confirmedBy: '',
    })))
  }
  template.summary.total = template.checks.length
  template.summary.UNKNOWN = template.checks.length
  return template
}

export function evaluateEnterprisePageAcceptance(run, submittedChecks = []) {
  const submittedById = new Map(submittedChecks.map(check => [check.id, check]))
  const checks = run.checks.map(expected => {
    const submitted = submittedById.get(expected.id)
    if (!submitted) return { ...expected, result: 'UNKNOWN', reason: '验收结果缺失' }
    const result = ENTERPRISE_PAGE_ACCEPTANCE_RESULTS.includes(submitted.result) ? submitted.result : 'UNKNOWN'
    if (result === 'N/A' && (!String(submitted.naReason || '').trim() || !String(submitted.confirmedBy || '').trim())) {
      return { ...expected, ...submitted, result: 'FAIL', reason: 'N/A必须填写原因和确认人' }
    }
    return { ...expected, ...submitted, result }
  })
  const count = result => checks.filter(check => check.result === result).length
  const summary = {
    total: checks.length,
    PASS: count('PASS'),
    FAIL: count('FAIL'),
    'N/A': count('N/A'),
    UNKNOWN: count('UNKNOWN'),
  }
  const blockingReasons = []
  if (summary.FAIL) blockingReasons.push(`FAIL=${summary.FAIL}`)
  if (summary.UNKNOWN) blockingReasons.push(`UNKNOWN=${summary.UNKNOWN}`)
  if (run.execution?.manualAcceptance !== 'PASS') blockingReasons.push('人工验收未通过')
  if (run.execution?.archiveStatus !== 'ARCHIVED') blockingReasons.push('验收未归档')
  return Object.freeze({
    ...clone(run),
    checks,
    summary,
    status: summary.FAIL ? 'FAIL' : summary.UNKNOWN ? 'UNKNOWN' : 'PASS',
    releaseGate: { nextPageAllowed: blockingReasons.length === 0, blockingReasons },
  })
}

export function listEnterprisePageAcceptanceTemplates() {
  return Object.freeze({
    master: clone(masterTemplate),
    commonChecklist: clone(commonChecklist),
    scmBusinessPage: clone(scmTemplate),
  })
}
