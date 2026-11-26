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
const current = run(['--test', 'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs'])
const regression = run(['scripts/verifySupplierRecommendationEntryGovernanceV1142817.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const pass = current.status === 0
const provider = read('src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js')
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const cases = readGovernance('问题案例库.md')
const protectedBoundary = ['src/router/index.js', 'src/meta/governance/businessNameRegistry.js',
  'src/meta/process/scm/supplierRecommendation/supplierRecommendationEntryRouteV1142817.js',
  'src/meta/components/PceListPageShell.vue', 'src/meta/components/PceEnterpriseListTable.vue',
  'src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js',
  'src/meta/pages/ScmPurchaseOrderGatePage.vue'].every(file => !read(file).includes('V1142818'))
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['PriceApproval Context', pass && provider.includes('PriceApprovalRuntimeContext')
    && provider.includes('priceApprovalId: priceApprovalIds[0]')
    && page.includes('采购申请编号') && page.includes('核价编号')],
  ['Task Data', pass && provider.includes("sourcePriority: freeze(['SupplierRecommendationTask'")
    && provider.includes('task.runtimeContextId !== itemBindings[index].runtimeContextId')],
  ['DecisionBatch Data', pass && provider.includes('decisionBatchStore.findById(entryTaskId)')
    && provider.includes('batch.sourcePriceApprovalBatch')],
  ['DecisionItem Data', pass && provider.includes('batch.items.map')
    && provider.includes('ITEM_BINDING_COUNT_INVALID')],
  ['QuoteComparison Match', pass && provider.includes('QUOTE_COMPARISON_MISMATCH')
    && page.includes('quoteComparisonId')],
  ['Material Match', pass && provider.includes('MATERIAL_MISMATCH')
    && provider.includes('value.materialCode === item.materialCode')],
  ['Supplier Match', pass && provider.includes('SUPPLIER_CANDIDATE_MISMATCH')
    && provider.includes('Number(source.quotePrice) === Number(candidate.quotePrice)')],
  ['No Demo Data', pass && provider.includes('NON_PRODUCTION_FACT')
    && provider.includes('PI-TEST-SR') && !page.includes('PI-TEST-SR')],
  ['PROCESS-011 Data Handoff', pass && process011.includes('Data Handoff PASS')
    && provider.includes("factScope: complete ? 'real_price_approval_handoff' : 'blocked'")
    && cases.includes('CASE-SCM-050')],
  ['Regression', regression.status === 0 && protectedBoundary],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.18')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_DATA_HANDOFF_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_DATA_HANDOFF_ISSUES_FOUND')
if (!passed) process.exitCode = 1
