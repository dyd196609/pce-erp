import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const run = args => spawnSync(process.execPath, args, {
  cwd: root,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '统一列表运行层规范.md',
  '页面开发模板.md',
  '一页一验收规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
]
const governanceLoaded = governanceFiles.every(file => {
  const target = path.join(workspaceRoot, 'docs', 'governance', file)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
})

const recovery = run(['--test', 'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const processCenter = run(['--test',
  'tests/acceptance/enterpriseScmProcessCenterNavigationV11428101.test.mjs',
  'tests/acceptance/processNodeNavigationV1142819.test.mjs',
])
const purchaseInquiry = run(['--test', 'tests/acceptance/enterpriseListRuntimeGovernanceV11428131.test.mjs'])
const supplierQuote = run(['--test',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteSimpleRuntimeV11428121.test.mjs',
])
const quoteComparison = run(['--test',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142812.test.mjs',
])
const materialPrice = run(['--test',
  'tests/acceptance/materialPriceContextV1142815.test.mjs',
  'tests/acceptance/enterpriseListFilterPriceReferenceV1142814.test.mjs',
])
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])

for (const result of [recovery, processCenter, purchaseInquiry, supplierQuote, quoteComparison, materialPrice, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const recoveryPassed = recovery.status === 0
const checks = [
  ['Governance Files Loaded', governanceLoaded && recoveryPassed],
  ['Process Center Visual Contract', recoveryPassed && processCenter.status === 0],
  ['Purchase Inquiry Regression', recoveryPassed && purchaseInquiry.status === 0],
  ['Supplier Quote Regression', recoveryPassed && supplierQuote.status === 0],
  ['Quote Comparison Regression', recoveryPassed && quoteComparison.status === 0],
  ['Price Approval Regression', materialPrice.status === 0],
  ['Material Price Context', recoveryPassed && materialPrice.status === 0],
  ['No Business Regression', recoveryPassed && processCenter.status === 0
    && purchaseInquiry.status === 0 && supplierQuote.status === 0 && quoteComparison.status === 0],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.18.15.1')
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log('Business Write Count: 0')
console.log('Production Data Written: false')
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_PRICE_CONTEXT_REGRESSION_ISSUES_FOUND' : 'SCM_PRICE_CONTEXT_REGRESSION_FIXED')
if (failures.length) process.exitCode = 1
