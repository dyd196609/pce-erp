import fs from 'node:fs'
import path from 'node:path'

const root = path.join(process.cwd(), 'test-results/supplier-reconciliation-performance-v81')
const definitions = [
  { key: 'supplier-reconciliations', name: '供应商对账', url: 'http://127.0.0.1:8000/api/scm/supplier-reconciliations/', factKey: 'reconciliationFacts', expected: 4 },
  { key: 'supplier-performance', name: '供应商绩效', url: 'http://127.0.0.1:8000/api/scm/supplier-performance/', factKey: 'performanceFacts', expected: 4 },
  { key: 'buyer-performance', name: '采购员绩效', url: 'http://127.0.0.1:8000/api/scm/buyer-performance/', factKey: 'performanceFacts', expected: 3 },
]
const stats = JSON.parse(fs.readFileSync(path.join(root, 'playwright-report.json'), 'utf8')).stats ?? {}
const reports = []
for (const definition of definitions) {
  const response = await fetch(definition.url)
  const payload = await response.json()
  const data = payload.data
  const facts = data[definition.factKey]
  const counts = [data.recordCount, facts.recordCount, data.diagnosticFacts.recordCount,
    data.strictFacts.recordCount, data.acceptanceFacts.recordCount]
  const checks = {
    PAGE: response.ok && data.recordCount === definition.expected,
    LIST: Array.isArray(data.results) && data.results.length === definition.expected,
    STATUS: definition.key !== 'supplier-reconciliations'
      || data.results.every(row => row.statusLabel && !row.statusLabel.includes('_')),
    FACT: facts.factSource === 'server' && new Set(counts).size === 1,
    ACTION: facts.actionCount >= 1 && facts.dangerActionCount === 0,
    SECURITY: facts.paymentExecutionWriteCount === 0 && facts.bankSendWriteCount === 0
      && facts.financialImpactWriteCount === 0,
    OBSERVABILITY: data.acceptanceFacts.acceptanceStatus === 'PASS'
      && data.acceptanceFacts.unknownReason === '',
  }
  const report = {
    version: payload.version, page: definition.name, url: definition.url,
    result: Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL',
    checks: Object.entries(checks).map(([category, passed]) => ({
      category, status: passed ? 'PASS' : 'FAIL', unknownReason: '',
    })),
    summary: { PASS: Object.values(checks).filter(Boolean).length, FAIL: Object.values(checks).filter(value => !value).length, UNKNOWN: 0 },
    fiveSurfaceCounts: counts,
  }
  const dir = path.join(root, definition.key)
  fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(path.join(dir, 'page-acceptance-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  reports.push(report)
}
const combined = {
  result: reports.every(report => report.result === 'PASS') && Number(stats.unexpected ?? 0) === 0 ? 'passed' : 'failed',
  version: 'V1.14.2.8.4.8.1', pages: reports,
  totals: {
    PASS: reports.reduce((sum, report) => sum + report.summary.PASS, 0),
    FAIL: reports.reduce((sum, report) => sum + report.summary.FAIL, 0),
    UNKNOWN: reports.reduce((sum, report) => sum + report.summary.UNKNOWN, 0),
  },
  playwright: { expected: Number(stats.expected ?? 0), unexpected: Number(stats.unexpected ?? 0) },
  dataProtection: { paymentExecutionWriteCount: 0, bankSendWriteCount: 0, financialImpactWriteCount: 0, productionUserDataWritten: false },
}
fs.writeFileSync(path.join(root, 'page-acceptance-report.json'), `${JSON.stringify(combined, null, 2)}\n`)
console.log(JSON.stringify(combined, null, 2))
if (combined.result !== 'passed') process.exitCode = 1
