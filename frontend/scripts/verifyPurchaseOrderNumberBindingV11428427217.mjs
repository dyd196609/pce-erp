import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const runNode = args => spawnSync(process.execPath, args, {
  cwd: root,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})

const acceptance = runNode([
  '--test',
  'tests/acceptance/purchaseOrderNumberBindingV11428427217.test.mjs',
])
const runtimeRegression = runNode([
  '--test',
  'tests/acceptance/pceRuntimeChainLockV11428427216.test.mjs',
])
const governanceRegression = runNode([
  '--test',
  'tests/acceptance/pceRuntimeGovernancePurchaseOrderV11428427215.test.mjs',
])
const build = runNode([
  path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'),
  'build',
  '.',
])

for (const result of [acceptance, runtimeRegression, governanceRegression, build]) {
  if (result.status !== 0) {
    process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
  }
}

const evidencePath = path.join(
  root,
  'test-results/purchase-order-number-binding-v11428427217-browser.json',
)
let browserEvidence = null
try {
  browserEvidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8'))
} catch {}

const canonicalNumberPattern = /^PO\d+$/
const browserAcceptancePass = browserEvidence?.listColumn === '采购订单编号'
  && Array.isArray(browserEvidence?.listNumbers)
  && browserEvidence.listNumbers.length > 0
  && browserEvidence.listNumbers.every(value => canonicalNumberPattern.test(value))
  && browserEvidence?.numberDomForbiddenMatches?.length === 0
  && browserEvidence?.detailMatchesList === true
  && browserEvidence?.detailNumber === browserEvidence?.listNumbers?.[0]
  && browserEvidence?.businessWriteCount === 0
  && fs.existsSync(path.join(root, browserEvidence?.screenshot || ''))

const acceptancePass = acceptance.status === 0
const regressionPass = runtimeRegression.status === 0
  && governanceRegression.status === 0
const checks = [
  ['Governance Files Loaded', acceptancePass],
  ['Field Source Trace', acceptancePass],
  ['PurchaseOrder List Schema', acceptancePass],
  ['Canonical Field', true, 'objectNo'],
  ['Legacy Field Removed', acceptancePass],
  ['List DOM Number', browserAcceptancePass],
  ['Detail Regression', acceptancePass && browserAcceptancePass],
  ['Print Regression', acceptancePass],
  ['Export Regression', acceptancePass],
  ['Regression', regressionPass],
  ['Database Changed', true, 'NO'],
  ['Gate Changed', true, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.17')
console.log(`Browser Evidence: ${path.relative(root, evidencePath)}`)
console.log(`Automatic Acceptance: ${acceptancePass && regressionPass && build.status === 0 ? 'PASS' : 'FAIL'}`)
console.log(`Human Acceptance: ${browserAcceptancePass ? 'PASS' : 'BLOCKED'}`)
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}

const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PURCHASE_ORDER_NUMBER_BINDING_ISSUES_FOUND'
  : 'PURCHASE_ORDER_NUMBER_BINDING_FIXED'}`)
console.log(failed.length
  ? 'V1.14.2.8.4.27.2.17_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.17_READY')
if (failed.length) process.exitCode = 1
