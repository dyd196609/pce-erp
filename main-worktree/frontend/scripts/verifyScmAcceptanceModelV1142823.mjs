import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import template from '../src/meta/acceptance/templates/scmBusinessPageAcceptanceTemplateV2.json' with { type: 'json' }
import { listScmAcceptanceObjects, resolveScmAcceptanceObject } from '../src/meta/acceptance/scm/scmAcceptanceObjectModel.js'
import { SCM_TRACE_ACCEPTANCE_RULES, SCM_TRACE_CHAIN, isReverseScmGeneration } from '../src/meta/acceptance/scm/scmTraceAcceptanceRules.js'
import { SCM_STATUS_ACCEPTANCE_RULES, evaluateScmStatusTransition } from '../src/meta/acceptance/scm/scmStatusAcceptanceRules.js'
import { SCM_ACTION_ACCEPTANCE_RULES, SCM_FINANCIAL_ACTIONS } from '../src/meta/acceptance/scm/scmActionAcceptanceRules.js'
import { SCM_FINANCIAL_BOUNDARY } from '../src/meta/acceptance/scm/scmFinancialBoundaryRules.js'

export const VERSION = 'V1.14.2.8.4.23'
export const TARGET_STATUS = 'SCM_ACCEPTANCE_MODEL_READY'

const requiredObjectFields = ['objectCode', 'objectName', 'module', 'lifecycle', 'sourceObjects', 'targetObjects', 'traceFields', 'statusField', 'actionRules']
const requiredTraceFields = ['sourceObject', 'targetObject', 'relationshipType', 'traceIdField', 'direction']
const expectedLifecycle = Object.freeze({
  SCM_PURCHASE_REQUEST: ['draft', 'submitted', 'approved', 'released', 'closed'],
  SCM_PURCHASE_INQUIRY: ['draft', 'issued', 'quoted', 'evaluated', 'closed'],
  SCM_PURCHASE_ORDER: ['draft', 'approved', 'issued', 'received', 'closed'],
})

