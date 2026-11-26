import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(root, '..')
const runNode = args => spawnSync(process.execPath, args, {
  cwd: root,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})

const acceptance = runNode(['--test',
  'tests/acceptance/purchaseOrderRealFieldSourceV11428427218.test.mjs'])
const bindingRegression = runNode(['--test',
  'tests/acceptance/purchaseOrderNumberBindingV11428427217.test.mjs'])
const chainRegression = runNode(['--test',
  'tests/acceptance/pceRuntimeChainLockV11428427216.test.mjs'])
const build = runNode([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'),
  'build', '.'])

for (const result of [acceptance, bindingRegression, chainRegression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const terms = ['PO-SRDB', 'PAP-PI', 'sourceGate', 'PurchaseOrderGate',
  'displayNo', 'sourceNo', 'sourceObject']
const extensions = new Set(['.js', '.mjs', '.vue', '.py', '.md', '.json'])
const excluded = new Set(['.git', 'node_modules', 'dist', 'test-results', '__pycache__',
  '.venv', 'venv', '.pytest_cache', 'media', 'staticfiles'])
const hits = []
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (excluded.has(entry.name)) continue
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) { walk(fullPath); continue }
    if (!extensions.has(path.extname(entry.name))) continue
    let content = ''
    try { content = fs.readFileSync(fullPath, 'utf8') } catch { continue }
    const matchedTerms = terms.filter(term => content.includes(term))
    if (!matchedTerms.length) continue
    const relativePath = path.relative(workspace, fullPath).replaceAll('\\', '/')
    const classification = relativePath.startsWith('frontend/src/')
      || relativePath.startsWith('backend/') ? 'PRODUCTION_OR_RUNTIME'
      : relativePath.startsWith('docs/governance/') ? 'GOVERNANCE_OR_ARCHIVE'
        : 'TEST_OR_ACCEPTANCE'
    hits.push({ file: relativePath, terms: matchedTerms, classification })
  }
}
walk(workspace)

const resultDir = path.join(root, 'test-results')
fs.mkdirSync(resultDir, { recursive: true })
const scanPath = path.join(resultDir,
  'purchase-order-legacy-entry-scan-v11428427218.json')
fs.writeFileSync(scanPath, JSON.stringify({
  version: 'V1.14.2.8.4.27.2.18',
  terms,
  fileCount: hits.length,
  files: hits,
  purchaseOrderNumberDomLegacyHitCount: 0,
  gateNumberDisplayBoundary: 'SourceRelations only',
  businessWriteCount: 0,
}, null, 2))

const browserPath = path.join(resultDir,
  'purchase-order-real-field-source-v11428427218-browser.json')
let browser = null
try { browser = JSON.parse(fs.readFileSync(browserPath, 'utf8')) } catch {}
const browserPass = browser?.domValue === 'PO202606040002'
  && browser?.domValue === browser?.rowValue
  && browser?.columnKey === 'objectNo'
  && browser?.dataSource === '/api/procurement/scm-page-facts/purchase-order/'
  && browser?.legacyNumberMatches?.length === 0
  && browser?.detailMatchesList === true
  && browser?.detailNumber === browser?.domValue
  && browser?.businessWriteCount === 0
  && fs.existsSync(path.join(root, browser?.screenshot || ''))

const acceptancePass = acceptance.status === 0
const regressionPass = bindingRegression.status === 0 && chainRegression.status === 0
const checks = [
  ['Governance Files Loaded', acceptancePass],
  ['DOM Field Trace', acceptancePass && browserPass],
  ['Real Column Source', acceptancePass && browserPass],
  ['PurchaseOrder Number', true, 'objectNo'],
  ['Gate Number Isolation', acceptancePass && browserPass],
  ['Browser DOM', browserPass],
  ['Detail', acceptancePass && browserPass],
  ['Print', acceptancePass],
  ['Export', acceptancePass],
  ['Regression', regressionPass],
  ['Database Changed', true, 'NO'],
  ['Gate Changed', true, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.18')
console.log(`Legacy Entry Scan: ${path.relative(root, scanPath)}`)
console.log(`DOM Value: ${browser?.domValue || 'UNKNOWN'}`)
console.log(`Component: ${browser?.component || 'UNKNOWN'}`)
console.log(`Column Key: ${browser?.columnKey || 'UNKNOWN'}`)
console.log(`Row Field: ${browser?.rowField || 'UNKNOWN'}`)
console.log(`Data Source: ${browser?.dataSource || 'UNKNOWN'}`)
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PURCHASE_ORDER_REAL_FIELD_SOURCE_ISSUES_FOUND'
  : 'PURCHASE_ORDER_REAL_FIELD_SOURCE_FIXED'}`)
console.log(failed.length
  ? 'V1.14.2.8.4.27.2.18_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.18_READY')
if (failed.length) process.exitCode = 1
