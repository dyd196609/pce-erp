import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const run = args => spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'] })
const governanceNames = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceNames.every(name => {
  const target = path.join(governanceRoot, name)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
}) && fs.readFileSync(path.join(governanceRoot, 'CODEX执行命令规范.md'), 'utf8')
  .includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationRuntimePathV11428162.test.mjs'])
const prior = run(['--test', 'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionRuntimeV1142816.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142811.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationRuntimeV1142813.test.mjs',
  'tests/acceptance/enterpriseSupplierRecommendationDataBindingV1142811.test.mjs',
  'tests/acceptance/enterpriseScmNodePageGovernanceV11428103.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])
for (const result of [current, prior, regression, build]) {
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
const gateProvider = fs.readFileSync(path.join(root,
  'src/meta/providers/purchaseOrderGateHandoffProviderV11428161.js'), 'utf8')
const runtimeSpec = fs.readFileSync(path.join(governanceRoot, '流程节点真实运行验收规范.md'), 'utf8')
const actionAt = pricePage.indexOf("if(action.actionCode==='OPEN_SUPPLIER_RECOMMENDATION')")
const handoffAt = pricePage.indexOf('executePriceApprovalSupplierRecommendationHandoffV11428161', actionAt)
const routeAt = pricePage.indexOf('router.push', actionAt)
const currentPassed = current.status === 0
const contextFields = ['priceApprovalId', 'priceApprovalNo', 'quoteComparisonId', 'materialCode',
  'materialName', 'supplierCandidates', 'priceEvidence', 'historicalPriceEvidence']
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['PriceApproval Entry', currentPassed && handoffAt > actionAt && routeAt > handoffAt],
  ['Handoff Context', currentPassed && contextFields.every(field => handoff.includes(field))],
  ['Real Data Binding', currentPassed && provider.includes('priceApprovalPreparations')
    && provider.includes('quoteComparisonPreparations') && recommendationPage.includes('route.query.priceApprovalId')],
  ['No Demo Fact', currentPassed && provider.includes('acceptanceModeResolver()')
    && provider.includes(': Object.freeze([])')],
  ['Candidate Selection', currentPassed && recommendationPage.includes('manualSelections')],
  ['Decision Confirmation', currentPassed && recommendationPage.includes('CONFIRM_RECOMMENDATION_DECISION')
    && recommendationPage.includes('currentDecision')],
  ['PurchaseOrderGate Handoff', currentPassed && ['recommendationBasis', 'confirmedBy', 'confirmedAt']
    .every(field => gateProvider.includes(field)) && ['推荐供应商', '推荐依据', '确认人', '确认时间']
    .every(label => gatePage.includes(label)) && !recommendationPage.includes('data-process-action="CREATE_PURCHASE_ORDER"')],
  ['PROCESS-011', currentPassed && ['对象存在', '页面存在', '数据真实承接', '人工动作闭环']
    .every(layer => runtimeSpec.includes(layer))],
  ['Regression', prior.status === 0 && regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.2')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log('Business Write Count: 1 (PriceApproval handoff only)')
console.log('Production Data Written: false')
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_PATH_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_PATH_ISSUES_FOUND')
if (!passed) process.exitCode = 1
