import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim()
})

const current = run(['--test', 'tests/acceptance/supplierRecommendationRouteIdentityV11428171.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs',
  'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const router = read('src/router/index.js')
const resolver = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const identityFiles = ['src/meta/governance/businessNameRegistry.js',
  'src/meta/schema/scm/scmPageIdentityRegistry.js', 'src/meta/schema/scm/scmStandardPageContract.js',
  'src/meta/process/scmPageGovernanceComplianceV114281031.js',
  'src/meta/process/scmNodePageGovernanceV11428103.js',
  'src/meta/process/scm/supplierRecommendation/supplierRecommendationPageContractV1142811.js']
const currentPass = current.status === 0
const activeRouteSources = [router, pricePage, page, scmRegistry, processRegistry, ...identityFiles.map(read)]
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Page Route', currentPass && router.includes("path: 'scm/supplier-recommendation'")
    && resolver.includes("'/scm/supplier-recommendation'")],
  ['No Business Data Leakage', currentPass && activeRouteSources.every(source =>
    !/supplier-recommendation-task\/:taskId|route\.(?:params|query)\.(?:taskId|batchId|decisionBatchId|runtimeContextId|priceApprovalId|quoteComparisonId)/.test(source))],
  ['Process Center Entry', currentPass && scmRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428171')
    && processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428171(node)')],
  ['Context Restore', currentPass && resolver.includes('task: frozen(tasks[0])')
    && resolver.includes('decisionBatch: frozen(decisionBatch)')
    && resolver.includes('decisionItems: frozen(decisionBatch.items)')
    && page.includes('supplierRecommendationRouteContextResolverV11428171.resolve()')],
  ['Same Page Identity', currentPass && identityFiles.every(file =>
    read(file).includes('/scm/supplier-recommendation'))
    && pricePage.includes('router.push(context.pageRoute)')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.17.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_ROUTE_IDENTITY_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_ROUTE_IDENTITY_ISSUES_FOUND')
if (!passed) process.exitCode = 1
