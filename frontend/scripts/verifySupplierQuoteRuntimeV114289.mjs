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

const nodeSource = readFrontend('src/meta/process/scm/supplierQuote/supplierQuoteNodeContractV114289.js')
const domainSource = readFrontend('src/meta/process/scm/supplierQuote/supplierQuoteDomainModelV114289.js')
const stateSource = readFrontend('src/meta/process/scm/supplierQuote/supplierQuoteStateContractV114289.js')
const actionSource = readFrontend('src/meta/process/scm/supplierQuote/supplierQuoteActionContractsV114289.js')
const handoffSource = readFrontend('src/meta/process/scm/supplierQuote/quotePreparationToSupplierQuoteHandoffContract.js')
const providerSource = readFrontend('src/meta/providers/supplierQuoteProviderV114289.js')
const pageSource = readFrontend('src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue')
const routerSource = readFrontend('src/router/index.js')
const registrySource = readFrontend('src/meta/schema/scm/scmPageIdentityRegistry.js')
const sourcePage = readFrontend('src/meta/pages/ScmPage.vue')
const caseLibrary = readWorkspace('docs/governance/问题案例库.md')
const pageAcceptancePath = path.join(workspaceRoot, 'docs', 'acceptance', 'supplier-quote-v114289', 'PAGE-SUPPLIER-QUOTE.md')

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV1142811.test.mjs',
  'tests/acceptance/enterpriseScmPurchaseGoldenPathStabilizationV1142881.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const goldenRegression = spawnSync(process.execPath, ['scripts/verifyScmPurchaseGoldenPathV114288.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const nodeContract = nodeSource.includes("nodeCode: 'SCM_SUPPLIER_QUOTE'")
  && nodeSource.includes("inputObject: 'QuotePreparationContext'")
  && nodeSource.includes("outputObject: 'QuoteComparisonPreparationContext'")
  && nodeSource.includes("approvalContract: 'not_applicable'")
const domain = ['SupplierQuoteContext', 'SupplierQuote', 'supplierCode', 'materialCode', 'unitPrice',
  'taxRate', 'deliveryDate', 'validityDate'].every(value => domainSource.includes(value))
const stateContract = ['quote_preparation_ready', 'supplier_quote_collecting',
  'supplier_quote_completed', 'comparison_ready'].every(value => stateSource.includes(value))
  && stateSource.includes('comparisonReadyCreatesFormalComparison: false')
const actionContract = ['CREATE_SUPPLIER_QUOTE_CONTEXT', 'SAVE_SUPPLIER_QUOTE', 'COMPLETE_SUPPLIER_QUOTE']
  .every(value => actionSource.includes(value))
  && ['SEND_SUPPLIER', 'CALL_SUPPLIER_API', 'CREATE_PURCHASE_ORDER', 'CREATE_QUOTE_COMPARISON']
    .every(value => actionSource.includes(value))
const handoff = handoffSource.includes("source: 'QuotePreparationContext'")
  && handoffSource.includes("target: 'SupplierQuoteContext'")
  && ['inquiryNo', 'sourceRequestNo', 'materialLines', 'supplierCandidates'].every(value => handoffSource.includes(value))
const provider = providerSource.includes("providerCode: 'SCM_SUPPLIER_QUOTE_PROVIDER'")
  && providerSource.includes("factSource: 'supplier_quote_runtime_store'")
  && !providerSource.includes('legacyMock') && !providerSource.includes('fetch(')
const page = pageSource.includes('data-page-code="supplier-quote-workbench"')
  && ['data-acceptance-region="business-context"', 'data-acceptance-region="quote-detail"',
    'data-acceptance-region="business-actions"', 'data-acceptance-region="next-action"']
    .every(value => pageSource.includes(value))
  && ['来源询价', '来源采购申请', '报价状态', '录入报价', '保存报价', '完成报价收集',
    '当前节点', '供应商报价', '下一节点', '报价比较准备'].every(value => pageSource.includes(value))
  && !pageSource.includes('{{ currentContext.quoteStatus }}')
const pageIdentity = routerSource.includes("path: 'scm/supplier-quotes'")
  && routerSource.includes("pageCode: 'supplier-quote-workbench'")
  && registrySource.includes("pageName: '供应商报价工作台'")
  && registrySource.includes("businessObject: 'SupplierQuote'")
const process006A = tests.status === 0 && nodeContract && domain && stateContract && actionContract && page
const process006B = tests.status === 0 && handoff && provider
const process006C = pageIdentity && sourcePage.includes("router.push('/scm/supplier-quotes')")
const process006D = tests.status === 0
const process008 = goldenRegression.status === 0
  && goldenRegression.stdout.includes('SCM_PURCHASE_GOLDEN_PATH_STABILIZED')
const process009 = fs.existsSync(pageAcceptancePath)
  && fs.readFileSync(pageAcceptancePath, 'utf8').includes('结果：PASS')
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
  ['Governance Files Loaded', governanceLoaded],
  ['Node Contract', nodeContract], ['Domain', domain], ['State Contract', stateContract],
  ['Action Contract', actionContract], ['Handoff', handoff], ['Provider', provider], ['Page', page && pageIdentity],
  ['PROCESS-006-A', process006A], ['PROCESS-006-B', process006B],
  ['PROCESS-006-C', process006C], ['PROCESS-006-D', process006D],
  ['PROCESS-008', process008], ['PROCESS-009', process009], ['PROCESS-010', process010],
  ['Regression', regression], ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('问题清单：')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_SUPPLIER_QUOTE_RUNTIME_ISSUES_FOUND' : 'SCM_SUPPLIER_QUOTE_RUNTIME_READY')
if (failures.length) process.exitCode = 1
