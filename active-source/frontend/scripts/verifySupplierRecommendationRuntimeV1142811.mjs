import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { evaluateGovernanceFirstGate } from '../src/meta/governance/governanceFirstDevelopment.js'

const VERSION = 'V1.14.2.8.18.11'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')
const governanceFiles = [
  'CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md', '节点开发模板.md', '页面开发模板.md',
  '一页一验收规范.md', '问题案例库.md', '治理符合性检查矩阵.md', '业务名称治理规范.md',
]
const governanceFilesLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})
const commandGovernance = fs.readFileSync(path.join(governanceRoot, 'CODEX执行命令规范.md'), 'utf8')
const humanFeedbackGovernanceLoaded = commandGovernance.includes('第十三章：人工验收反向校验机制')
  && commandGovernance.includes('CODEX-COMMAND-002')
const governanceFirst = evaluateGovernanceFirstGate({ existingStandardAssessed: true,
  standardUpdateRequired: false, caseUpdateRequired: false, matrixUpdateRequired: false })

const nodeSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationNodeContractV1142811.js')
const domainSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationDomainModelV1142811.js')
const stateSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationStateContractV1142811.js')
const actionSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationActionContractsV1142811.js')
const handoffSource = readFrontend('src/meta/process/scm/supplierRecommendation/quoteComparisonSupplierRecommendationHandoffV1142811.js')
const providerSource = readFrontend('src/meta/providers/supplierRecommendationProviderV1142811.js')
const providerContractSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationProviderContractV1142811.js')
const pageSource = readFrontend('src/meta/pages/ScmSupplierRecommendationPage.vue')
const pageContractSource = readFrontend('src/meta/process/scm/supplierRecommendation/supplierRecommendationPageContractV1142811.js')
const routerSource = readFrontend('src/router/index.js')
const identitySource = readFrontend('src/meta/schema/scm/scmPageIdentityRegistry.js')
const nameRegistrySource = readFrontend('src/meta/governance/businessNameRegistry.js')
const acceptanceRecord = readWorkspace('docs/acceptance/PAGE-SUPPLIER-RECOMMENDATION.md')
const caseLibrary = readWorkspace('docs/governance/问题案例库.md')

const nodeContract = ["SCM_SUPPLIER_RECOMMENDATION_DECISION",
  "inputObject: 'SupplierRecommendationDecisionPreparationContext'",
  "outputObject: 'SupplierRecommendationDecision'", "nextNode: 'SCM_PURCHASE_ORDER_CREATION_GATE'"]
  .every(token => nodeSource.includes(token))
const domain = ['SupplierRecommendationDecisionContext', 'SupplierRecommendationDecision',
  'SupplierRecommendationEvidence', 'RecommendationApprovalContext', 'supplierCode', 'materialCode',
  'quoteBasis', 'priceRank', 'deliveryBasis', 'qualificationStatus', 'recommendationReason',
  'manualConfirmationStatus', 'sourceQuoteComparisonId', 'priceRanking', 'qualificationEvidence',
  'decisionId', 'decisionStatus', 'manualReviewer', 'manualConfirmedAt', 'reviewStatus', 'reviewer',
  'reviewComment', "decisionMode: 'manual_only'"]
  .every(token => domainSource.includes(token))
  && !domainSource.includes('recommendedSupplierId')
const stateContract = ['created', 'evaluating', 'decision_prepared', 'manual_review', 'confirmed', 'handoff_ready']
  .every(token => stateSource.includes(token))
  && stateSource.includes('confirmed: \'推荐结果已确认\'')
const actionContract = ['CREATE_RECOMMENDATION_DECISION_CONTEXT', 'START_RECOMMENDATION_EVALUATION',
  'PREPARE_RECOMMENDATION_DECISION', 'START_MANUAL_REVIEW', 'CONFIRM_RECOMMENDATION_DECISION',
  'PREPARE_PURCHASE_ORDER_GATE_HANDOFF'].every(token => actionSource.includes(token))
  && ['AUTO_RECOMMEND_SUPPLIER', 'AI_DECIDE_SUPPLIER', 'CREATE_PURCHASE_ORDER']
    .every(token => actionSource.includes(token))
  && ['prepareRecommendationDecision', 'submitManualReview', 'confirmRecommendation',
    'autoRecommendSupplier', 'createPurchaseOrder', 'sendSupplier', 'executePurchaseOrder',
    'financeWrite', 'warehouseWrite', 'mesWrite'].every(token => actionSource.includes(token))
const handoff = ['QuoteComparison', 'SupplierRecommendationDecisionPreparationContext',
  'SupplierRecommendationDecisionContext', 'SupplierRecommendationDecision', 'PurchaseOrderCreationGateContext',
  'sourceObjectType', 'sourceObjectId', 'manualConfirmationStatus']
  .every(token => handoffSource.includes(token))
  && handoffSource.includes('purchaseOrderGateCreated: false')
