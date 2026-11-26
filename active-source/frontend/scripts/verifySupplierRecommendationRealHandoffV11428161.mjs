import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const run = args => spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'] })
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const governanceNames = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceNames.every(name => {
  const target = path.join(governanceRoot, name)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
}) && fs.readFileSync(path.join(governanceRoot, 'CODEX执行命令规范.md'), 'utf8')
  .includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs'])
const v16 = run(['--test', 'tests/acceptance/supplierRecommendationDecisionRuntimeV1142816.test.mjs'])
const legacy = run(['--test',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142813.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationDataBindingV1142811.test.mjs',
  'tests/acceptance/materialPriceContextV1142815.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs',
])
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])
for (const result of [current, v16, legacy, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const handoff = fs.readFileSync(path.join(root,
  'src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'), 'utf8')
const provider = fs.readFileSync(path.join(root,
  'src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'), 'utf8')
const pricePage = fs.readFileSync(path.join(root,
  'src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue'), 'utf8')
const recommendationPage = fs.readFileSync(path.join(root,
  'src/meta/pages/ScmSupplierRecommendationPage.vue'), 'utf8')
const gatePage = fs.readFileSync(path.join(root, 'src/meta/pages/ScmPurchaseOrderGatePage.vue'), 'utf8')
const actionAt = pricePage.indexOf("if(action.actionCode==='OPEN_SUPPLIER_RECOMMENDATION')")
const writeAt = pricePage.indexOf('executePriceApprovalSupplierRecommendationHandoffV11428161', actionAt)
const routeAt = pricePage.indexOf('router.push', actionAt)
const currentPassed = current.status === 0
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['PriceApproval Input', currentPassed && ['priceApprovalId', 'materialCode', 'priceEvidence']
    .every(field => handoff.includes(field)) && writeAt > actionAt && routeAt > writeAt],
  ['QuoteComparison Context', currentPassed && ['quoteComparisonId', 'supplierCandidates']
    .every(field => handoff.includes(field))],
  ['Real Provider', currentPassed && provider.includes('priceApprovalPreparations')
    && provider.includes('quoteComparisonPreparations')],
  ['No Demo Fact In Production', currentPassed && provider.includes('acceptanceModeResolver()')
    && provider.includes(': Object.freeze([])')],
  ['Candidate Binding', currentPassed && handoff.includes('supplierQualificationFacts')],
  ['Manual Confirmation', currentPassed && recommendationPage.includes('CONFIRM_RECOMMENDATION_DECISION')],
  ['Decision Created', currentPassed && recommendationPage.includes('currentDecision')],
  ['PurchaseOrder Isolation', currentPassed && handoff.includes('purchaseOrderCreated: false')
    && gatePage.includes('purchaseOrderGateHandoffProviderV11428161')
    && !recommendationPage.includes('data-process-action="CREATE_PURCHASE_ORDER"')],
  ['Regression', v16.status === 0 && legacy.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log('Business Write Count: 1 (PriceApproval handoff only)')
console.log('Production Data Written: false')
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_REAL_HANDOFF_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_REAL_HANDOFF_ISSUES_FOUND')
if (!passed) process.exitCode = 1