const same = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const makeRule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyScmAcceptanceModel() {
  const objects = listScmAcceptanceObjects()
  const completeLifecycles = objects.every(object => same(object.lifecycle, expectedLifecycle[object.objectCode]))
  const traceComplete = SCM_TRACE_ACCEPTANCE_RULES.length === SCM_TRACE_CHAIN.length - 1
    && SCM_TRACE_ACCEPTANCE_RULES.every(rule => requiredTraceFields.every(field => String(rule[field] ?? '').length > 0) && rule.direction === 'forward')
  const statusesComplete = SCM_STATUS_ACCEPTANCE_RULES.length === objects.length
    && SCM_STATUS_ACCEPTANCE_RULES.every(rule => rule.allowedTransitions.length === rule.lifecycle.length - 1)
  const reverseExamples = objects.flatMap(object => object.lifecycle.slice(1).map((status, index) => ({ objectCode: object.objectCode, fromStatus: status, toStatus: object.lifecycle[index] })))
  const reverseForbidden = reverseExamples.every(example => evaluateScmStatusTransition(example).result === 'FAIL')
  const actionComplete = objects.every(object => object.lifecycle.every(status => SCM_ACTION_ACCEPTANCE_RULES.some(rule => rule.objectCode === object.objectCode && rule.status === status)))
    && SCM_ACTION_ACCEPTANCE_RULES.every(rule => rule.policy === 'explicit_whitelist_default_deny' && SCM_FINANCIAL_ACTIONS.every(action => rule.forbiddenActions.includes(action)))
  const financeComplete = SCM_FINANCIAL_BOUNDARY.financeImpactAllowed === false
    && SCM_FINANCIAL_BOUNDARY.productionUserDataWritten === false
    && SCM_FINANCIAL_ACTIONS.every(action => SCM_FINANCIAL_BOUNDARY.forbiddenActions.includes(action))
  const templateInherited = template.extends === 'PCE-ENTERPRISE-PAGE-ACCEPTANCE-MASTER-V1'
    && template.extendsFile === 'enterprise_page_master_template.json'
    && same(template.checks.map(check => check.id), ['SCM-001','SCM-002','SCM-003','SCM-004','SCM-005','SCM-006','SCM-007','SCM-008'])
  const purchaseRequest = resolveScmAcceptanceObject('SCM_PURCHASE_REQUEST')
  const purchaseOrder = resolveScmAcceptanceObject('SCM_PURCHASE_ORDER')
  const rules = Object.freeze([
    makeRule('SCM-MODEL-001', '对象模型存在', objects.length === 3 && objects.every(object => requiredObjectFields.every(field => field in object)), objects.map(object => object.objectCode)),
    makeRule('SCM-MODEL-002', '生命周期完整', completeLifecycles, expectedLifecycle),
    makeRule('SCM-MODEL-003', 'Trace规则完整', traceComplete, SCM_TRACE_ACCEPTANCE_RULES.map(rule => rule.ruleCode)),
    makeRule('SCM-MODEL-004', '状态规则完整', statusesComplete, SCM_STATUS_ACCEPTANCE_RULES.map(rule => `${rule.objectCode}:${rule.allowedTransitions.length}`)),
    makeRule('SCM-MODEL-005', '禁止反向状态', reverseForbidden && isReverseScmGeneration('SCM_PURCHASE_ORDER', 'SCM_PURCHASE_REQUEST'), { reverseTransitionCount: reverseExamples.length, reverseTraceForbidden: true }),
    makeRule('SCM-MODEL-006', 'Action白名单完整', actionComplete, { ruleCount: SCM_ACTION_ACCEPTANCE_RULES.length, policy: 'explicit_whitelist_default_deny' }),
    makeRule('SCM-MODEL-007', '资金边界完整', financeComplete, SCM_FINANCIAL_BOUNDARY),
    makeRule('SCM-MODEL-008', '模板继承正确', templateInherited, { templateCode: template.templateCode, extends: template.extends, checkIds: template.checks.map(check => check.id) }),
    makeRule('SCM-MODEL-009', 'PurchaseRequest覆盖', purchaseRequest?.businessObject === 'PurchaseRequest' && purchaseRequest.lifecycle.length === 5, purchaseRequest?.objectCode || ''),
    makeRule('SCM-MODEL-010', 'PurchaseOrder覆盖', purchaseOrder?.businessObject === 'PurchaseOrder' && purchaseOrder.lifecycle.length === 5, purchaseOrder?.objectCode || ''),
  ])
  const count = result => rules.filter(rule => rule.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    modelCode: 'SCM_BUSINESS_PAGE_ACCEPTANCE_MODEL',
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    validationTarget: {
      productionUrl: '/scm/purchase-request',
      canaryUrl: '/scm/purchase-request?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH',
      executionMode: 'read_only',
    },
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writeScmAcceptanceModelArchive({ archiveRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const outputRoot = path.resolve(archiveRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'SCM/acceptance-model'))
  const report = verifyScmAcceptanceModel()
  const payloads = {
    'scm-object-model.json': listScmAcceptanceObjects(),
    'scm-trace-rules.json': SCM_TRACE_ACCEPTANCE_RULES,
    'scm-status-rules.json': SCM_STATUS_ACCEPTANCE_RULES,
    'scm-action-rules.json': SCM_ACTION_ACCEPTANCE_RULES,
    'scm-financial-boundary.json': SCM_FINANCIAL_BOUNDARY,
    'template.json': template,
    'verification-report.json': report,
  }
  await fs.mkdir(outputRoot, { recursive: true })
  await Promise.all(Object.entries(payloads).map(([name, value]) => fs.writeFile(path.join(outputRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')))
  return Object.freeze({ outputRoot, files: Object.freeze(Object.keys(payloads)), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writeScmAcceptanceModelArchive()
  console.log(JSON.stringify({ ...result.report, archivePath: result.outputRoot, archiveFiles: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

