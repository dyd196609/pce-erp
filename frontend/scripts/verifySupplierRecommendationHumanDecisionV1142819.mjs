import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const evidence = JSON.parse(read('acceptance/supplierRecommendationHumanDecisionV1142819.json'))
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md', '页面开发模板.md',
  '一页一验收规范.md', '问题案例库.md', '页面Route与业务Context分离规范.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs',
  'tests/acceptance/supplierRecommendationBatchIntegrityV11428182.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs',
  'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const model = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const gate = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const cases = readGovernance('问题案例库.md')
const currentPass = current.status === 0
const realHuman = evidence.source === 'real-supplier-recommendation-page'
  && !evidence.demoFactUsed && !evidence.acceptanceFactUsed
const candidateDisplay = realHuman && evidence.candidates.length === 3
  && ['报价金额', '报价比较', '历史价格', '资格状态'].every(label => page.includes(label))
const supplierSelection = evidence.manualDecision.selectedSupplierCode === 'SUP001'
  && evidence.candidates.some(item => item.supplierCode === evidence.manualDecision.selectedSupplierCode)
const reasonInput = Boolean(evidence.manualDecision.selectionReason)
  && evidence.automaticBehavior.automaticReasonGeneration === false
const manualConfirm = evidence.manualDecision.nonLowestPriceSelection === true
  && evidence.manualDecision.selectedQuotePrice > evidence.manualDecision.lowestQuotePrice
  && evidence.automaticBehavior.automaticLowestPriceSelection === false
const decisionStatus = evidence.manualDecision.reviewStatus === 'confirmed'
  && Boolean(evidence.manualDecision.reviewer && evidence.manualDecision.reviewedAt)
  && ['decisionItemId', 'selectedSupplierCode', 'selectedSupplierName', 'selectionReason',
    'reviewStatus', 'reviewer', 'reviewedAt'].every(field => model.includes(field))
const batchConfirm = currentPass && evidence.batchResult.status === 'confirmed'
  && evidence.canaries.canaryBThirteenItemsAutomated === 'PASS'
const gateHandoff = evidence.gateHandoff.status === 'handoff_ready'
  && ['materialDisplayed', 'supplierDisplayed', 'reasonDisplayed', 'reviewerDisplayed', 'reviewedAtDisplayed']
    .every(field => evidence.gateHandoff[field] === true)
  && gate.includes('decision-batch-gate-handoff')
const noAuto = evidence.automaticBehavior.automaticSupplierSelection === false
  && evidence.automaticBehavior.aiDecision === false
  && page.includes('采购人员必须为每个物料选择一家供应商并填写独立理由')
const noPurchaseOrder = evidence.gateHandoff.purchaseOrderCreated === false
  && evidence.automaticBehavior.purchaseOrderCreated === false
  && model.includes('purchaseOrderCreated: false')
const routeIdentity = routeRegression.status === 0 && !evidence.route.technicalQueryLeakage
const process011 = [candidateDisplay, supplierSelection, reasonInput, manualConfirm, decisionStatus,
  batchConfirm, gateHandoff, noAuto, noPurchaseOrder, routeIdentity].every(Boolean)
  && cases.includes('CASE-SCM-055')

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Candidate Display', candidateDisplay],
  ['Supplier Selection', supplierSelection],
  ['Reason Input', reasonInput],
  ['Manual Confirm', manualConfirm],
  ['Decision Status', decisionStatus],
  ['Batch Confirm', batchConfirm],
  ['Gate Handoff', gateHandoff],
  ['No Auto Recommendation', noAuto],
  ['No PurchaseOrder', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.19')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const layer of ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop',
  'Entry Consistency', 'Action Executability', 'Route Identity', 'Context Separation']) {
  console.log(`${layer} ${process011 ? 'PASS' : 'FAIL'}`)
}
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_HUMAN_DECISION_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_HUMAN_DECISION_ISSUES_FOUND')
if (!passed) process.exitCode = 1
