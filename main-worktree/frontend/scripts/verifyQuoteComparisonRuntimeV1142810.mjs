import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')
const governanceFiles = ['PCE-ERP开发治理总规范.md', '节点开发模板.md', '页面开发模板.md',
  'Approval审批治理规范.md', '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(workspaceRoot, 'docs', 'governance', name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const nodeSource = readFrontend('src/meta/process/scm/quoteComparison/quoteComparisonNodeContractV1142810.js')
const domainSource = readFrontend('src/meta/process/scm/quoteComparison/quoteComparisonDomainModelV1142810.js')
const stateSource = readFrontend('src/meta/process/scm/quoteComparison/quoteComparisonStateContractV1142810.js')
const actionSource = readFrontend('src/meta/process/scm/quoteComparison/quoteComparisonActionContractsV1142810.js')
const handoffSource = readFrontend('src/meta/process/scm/quoteComparison/supplierQuoteToQuoteComparisonHandoffContractV1142810.js')
const providerSource = readFrontend('src/meta/providers/quoteComparisonProviderV1142810.js')
const pageSource = readFrontend('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const routerSource = readFrontend('src/router/index.js')
const registrySource = readFrontend('src/meta/schema/scm/scmPageIdentityRegistry.js')
const supplierPage = readFrontend('src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue')
const caseLibrary = readWorkspace('docs/governance/问题案例库.md')
const acceptancePath = path.join(workspaceRoot, 'docs', 'acceptance', 'QUOTE-COMPARISON-PAGE.md')

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteComparisonV1142853.test.mjs',
  'tests/acceptance/enterpriseScmPurchaseGoldenPathStabilizationV1142881.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const goldenRegression = spawnSync(process.execPath, ['scripts/verifyScmPurchaseGoldenPathV114288.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const nodeContract = nodeSource.includes("nodeCode: 'SCM_QUOTE_COMPARISON'")
  && nodeSource.includes("inputObject: 'SupplierQuoteContext'")
  && nodeSource.includes("outputObject: 'SupplierRecommendationDecisionPreparationContext'")
const domain = ['QuoteComparisonPreparationContext', 'QuoteComparison', 'materialCode', 'supplierCode',
  'unitPrice', 'totalPrice', 'deliveryDate', 'validityDate', 'comparisonResult'].every(value => domainSource.includes(value))
const stateContract = ['supplier_quote_completed', 'comparison_preparing', 'comparison_ready']
  .every(value => stateSource.includes(value)) && stateSource.includes('比较准备完成')
const actionContract = ['CREATE_QUOTE_COMPARISON_CONTEXT', 'GENERATE_QUOTE_COMPARISON', 'SAVE_QUOTE_COMPARISON']
  .every(value => actionSource.includes(value))
  && ['CREATE_SUPPLIER_RECOMMENDATION', 'CREATE_PURCHASE_ORDER'].every(value => actionSource.includes(value))
const handoff = handoffSource.includes("fromNode: 'SCM_SUPPLIER_QUOTE'")
  && handoffSource.includes("toNode: 'SCM_QUOTE_COMPARISON'")
  && ['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierQuotes'].every(value => handoffSource.includes(value))
const provider = providerSource.includes("providerCode: 'SCM_QUOTE_COMPARISON_PROVIDER'")
  && providerSource.includes("factSource: 'SupplierQuoteProvider'")
  && providerSource.includes('supplierQuoteProvider') && !providerSource.includes('legacyMock') && !providerSource.includes('fetch(')
const pageRegions = ['business-context', 'quote-detail', 'comparison-result', 'next-action']
  .every(value => pageSource.includes(`data-acceptance-region=\"${value}\"`))
const page = pageSource.includes('PceEnterpriseListTable') && pageSource.includes('PceBusinessStatus')
  && pageSource.includes('PCE') === false
  && ['来源询价编号', '来源采购申请', '报价数量', '供应商数量', '价格排名', '交期排名',
    '有效期状态', '供应商推荐决策准备'].every(value => pageSource.includes(value)) && pageRegions
const pageIdentity = routerSource.includes("path: 'scm/quote-comparisons'")
  && routerSource.includes("pageCode: 'quote-comparison-workbench'")
  && registrySource.includes("pageName: '报价比较工作台'")
  && registrySource.includes("businessObject: 'QuoteComparison'")
const process006A = tests.status === 0 && nodeContract && domain && stateContract && actionContract && page
const process006B = tests.status === 0 && handoff && provider
const process006C = pageIdentity && supplierPage.includes("router.push('/scm/quote-comparisons')")
const process006D = tests.status === 0
const process008 = goldenRegression.status === 0 && goldenRegression.stdout.includes('SCM_PURCHASE_GOLDEN_PATH_STABILIZED')
const process009 = fs.existsSync(acceptancePath) && fs.readFileSync(acceptancePath, 'utf8').includes('结果：PASS')
const process010 = ['CASE-SCM-010', 'CASE-SCM-011', 'CASE-SCM-012', 'CASE-SCM-013', 'CASE-SCM-014']
  .every(value => caseLibrary.includes(value))

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (tests.status !== 0) process.stderr.write(`${tests.stdout || ''}${tests.stderr || ''}`)
if (goldenRegression.status !== 0) process.stderr.write(`${goldenRegression.stdout || ''}${goldenRegression.stderr || ''}`)
if (build.status !== 0) process.stderr.write(`${build.stdout || ''}${build.stderr || ''}`)

const regression = tests.status === 0 && process008
const checks = [
  ['Governance Files Loaded', governanceLoaded], ['Node Contract', nodeContract], ['Domain', domain],
  ['State Contract', stateContract], ['Action Contract', actionContract], ['Handoff', handoff],
  ['Provider', provider], ['Page', page && pageIdentity], ['PROCESS-006-A', process006A],
  ['PROCESS-006-B', process006B], ['PROCESS-006-C', process006C], ['PROCESS-006-D', process006D],
  ['PROCESS-008', process008], ['PROCESS-009', process009], ['PROCESS-010', process010],
  ['Regression', regression], ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('问题清单：')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_QUOTE_COMPARISON_RUNTIME_ISSUES_FOUND' : 'SCM_QUOTE_COMPARISON_RUNTIME_READY')
if (failures.length) process.exitCode = 1
