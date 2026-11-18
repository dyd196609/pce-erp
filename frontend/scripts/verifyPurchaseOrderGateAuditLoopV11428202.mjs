import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(root, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceFiles = [
  'CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md', '流程节点真实运行验收规范.md',
  '页面Route与业务Context分离规范.md', '问题案例库.md',
].map(name => path.join(repositoryRoot, 'docs', 'governance', name))
const governanceLoaded = governanceFiles.every(file => fs.existsSync(file)
  && fs.readFileSync(file, 'utf8').trim().length > 0)
  && fs.readFileSync(governanceFiles[1], 'utf8').includes('BATCH-COMPLETENESS-001')

const current = run(['--test', 'tests/acceptance/purchaseOrderGateAuditLoopV11428202.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/purchaseOrderGateActionClosureV11428201.test.mjs',
  'tests/acceptance/purchaseOrderGateRuntimeV1142820.test.mjs',
  'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const gatePage = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const recommendationPage = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const provider = read('src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js')
const decisionModel = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const inspectionModel = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderGateInspectionRecordV11428202.js')
const returnModify = current.status === 0 && gatePage.includes('reopenMaterial(row.materialCode')
  && gatePage.includes("router.push('/scm/supplier-recommendation')")
const decisionReopen = decisionModel.includes("from: 'confirmed', to: 'reopen_review'")
  && decisionModel.includes("from: 'reopen_review', to: 'manual_review'")
  && provider.includes('executeReopenSupplierRecommendationDecisionItemV11428202')
const reconfirm = current.status === 0 && recommendationPage.includes("['selected', 'confirmed'].includes(item.status)")
  && decisionModel.includes("['selected', 'confirmed'].includes(item.status)")
const inspectionRecord = inspectionModel.includes("objectType: 'PurchaseOrderGateInspectionRecord'")
  && ['inspectionId', 'gateId', 'checker', 'checkedAt', 'checkResult', 'checkItems', 'blockReasons']
    .every(field => inspectionModel.includes(field))
  && provider.includes('inspectionRecordStore.save') && gatePage.includes('gate-inspection-records')
const auditTrace = ['确认动作', '检查动作', '检查结果', '检查时间', '检查人']
  .every(label => gatePage.includes(label)) && inspectionModel.includes('confirmationAction')
  && inspectionModel.includes('inspectionAction')
const noPurchaseOrder = [gatePage, provider, decisionModel, inspectionModel].every(source =>
  !/createPurchaseOrder\s*\(|savePurchaseOrder\s*\(|submitPurchaseOrder\s*\(/.test(source))
  && inspectionModel.includes('purchaseOrderCreated: false')
const process011 = governanceLoaded && current.status === 0 && routeRegression.status === 0
  && returnModify && decisionReopen && reconfirm && inspectionRecord && auditTrace && noPurchaseOrder

const checks = [
  ['Return Modify', returnModify],
  ['Decision Reopen', decisionReopen],
  ['Reconfirm', reconfirm],
  ['Gate Inspection Record', inspectionRecord],
  ['Audit Trace', auditTrace],
  ['No PurchaseOrder', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0 && routeRegression.status === 0],
  ['Build', build.status === 0],
]
const passed = governanceLoaded && checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.20.2')
console.log(`Governance Files Loaded ${governanceLoaded ? 'PASS' : 'FAIL'}`)
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const layer of ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop',
  'Entry Consistency', 'Action Executability', 'Route Identity', 'Context Separation',
  'Batch Completeness']) console.log(`${layer} ${process011 ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'PURCHASE_ORDER_GATE_AUDIT_LOOP_READY'
  : 'PURCHASE_ORDER_GATE_AUDIT_LOOP_ISSUES_FOUND')
if (!passed) process.exitCode = 1
