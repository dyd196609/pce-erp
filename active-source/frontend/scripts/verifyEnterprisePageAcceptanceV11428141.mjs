import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  ENTERPRISE_PAGE_ACCEPTANCE_DIMENSIONS,
  ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION,
  ENTERPRISE_PAGE_DATA_PROTECTION_POLICY,
  ENTERPRISE_PAGE_TEMPLATE,
  evaluateEnterprisePageReleaseGate,
} from '../src/meta/acceptance/enterprisePageAcceptanceStandard.js'
import { SCMEnterpriseAcceptanceMatrixV11428141 } from '../src/meta/acceptance/enterprisePageAcceptanceMatrix.js'
import { SCM_PAGE_PERFORMANCE_BUDGET } from '../src/meta/runtime/scmPagePerformanceDiagnostic.js'
import { writeScmRealBusinessChainReport } from './verifyScmRealBusinessChainV11428141.mjs'

const VERSION = ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const outputDir = join(frontendRoot, 'test-results', 'enterprise-page-acceptance-v11428141')
const databasePath = join(repositoryRoot, 'backend', 'db.sqlite3')
const source = (path) => readFileSync(join(repositoryRoot, path), 'utf8')
const hashFile = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')
const writeJson = (name, value) => writeFileSync(join(outputDir, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')

const databaseHashBefore = hashFile(databasePath)
const routerSource = source('frontend/src/router/index.js')
const shellSource = source('frontend/src/meta/components/PceListPageShell.vue')
const contextSource = source('frontend/src/meta/components/ScmStandardPageContext.vue')
const performanceSource = source('frontend/src/meta/runtime/scmPagePerformanceDiagnostic.js')
const standardSource = source('frontend/src/meta/acceptance/enterprisePageAcceptanceStandard.js')
const matrixSource = source('frontend/src/meta/acceptance/enterprisePageAcceptanceMatrix.js')
const manualTemplateSource = source('frontend/src/meta/acceptance/Enterprise_Page_Manual_Acceptance_Template.md')

const routeRegistered = (pageUrl) => routerSource.includes(`path: '${pageUrl.slice(1)}'`)
  || routerSource.includes(`path: '${pageUrl.slice(1).replace(/s$/, '')}'`)
const requiredRegions = ['page-identity-region', 'finance-operation-summary', 'business-process-navigation', 'scm-server-facts', 'scm-business-boundary-protection']

const API_BASE = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'
const apiResults = []
for (const page of SCMEnterpriseAcceptanceMatrixV11428141) {
  const startedAt = performance.now()
  try {
    const response = await fetch(`${API_BASE}${page.apiEndpoint}`, { signal: AbortSignal.timeout(8000) })
    await response.arrayBuffer()
    apiResults.push({
      pageCode: page.pageCode,
      runtimePageCode: page.runtimePageCode,
      apiEndpoint: page.apiEndpoint,
      method: 'GET',
      httpStatus: response.status,
      apiTime: Number((performance.now() - startedAt).toFixed(2)),
      result: response.status === 200 ? 'PASS' : 'FAIL',
    })
  } catch (error) {
    apiResults.push({
      pageCode: page.pageCode,
      runtimePageCode: page.runtimePageCode,
      apiEndpoint: page.apiEndpoint,
      method: 'GET',
      httpStatus: 0,
      apiTime: Number((performance.now() - startedAt).toFixed(2)),
      error: error.message,
      result: 'FAIL',
    })
  }
}

const runtimeFieldsPresent = ['routeLoadTime', 'schemaLoadTime', 'apiTime', 'renderTime', 'totalTime']
  .every((field) => performanceSource.includes(field))
const templateRegionsImplemented = requiredRegions.every((region) => shellSource.includes(region) || contextSource.includes(region))
const databaseHashAfterReadChecks = hashFile(databasePath)

const pages = SCMEnterpriseAcceptanceMatrixV11428141.map((page, index) => {
  const api = apiResults.find((item) => item.pageCode === page.pageCode)
  const buttonsComplete = page.buttonRules.length > 0 && page.buttonRules.every((button) =>
    ['buttonName', 'allowedStatus', 'actionType', 'writeScope'].every((field) => Object.prototype.hasOwnProperty.call(button, field)))
  const navigationComplete = Boolean(page.navigation.currentPage?.pageUrl)
    && (index === 0 || Boolean(page.navigation.previousPage?.pageUrl))
    && (index === SCMEnterpriseAcceptanceMatrixV11428141.length - 1 || Boolean(page.navigation.nextPage?.pageUrl))
  const dimensionResults = {
    A: ['pageCode', 'pageName', 'moduleCode', 'businessObject', 'version'].every((field) => Boolean(page[field])),
    B: page.template === ENTERPRISE_PAGE_TEMPLATE && templateRegionsImplemented,
    C: Boolean(page.pageUrl) && routeRegistered(page.pageUrl),
    D: navigationComplete,
    E: page.factSource === 'server' && page.apiEndpoint.startsWith('/api/'),
    F: api?.httpStatus === 200 && ['GET', 'POST', 'PUT', 'DELETE'].every((method) => Boolean(page.apiMethodPolicy[method])),
    G: (index === 0 || Object.prototype.hasOwnProperty.call(page, 'sourceObject')) && (index === 15 || Boolean(page.targetObject)),
    H: page.buttonRules.every((button) => Array.isArray(button.allowedStatus) && button.allowedStatus.length > 0),
    I: buttonsComplete,
    J: page.buttonRules.every((button) => !/(bank|ledger|总账|银行)/i.test(button.writeScope)),
    K: contextSource.includes('服务端事实读取失败') && contextSource.includes('加载失败'),
    L: runtimeFieldsPresent && api.apiTime < (SCM_PAGE_PERFORMANCE_BUDGET.complexPageCodes.includes(page.runtimePageCode) ? 3000 : 1000),
    M: databaseHashBefore === databaseHashAfterReadChecks && ENTERPRISE_PAGE_DATA_PROTECTION_POLICY.productionUserDataWritten === false,
  }
  const checks = page.checks.map((check) => ({
    ...check,
    result: dimensionResults[check.dimension] ? 'PASS' : 'FAIL',
  }))
  const automaticAcceptance = checks.every((check) => check.result === 'PASS') ? 'PASS' : 'FAIL'
  const releaseGate = evaluateEnterprisePageReleaseGate({
    automaticAcceptance,
    manualAcceptance: 'PENDING',
    archiveStatus: 'NOT_ARCHIVED',
  })
  return {
    ...page,
    checks,
    apiResult: api,
    automaticAcceptance,
    manualAcceptance: 'PENDING',
    archiveStatus: 'NOT_ARCHIVED',
    finalAcceptance: 'PENDING_MANUAL_ACCEPTANCE',
    nextPageAllowed: releaseGate.nextPageAllowed,
    releaseBlockingReason: releaseGate.blockingReason,
  }
})

const rules = [
  ['PAGE-STD-001', '统一标准包含A至M共13个验收维度', ENTERPRISE_PAGE_ACCEPTANCE_DIMENSIONS.length === 13],
  ['PAGE-STD-002', '一页一验收范围规则已建立', standardSource.includes('PCE_PAGE_ACCEPTANCE_SCOPE_MUST_BE_SINGLE_PAGE')],
  ['PAGE-STD-003', '自动与人工双通过门禁已建立', standardSource.includes('automaticPassed && manualPassed && archived')],
  ['PAGE-STD-004', 'SCM 16页全部纳入矩阵', pages.length === 16],
  ['PAGE-STD-005', 'SCM页面身份完整', pages.every((page) => page.checks.find((check) => check.dimension === 'A')?.result === 'PASS')],
  ['PAGE-STD-006', '统一页面区域存在', pages.every((page) => page.checks.find((check) => check.dimension === 'B')?.result === 'PASS')],
  ['PAGE-STD-007', '路由和pageCode映射完整', pages.every((page) => page.checks.find((check) => check.dimension === 'C')?.result === 'PASS')],
  ['PAGE-STD-008', '16页流程导航URL完整', pages.every((page) => page.checks.find((check) => check.dimension === 'D')?.result === 'PASS')],
  ['PAGE-STD-009', '所有事实来源为server', pages.every((page) => page.factSource === 'server')],
  ['PAGE-STD-010', '16页GET API可访问', apiResults.every((item) => item.result === 'PASS')],
  ['PAGE-STD-011', '对象来源与目标登记完整', pages.every((page) => page.checks.find((check) => check.dimension === 'G')?.result === 'PASS')],
  ['PAGE-STD-012', '按钮四字段登记完整', pages.every((page) => page.checks.find((check) => check.dimension === 'I')?.result === 'PASS')],
  ['PAGE-STD-013', '性能五指标和预算存在', runtimeFieldsPresent && performanceSource.includes('normalPageMs: 1000') && performanceSource.includes('complexPageMs: 3000')],
  ['PAGE-STD-014', '人工验收模板完整', ['页面名称', '流程导航', '业务操作', '异常处理', '性能体验', '最终结论'].every((value) => manualTemplateSource.includes(value))],
  ['PAGE-STD-015', '人工验收未完成时禁止进入下一页', pages.every((page) => page.manualAcceptance === 'PENDING' && page.nextPageAllowed === false)],
  ['PAGE-STD-016', '验收过程数据库零写入', databaseHashBefore === databaseHashAfterReadChecks],
  ['PAGE-STD-017', '矩阵显式映射验收编码与运行编码', matrixSource.includes('runtimePageCode')],
].map(([code, name, passed]) => ({ code, name, result: passed ? 'PASS' : 'FAIL' }))

mkdirSync(outputDir, { recursive: true })
const realBusinessChain = writeScmRealBusinessChainReport(outputDir)
const databaseHashAfter = hashFile(databasePath)
const matrixReport = {
  version: VERSION,
  standard: ENTERPRISE_PAGE_TEMPLATE,
  pageCount: pages.length,
  executionType: 'MATRIX_GOVERNANCE_SCAN_WITH_INDEPENDENT_PAGE_RESULTS',
  singlePageFinalAcceptanceRequired: true,
  pages,
  automaticAcceptanceSummary: {
    PASS: pages.filter((page) => page.automaticAcceptance === 'PASS').length,
    FAIL: pages.filter((page) => page.automaticAcceptance === 'FAIL').length,
    UNKNOWN: 0,
  },
  manualAcceptanceSummary: { PASS: 0, FAIL: 0, PENDING: pages.length },
  finalAcceptance: 'PENDING_MANUAL_ACCEPTANCE',
  nextPageAllowed: false,
}
const acceptanceReport = {
  version: VERSION,
  ruleCount: rules.length,
  PASS: rules.filter((rule) => rule.result === 'PASS').length,
  FAIL: rules.filter((rule) => rule.result === 'FAIL').length,
  UNKNOWN: 0,
  rules,
  automaticAcceptance: rules.every((rule) => rule.result === 'PASS') ? 'PASS' : 'FAIL',
  acceptanceMeaning: '统一标准与矩阵治理自动检查通过，不代表16页企业人工操作通过。',
  singlePageFinalAcceptanceRequired: true,
  manualAcceptance: 'PENDING',
  finalAcceptance: 'PENDING_MANUAL_ACCEPTANCE',
  realBusinessChainDiagnosis: realBusinessChain.diagnosis,
  productionUserDataWritten: false,
  businessWriteCount: 0,
  databaseHashBefore,
  databaseHashAfter,
  databaseHashUnchanged: databaseHashBefore === databaseHashAfter,
}

writeJson('scm_enterprise_acceptance_matrix_v11428141.json', matrixReport)
writeJson('enterprise_page_acceptance_automatic_report_v11428141.json', acceptanceReport)

if (acceptanceReport.automaticAcceptance !== 'PASS' || !acceptanceReport.databaseHashUnchanged) {
  throw new Error(`PCE统一页面自动验收失败：${rules.filter((rule) => rule.result === 'FAIL').map((rule) => rule.code).join(', ')}`)
}
console.log(JSON.stringify({
  result: acceptanceReport.automaticAcceptance,
  ruleCount: acceptanceReport.ruleCount,
  PASS: acceptanceReport.PASS,
  FAIL: acceptanceReport.FAIL,
  UNKNOWN: acceptanceReport.UNKNOWN,
  scmPageCount: pages.length,
  scmAutomaticPass: matrixReport.automaticAcceptanceSummary.PASS,
  manualAcceptance: acceptanceReport.manualAcceptance,
  finalAcceptance: acceptanceReport.finalAcceptance,
  realBusinessChainDiagnosis: acceptanceReport.realBusinessChainDiagnosis,
  productionUserDataWritten: false,
  databaseHashUnchanged: acceptanceReport.databaseHashUnchanged,
  outputDir,
}, null, 2))
