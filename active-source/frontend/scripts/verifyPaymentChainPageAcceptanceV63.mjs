import fs from 'node:fs'
import path from 'node:path'

process.env.PCE_ACCEPTANCE_VERSION = 'V1.14.2.8.4.7.63'
process.env.PCE_ACCEPTANCE_OUTPUT_DIR = 'test-results/payment-chain-observability-v63'
await import('./verifyPaymentChainPageAcceptanceV62.mjs')

const outputRoot = path.resolve(process.cwd(), process.env.PCE_ACCEPTANCE_OUTPUT_DIR)
const sourcePath = path.join(outputRoot, 'payment_chain_page_acceptance_report.json')
const source = JSON.parse(fs.readFileSync(sourcePath, 'utf8'))

const result = passed => (passed ? 'PASS' : 'FAIL')
const pages = source.pages.map(page => {
  const facts = page.acceptanceFacts
  const apiFacts = page.fourEndpointFacts.api
  const dangerousButtonCount = page.actionDecision.ui.dangerousButtons.length
  const checks = [
    {
      id: 'OBS-001',
      result: result(Boolean(facts)),
      evidence: `pageCode=${facts?.pageCode || ''}`,
    },
    {
      id: 'OBS-002',
      result: result(facts?.factSource === 'server'),
      evidence: `factSource=${facts?.factSource || ''}`,
    },
    {
      id: 'OBS-003',
      result: result(
        Number.isInteger(facts?.recordCount)
        && Number(apiFacts?.recordCount) === facts.recordCount,
      ),
      evidence: `api=${apiFacts?.recordCount}; acceptance=${facts?.recordCount}`,
    },
    {
      id: 'OBS-004',
      result: result(facts?.dangerActionCount === dangerousButtonCount),
      evidence: `facts=${facts?.dangerActionCount}; ui=${dangerousButtonCount}`,
    },
    {
      id: 'OBS-005',
      result: result(facts?.businessProgressWriteCount === 0),
      evidence: `businessProgressWriteCount=${facts?.businessProgressWriteCount}`,
    },
    {
      id: 'OBS-006',
      result: result(Number.isInteger(facts?.downstreamObjectCount)),
      evidence: `downstreamObjectCount=${facts?.downstreamObjectCount}`,
    },
  ]
  return {
    page: page.page,
    pageCode: page.pageCode,
    checks,
    pass: checks.filter(check => check.result === 'PASS').length,
    fail: checks.filter(check => check.result === 'FAIL').length,
    acceptanceFacts: facts,
    endpointConsistency: page.fourEndpointFacts,
  }
})

const report = {
  version: 'V1.14.2.8.4.7.63',
  contractVersion: source.contractVersion,
  validator: 'AcceptanceFactsValidator',
  generatedAt: new Date().toISOString(),
  pageCount: pages.length,
  baseAcceptance: {
    totalChecks: source.totalChecks,
    pass: source.pass,
    fail: source.fail,
    unknown: source.unknown,
  },
  observabilityChecks: pages.length * 6,
  observabilityPass: pages.reduce((sum, page) => sum + page.pass, 0),
  observabilityFail: pages.reduce((sum, page) => sum + page.fail, 0),
  unknown: source.unknown,
  pages,
}
fs.writeFileSync(
  path.join(outputRoot, 'payment_chain_page_acceptance_v63_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify({
  outputRoot,
  baseAcceptance: report.baseAcceptance,
  observabilityChecks: report.observabilityChecks,
  observabilityPass: report.observabilityPass,
  observabilityFail: report.observabilityFail,
  unknown: report.unknown,
}, null, 2))
if (
  source.fail > 0
  || source.unknown > 0
  || report.observabilityFail > 0
) process.exitCode = 1
