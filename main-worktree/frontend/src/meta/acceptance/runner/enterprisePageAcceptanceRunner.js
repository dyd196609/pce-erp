import { collectEnterprisePageEvidence, createEvidenceCollectionPlan, evaluateCollectedEvidence, ENTERPRISE_PAGE_EVIDENCE_ENGINE_VERSION } from '../evidence/enterprisePageEvidenceEngine.js'
import { resolveEnterprisePage } from './enterprisePageResolver.js'
import { resolveEnterpriseAcceptanceTemplate, ENTERPRISE_ACCEPTANCE_TEMPLATE_RESOLVER_VERSION } from './enterpriseAcceptanceTemplateResolver.js'
import { createEnterpriseAcceptanceRunModel, transitionEnterpriseAcceptanceRun } from './enterpriseAcceptanceRunModel.js'

export const ENTERPRISE_PAGE_ACCEPTANCE_RUNNER_VERSION = 'V1.14.2.8.4.22'
const forbiddenAction = /^(create|update|delete|submit|approve|execute|post)$/i

export function assertEnterpriseAcceptanceReadOnly(input = {}) {
  if (input.readonly !== true) throw new Error('RUNNER_READONLY_REQUIRED')
  const actions = input.businessActions || []
  const blocked = actions.find(action => forbiddenAction.test(String(action)))
  if (blocked) throw new Error(`RUNNER_BUSINESS_ACTION_FORBIDDEN:${blocked}`)
  return true
}

export function createRun(input = {}) {
  assertEnterpriseAcceptanceReadOnly(input)
  return createEnterpriseAcceptanceRunModel(input)
}

export function resolvePage(run) {
  const page = resolveEnterprisePage({ pageUrl: run.pageUrl, moduleCode: run.moduleCode })
  run.page = page
  if (page.result !== 'PASS') throw new Error(page.error?.code || 'PAGE_RESOLUTION_UNKNOWN')
  run.pageCode = page.pageCode
  run.moduleCode = page.moduleCode
  return page
}

export function resolveTemplate(run) {
  const template = resolveEnterpriseAcceptanceTemplate(run.page || {})
  run.template = template
  if (template.result !== 'PASS') throw new Error(template.error?.code || 'TEMPLATE_RESOLUTION_UNKNOWN')
  run.templateCode = template.templateCode
  return template
}

export function generateReport(run) {
  const summary = run.evaluation?.acceptance?.summary || { total: 0, PASS: 0, FAIL: 0, 'N/A': 0, UNKNOWN: 0 }
  run.report = Object.freeze({
    runnerVersion: ENTERPRISE_PAGE_ACCEPTANCE_RUNNER_VERSION,
    runId: run.runId, pageCode: run.pageCode, pageUrl: run.pageUrl, templateCode: run.templateCode, mode: run.mode,
    status: run.status, result: run.result, collectorCount: run.collectorCount, evidenceCount: run.evidenceCount,
    summary, startedAt: run.startedAt, completedAt: run.completedAt,
    productionUserDataWritten: run.runtimeContext?.databaseProtection?.productionUserDataWritten ?? false,
    businessWriteCount: run.runtimeContext?.databaseProtection?.businessWriteCount ?? 0,
  })
  return run.report
}

export async function archive(run, options = {}) {
  if (typeof options.archiveWriter !== 'function') throw new Error('RUNNER_ARCHIVE_WRITER_REQUIRED')
  run.archiveResult = await options.archiveWriter(run, {
    ...options,
    runnerVersion: ENTERPRISE_PAGE_ACCEPTANCE_RUNNER_VERSION,
    templateResolverVersion: ENTERPRISE_ACCEPTANCE_TEMPLATE_RESOLVER_VERSION,
    evidenceEngineVersion: ENTERPRISE_PAGE_EVIDENCE_ENGINE_VERSION,
  })
  transitionEnterpriseAcceptanceRun(run, 'ARCHIVED')
  return run.archiveResult
}

export async function execute(run, options = {}) {
  try {
    assertEnterpriseAcceptanceReadOnly({ readonly: run.readonly, businessActions: options.businessActions || [] })
    transitionEnterpriseAcceptanceRun(run, 'RUNNING')
    resolvePage(run)
    resolveTemplate(run)
    const supplied = options.runtimeContext || (typeof options.runtimeContextProvider === 'function' ? await options.runtimeContextProvider(run) : {})
    assertEnterpriseAcceptanceReadOnly({ readonly: run.readonly, businessActions: supplied.businessActions || [] })
    run.runtimeContext = supplied.runtimeContext || supplied
    run.runtimeArtifacts = supplied.runtimeContext ? supplied : { runtimeContext: supplied }
    run.plan = createEvidenceCollectionPlan({
      pageIdentity: { pageCode: run.pageCode, pageName: run.page.pageName, pageUrl: run.page.pageUrl, moduleCode: run.moduleCode, businessObject: run.page.businessObject, pageVersion: run.page.pageVersion },
      moduleCode: run.moduleCode, templateCode: run.templateCode, acceptanceRunId: run.runId,
      dataMode: run.mode === 'canary' ? 'canary_acceptance' : 'production',
    })
    run.collection = await collectEnterprisePageEvidence(run.plan, run.runtimeContext)
    run.evaluation = evaluateCollectedEvidence(run.collection)
    run.collectorCount = run.plan.collectors.length
    run.evidenceCount = run.collection.evidence.length
    run.result = run.evaluation.status
    transitionEnterpriseAcceptanceRun(run, 'COMPLETED')
    generateReport(run)
    if (options.archiveWriter) await archive(run, options)
    return Object.freeze({ success: run.result === 'PASS', runId: run.runId, pageCode: run.pageCode, templateCode: run.templateCode, mode: run.mode, evidenceCount: run.evidenceCount, result: run.result, archivePath: run.archiveResult?.archiveDir || '', run })
  } catch (error) {
    run.error = { code: String(error.message || error).split(':')[0], message: error.message || String(error) }
    run.result = 'FAIL'
    if (run.status === 'CREATED' || run.status === 'RUNNING' || run.status === 'COMPLETED') transitionEnterpriseAcceptanceRun(run, 'FAILED')
    generateReport(run)
    return Object.freeze({ success: false, runId: run.runId, pageCode: run.pageCode, templateCode: run.templateCode, mode: run.mode, evidenceCount: run.evidenceCount, result: 'FAIL', archivePath: '', error: run.error, run })
  }
}
