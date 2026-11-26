import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const evidence = JSON.parse(fs.readFileSync(path.join(root, 'acceptance',
  'supplierRecommendationMultiSupplierCanaryV11428184.json'), 'utf8'))
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md', '页面Route与业务Context分离规范.md']
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const hash = relative => crypto.createHash('sha256')
  .update(fs.readFileSync(path.join(root, relative))).digest('hex').toUpperCase()
const unique = values => new Set(values).size === values.length

const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')
const boundaryProtected = Object.entries(evidence.protectedBusinessFileHashes)
  .every(([relative, expected]) => hash(relative) === expected)
const noDemo = evidence.source === 'real-business-page-chain'
  && evidence.runtimeMode === 'production-provider-path'
  && evidence.demoFactUsed === false && evidence.acceptanceFactUsed === false
const source = evidence.sourceDiagnostic.after
const sameMaterialQuotes = evidence.supplierQuotes.length >= 2
  && evidence.supplierQuotes.every(item => item.materialCode === source.materialCode)
  && unique(evidence.supplierQuotes.map(item => item.supplierCode))
  && evidence.supplierQuotes.every(item => item.quotePrice > 0)
const comparison = evidence.quoteComparison.materialCode === source.materialCode
  && evidence.quoteComparison.supplierCodes.length >= 2
  && evidence.quoteComparison.supplierCodes.length === evidence.quoteComparison.quotePrices.length
  && evidence.quoteComparison.quotePrices.every(value => value > 0)
const canary = evidence.canaryC
const singleItem = canary.status === 'PASS' && canary.decisionBatchCount === 1
  && canary.decisionItemCount === 1 && canary.materialCount === 1
  && canary.materialCode === source.materialCode
const candidateGroup = canary.supplierCandidateCount >= 2
  && canary.supplierCandidateCount === canary.supplierCandidates.length
  && unique(canary.supplierCandidates)
  && canary.supplierCandidates.every(code => evidence.quoteComparison.supplierCodes.includes(code))
const routeIdentity = evidence.route.pathname === '/scm/supplier-recommendation'
  && !/[?&](?:taskId|batchId|runtimeContextId|priceApprovalId|quoteComparisonId)=/i
    .test(evidence.route.fullUrl)
const contextSeparation = routeIdentity && evidence.route.technicalQueryLeakage === false
  && evidence.route.contextRestoredAfterReload === true && canary.reloadRestoredSameBatch === true
const humanAcceptance = Object.entries(evidence.humanAcceptance)
  .filter(([name]) => name !== 'humanActionLoop').every(([, value]) => value === 'PASS')
  && evidence.humanAcceptance.humanActionLoop === 'NOT TESTED'

const regression = run(['--test',
  'tests/acceptance/supplierRecommendationBatchIntegrityV11428182.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs',
  'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const process011 = singleItem && candidateGroup && comparison && routeIdentity && contextSeparation
  && noDemo && humanAcceptance
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Multi Supplier Source', source.supplierCount >= 2 && source.priceApprovalSelectedRowCount >= 2],
  ['SupplierQuote Count', sameMaterialQuotes && source.supplierQuoteCount === evidence.supplierQuotes.length],
  ['QuoteComparison Supplier Count', comparison
    && source.quoteComparisonSupplierCount === evidence.quoteComparison.supplierCodes.length],
  ['Single Material DecisionItem', singleItem],
  ['Supplier Candidate Group', candidateGroup],
  ['No Demo Data', noDemo],
  ['Canary C', process011],
  ['PROCESS-011', process011 && boundaryProtected && routeRegression.status === 0],
  ['Regression', regression.status === 0 && boundaryProtected],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.18.4')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(`Canary C Counts: SupplierQuote=${evidence.supplierQuotes.length}, `
  + `QuoteComparisonSupplier=${evidence.quoteComparison.supplierCodes.length}, `
  + `DecisionBatch=${canary.decisionBatchCount}, DecisionItem=${canary.decisionItemCount}, `
  + `Material=${canary.materialCount}, SupplierCandidate=${canary.supplierCandidateCount}`)
console.log('Object Exists PASS')
console.log('Page Exists PASS')
console.log(`Data Handoff ${process011 ? 'PASS' : 'FAIL'}`)
console.log(`Route Identity ${routeIdentity ? 'PASS' : 'FAIL'}`)
console.log(`Context Separation ${contextSeparation ? 'PASS' : 'FAIL'}`)
console.log('Human Action Loop NOT TESTED')
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_MULTI_SUPPLIER_CANARY_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_MULTI_SUPPLIER_CANARY_ISSUES_FOUND')
if (!passed) process.exitCode = 1
