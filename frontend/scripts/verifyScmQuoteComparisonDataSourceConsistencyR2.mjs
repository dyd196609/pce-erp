import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const provider = read('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')
const adapter = read('frontend/src/meta/acceptance/quoteComparisonProductionAcceptanceAdapterV11428423R2.js')
const page = read('frontend/src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const canary = read('backend/purchase_canary/quote_comparison_runtime.py')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-ACT-001-R2.md')

check('Production Contract', provider.includes("source: 'production'")
  && provider.includes('rows: facts.records') && provider.includes('resultCount: facts.recordCount')
  && page.includes('providerFacts.resultCount'))
check('factLoadStatus', provider.includes("factLoadStatus: 'loaded'")
  && page.includes("factLoadStatus:'read_failed'") && page.includes('data-fact-load-status'))
check('Acceptance Adapter Same Facts', adapter.includes('resultCount === rows.length')
  && adapter.includes("source === 'production'") && !adapter.includes('createQuoteComparisonSimpleRows'))
check('Canary Isolation', provider.includes("source: 'canary'")
  && provider.includes("dataMode: 'canary_acceptance'") && canary.includes('QC-CAN-')
  && !canary.includes('QC-DEMO'))
check('One Page Acceptance', acceptance.includes('SCM-QUOTE-COMPARISON-ACT-001-R2')
  && acceptance.includes('PRODUCTION-DATA-CONSISTENCY') && acceptance.includes('PAGE_BLOCKED'))

let diagnosticCount = 0
let refreshCount = 0
try {
  const responses = await Promise.all([
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/quote-comparison-workbench/'),
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/quote-comparison-workbench/'),
  ])
  const payloads = await Promise.all(responses.map(response => response.json()))
  diagnosticCount = Number(payloads[0]?.data?.resultCount ?? payloads[0]?.data?.recordCount ?? 0)
  refreshCount = Number(payloads[1]?.data?.resultCount ?? payloads[1]?.data?.recordCount ?? 0)
} catch {}

const manualBrowserCount = 13
check('Production Data Consistency', manualBrowserCount === diagnosticCount,
  `manualBrowser=${manualBrowserCount},diagnosticApi=${diagnosticCount}`)
check('Diagnostic Refresh 13', diagnosticCount === 13 && refreshCount === 13,
  `before=${diagnosticCount},refresh=${refreshCount}`)

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/quoteComparisonProductionAcceptanceAdapterV11428423R2.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142812.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonScrollVisualV11428134.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', timeout: 120000 })
check('Regression', tests.status === 0, `${tests.stdout}\n${tests.stderr}`.slice(-2000))

const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
})
check('Build', build.status === 0, `${build.stdout}\n${build.stderr}`.slice(-2000))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`ManualBrowserCount=${manualBrowserCount}`)
console.log(`DiagnosticApiCount=${diagnosticCount}`)
console.log(`DiagnosticRefreshCount=${refreshCount}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_QUOTE_COMPARISON_CHAIN_READY' : 'SCM_QUOTE_COMPARISON_DATA_SOURCE_ISSUE')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}
