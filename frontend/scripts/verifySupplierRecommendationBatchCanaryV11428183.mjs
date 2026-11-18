import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const evidencePath = path.join(root, 'acceptance', 'supplierRecommendationBatchCanaryV11428183.json')
const evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8'))
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md', '页面Route与业务Context分离规范.md']
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const unique = values => new Set(values).size === values.length
const hash = relative => crypto.createHash('sha256')
  .update(fs.readFileSync(path.join(root, relative))).digest('hex').toUpperCase()

const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')
const boundaryProtected = Object.entries(evidence.protectedBusinessFileHashes)
  .every(([relative, expected]) => hash(relative) === expected)
const realEntry = evidence.source === 'price-approval-page-real-entry'
  && evidence.runtimeMode === 'production'
  && evidence.demoFactUsed === false && evidence.acceptanceFactUsed === false
const completeCounts = canary => canary.priceApprovalCount === canary.taskCount
  && canary.decisionBatchCount === 1
  && canary.decisionItemCount === canary.materialCount
  && canary.sourcePriceApprovalIds.length === canary.priceApprovalCount
  && canary.quoteComparisonIds.length === canary.quoteComparisonCount
  && canary.materialCodes.length === canary.materialCount
  && unique(canary.sourcePriceApprovalIds) && unique(canary.quoteComparisonIds)
const canaryAPass = evidence.canaryA.status === 'PASS' && completeCounts(evidence.canaryA)
  && evidence.canaryA.priceApprovalCount === 1 && evidence.canaryA.decisionItemCount === 1
const canaryBPass = evidence.canaryB.status === 'PASS' && completeCounts(evidence.canaryB)
  && evidence.canaryB.priceApprovalCount === 3 && evidence.canaryB.decisionItemCount === 3
  && evidence.canaryB.reloadRestoredSameBatch === true
const canaryCPass = evidence.canaryC.status === 'PASS'
  && evidence.canaryC.supplierCandidateCount > evidence.canaryC.materialCount

const tests = run(['--test',
  'tests/acceptance/supplierRecommendationBatchIntegrityV11428182.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs',
  'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const route = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [tests, route, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const routeIdentity = route.status === 0
  && evidence.route.pathname === '/scm/supplier-recommendation'
  && !/[?&](?:taskId|batchId|runtimeContextId|priceApprovalId|quoteComparisonId)=/i
    .test(evidence.route.fullUrl)
const contextSeparation = routeIdentity && evidence.route.technicalQueryLeakage === false
  && evidence.route.contextRestoredAfterReload === true
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Real Entry', realEntry],
  ['Canary A', canaryAPass],
  ['Canary B', canaryBPass],
  ['Canary C', canaryCPass],
  ['Batch Integrity', canaryBPass && boundaryProtected],
  ['DecisionItem Grain', tests.status === 0 && canaryAPass && canaryBPass],
  ['No Data Loss', canaryBPass
    && evidence.canaryB.supplierCandidates.length === evidence.canaryB.supplierCandidateCount],
  ['Route Identity', routeIdentity],
  ['Context Separation', contextSeparation],
  ['PROCESS-011 Data Handoff', canaryAPass && canaryBPass && canaryCPass],
  ['Regression', tests.status === 0 && boundaryProtected],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.18.3')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const name of ['canaryA', 'canaryB']) {
  const item = evidence[name]
  console.log(`${name} Counts: PriceApproval=${item.priceApprovalCount}, Task=${item.taskCount}, `
    + `DecisionBatch=${item.decisionBatchCount}, DecisionItem=${item.decisionItemCount}, `
    + `Material=${item.materialCount}, SupplierCandidate=${item.supplierCandidateCount}, `
    + `QuoteComparison=${item.quoteComparisonCount}`)
}
if (!canaryCPass) console.log(`Canary C Issue: ${evidence.canaryC.reason}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_BATCH_CANARY_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_BATCH_CANARY_ISSUES_FOUND')
if (!passed) process.exitCode = 1