const provider = providerSource.includes("providerCode: 'SCM_SUPPLIER_RECOMMENDATION_PROVIDER'")
  && providerSource.includes("factSource: 'SupplierRecommendationRuntimeStore'")
  && providerSource.includes("upstreamFactSource: 'QuoteComparisonRuntimeStore'")
  && providerContractSource.includes('legacyMockAllowed: false')
  && !providerSource.includes('legacyMock') && !providerSource.includes('fetch(')
const pageRegions = ['business-context', 'comparison-evidence', 'recommendation-candidates',
  'recommendation-evidence', 'manual-confirmation', 'next-action']
  .every(region => pageSource.includes(`data-acceptance-region="${region}"`))
const pageIdentity = routerSource.includes("path: 'scm/supplier-recommendations'")
  && routerSource.includes("pageCode: 'supplier-recommendation'")
  && identitySource.includes("pageCode: 'supplier-recommendation'")
  && identitySource.includes("businessObject: 'SupplierRecommendationDecision'")
  && pageContractSource.includes("route: '/scm/supplier-recommendations'")
const nodePage001 = pageIdentity && pageSource.includes('data-page-code="supplier-recommendation"')
  && pageSource.includes('data-business-object="SupplierRecommendationDecision"')
const nameGov = nameRegistrySource.includes("['SupplierRecommendationDecision','supplier-recommendation','供应商推荐'")
  && pageSource.includes("resolveBusinessName('supplier-recommendation')")
  && pageSource.includes('{{ businessName.pageTitle }}')
  && !pageSource.includes('<h1>供应商推荐</h1>') && !pageSource.includes('document.title')
const process009 = acceptanceRecord.includes('PAGE-ACCEPT-SCM-SUPPLIER-RECOMMENDATION-V1142811')
  && acceptanceRecord.includes('人工验收：待人工验收') && pageRegions
const process010 = ['CASE-SCM-032', 'CASE-SCM-031', 'CASE-SCM-030', 'CASE-SCM-028', 'CASE-SCM-029']
  .every(token => caseLibrary.includes(token))
const productionScanSources = [
  readFrontend('src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js'),
  readFrontend('src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'),
  providerSource,
  pageSource,
]
const productionWritePatterns = [
  /fetch\s*\(/g, /axios\s*\./g, /\/api\//g, /createPurchaseOrder\s*\(/g,
  /executePurchaseOrder\s*\(/g, /workflowEngine\s*\./g, /approvalEngine\s*\./g,
  /financeRuntime\s*\./g, /wmsRuntime\s*\./g, /mesRuntime\s*\./g,
]
const businessWriteCount = productionScanSources.reduce((count, source) => count
  + productionWritePatterns.reduce((sum, pattern) => sum + (source.match(pattern) || []).length, 0), 0)
const productionDataWritten = businessWriteCount

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142813.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterprisePageNameConsumptionGovernanceV114281034.test.mjs',
  'tests/acceptance/enterprisePageShellNameGovernanceV114281035.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceRegression = spawnSync(process.execPath, ['scripts/verifyGovernanceFirstDevelopmentV114281036B.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
for (const run of [tests, governanceRegression, build]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const runtimePassed = tests.status === 0
const process006 = runtimePassed && nodeContract && domain && stateContract && actionContract && handoff && provider
  && pageIdentity
const process008 = runtimePassed && actionSource.includes('AUTO_RECOMMEND_SUPPLIER')
  && actionSource.includes('CREATE_PURCHASE_ORDER')
  && stateSource.includes('purchaseOrderCreated: false')
const regression = runtimePassed && governanceRegression.status === 0
const automaticAcceptance = governanceFirst.developmentAllowed && governanceFilesLoaded
  && humanFeedbackGovernanceLoaded && process006 && process008 && process009 && process010
  && nodePage001 && nameGov && businessWriteCount === 0 && build.status === 0 && regression
const checks = [
  ['Governance First Check', governanceFirst.developmentAllowed],
  ['Governance Files Loaded', governanceFilesLoaded && humanFeedbackGovernanceLoaded],
  ['Node Contract', nodeContract], ['Domain', domain], ['State Contract', stateContract],
  ['Action Contract', actionContract], ['Handoff', handoff], ['Provider', provider],
  ['Page Identity', pageIdentity], ['NODE-PAGE-001', nodePage001], ['NAME-GOV', nameGov],
  ['PROCESS-006', process006], ['PROCESS-008', process008], ['PROCESS-009', process009],
  ['PROCESS-010', process010], ['Regression', regression], ['Build', build.status === 0],
  ['Automatic Acceptance', automaticAcceptance],
]

console.log(`Version: ${VERSION}`)
console.log(`Version ${VERSION === 'V1.14.2.8.18.11' ? 'PASS' : 'FAIL'}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Business Write Count ${businessWriteCount}`)
console.log(`Production Data Written ${productionDataWritten}`)
console.log('Human Acceptance: 待人工验收')
console.log('Human Feedback Closed: 待人工验收后判定')
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
const humanAcceptancePending = true
if (failures.length || humanAcceptancePending) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
  console.log(`${failures.length + 1}. Human Acceptance Pending`)
}
console.log('SCM_SUPPLIER_RECOMMENDATION_RUNTIME_ISSUES_FOUND')
if (failures.length) process.exitCode = 1
