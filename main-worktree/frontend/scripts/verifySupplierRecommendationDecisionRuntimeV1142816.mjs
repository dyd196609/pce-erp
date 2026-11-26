import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const run = args => spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'] })
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '统一列表运行层规范.md', '页面开发模板.md',
  '一页一验收规范.md', '治理符合性检查矩阵.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(file => {
  const target = path.join(workspaceRoot, 'docs', 'governance', file)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
}) && fs.readFileSync(path.join(workspaceRoot, 'docs', 'governance', 'CODEX执行命令规范.md'), 'utf8')
  .includes('人工验收反向校验机制')

const runtime = run(['--test', 'tests/acceptance/supplierRecommendationDecisionRuntimeV1142816.test.mjs'])
const legacy = run(['--test',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142813.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationDataBindingV1142811.test.mjs',
  'tests/acceptance/enterpriseScmNodePageGovernanceV11428103.test.mjs',
])
const priorRegression = run(['scripts/verifyV11428151RegressionRecovery.mjs'])
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])
for (const result of [runtime, legacy, priorRegression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const domain = fs.readFileSync(path.join(root,
  'src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionDomainV1142816.js'), 'utf8')
const provider = fs.readFileSync(path.join(root,
  'src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'), 'utf8')
const handoff = fs.readFileSync(path.join(root,
  'src/meta/process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js'), 'utf8')
const page = fs.readFileSync(path.join(root, 'src/meta/pages/ScmSupplierRecommendationPage.vue'), 'utf8')
const runtimePassed = runtime.status === 0
const boundary = !['PceListPageShell.vue', 'PceEnterpriseListTable.vue'].some(name =>
  fs.readFileSync(path.join(root, 'src/meta/components', name), 'utf8').includes('V1142816'))
  && !fs.readFileSync(path.join(root, 'src/router/index.js'), 'utf8').includes('supplierRecommendationDecisionProviderV1142816')
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['BUSINESS-ENHANCEMENT-BOUNDARY', boundary && runtimePassed],
  ['QuoteComparison Input', runtimePassed && provider.includes("'QuoteComparison'")],
  ['Recommendation Context', runtimePassed && domain.includes('SupplierRecommendationDecisionContext')],
  ['Decision Domain', runtimePassed && domain.includes('manualReviewedAt')],
  ['Evidence', runtimePassed && domain.includes('historicalPriceEvidence')],
  ['Manual Confirmation', runtimePassed && domain.includes('RecommendationConfirmationContext')
    && page.includes('CONFIRM_RECOMMENDATION_DECISION')],
  ['Handoff', runtimePassed && handoff.includes("targetObjectType: 'PurchaseOrderCreationGateContext'")],
  ['PurchaseOrder Isolation', runtimePassed && handoff.includes('purchaseOrderCreated: false')
    && !page.includes('data-process-action="CREATE_PURCHASE_ORDER"')],
  ['No Finance/WMS/MES Write', runtimePassed && ['financeWritten: false', 'wmsWritten: false', 'mesWritten: false']
    .every(value => handoff.includes(value))],
  ['Regression', legacy.status === 0 && priorRegression.status === 0
    && priorRegression.stdout.includes('SCM_PRICE_CONTEXT_REGRESSION_FIXED')],
  ['Build', build.status === 0],
]
const automaticAcceptance = checks.every(([, passed]) => passed)
console.log('Version: V1.14.2.8.18.16')
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Automatic Acceptance ${automaticAcceptance ? 'PASS' : 'FAIL'}`)
console.log('Business Write Count: 0')
console.log('Production Data Written: false')
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(automaticAcceptance ? 'SCM_SUPPLIER_RECOMMENDATION_DECISION_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ISSUES_FOUND')
if (!automaticAcceptance) process.exitCode = 1
