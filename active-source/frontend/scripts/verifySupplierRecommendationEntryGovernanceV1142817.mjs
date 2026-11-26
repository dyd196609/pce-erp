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

const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')
const current = run(['--test', 'tests/acceptance/supplierRecommendationRouteIdentityV11428171.test.mjs'])
const regression = run(['scripts/verifySupplierRecommendationDecisionWorkbenchV11428169.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const pass = current.status === 0
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const route = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js')
const router = read('src/router/index.js')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const names = read('src/meta/governance/businessNameRegistry.js')
const cases = readGovernance('问题案例库.md')
const noTechnicalQuery = ![page, route, pricePage, processRegistry].some(source =>
  /[?&](?:batchId|runtimeContextId|priceApprovalId|quoteComparisonId)=|route\.query\.(?:batchId|decisionBatchId|runtimeContextId|priceApprovalId|quoteComparisonId)/.test(source))
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Page Name', pass && page.includes('data-page-name="供应商推荐"')
    && page.includes('<h1>供应商推荐</h1>') && !page.includes('供应商推荐决策工作台')
    && names.includes("'SupplierRecommendationDecisionBatch','supplier-recommendation','供应商推荐'")],
  ['Route Identity', pass && route.includes('/scm/supplier-recommendation')
    && router.includes("path: 'scm/supplier-recommendation'")],
  ['PurchaseApproval Entry', pass && pricePage.includes('supplierRecommendationRouteContextResolverV11428171.activate(result.activeBatch.batchId)')
    && pricePage.includes('supplierRecommendationRouteContextResolverV11428171.activate(firstBatch.batchId)')],
  ['Process Center Entry', pass && scmRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428171')
    && processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428171(node)')],
  ['Same Page Identity', pass && page.includes('supplierRecommendationRouteContextResolverV11428171.resolve()')
    && router.includes("name: 'ScmSupplierRecommendation'")],
  ['No Technical Query Leakage', pass && noTechnicalQuery && cases.includes('CASE-SCM-049')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.17')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_ENTRY_GOVERNANCE_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_ENTRY_GOVERNANCE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
