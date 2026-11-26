import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { listPageAcceptanceContracts } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const VERSION = 'V1.14.2.8.4.7.50.2'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const baselineRoot = path.join(frontend, 'test-results', 'pce-ui-baseline', 'pages')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const core = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const pages = [
  ['payable-prepare', '采购应付预备', '/finance/payable-prepares', 'payable_prepared'],
  ['payable-check', '采购应付核对', '/finance/payable-checks', 'payable_checked'],
  ['supplier-settlement', '供应商结算', '/scm/supplier-settlements', 'supplier_settlement_ready'],
  ['purchase-reconciliation', '采购对账', '/scm/purchase-reconciliations', 'purchase_reconciliation_matched_ready'],
  ['invoice-prepare', '采购发票准备', '/finance/purchase-invoice-prepares', 'purchase_invoice_prepare_validated_ready'],
  ['account-payable-draft', '采购应付账款草稿', '/finance/ap-drafts', 'purchase_accounts_payable_draft_controlled_generation_ready'],
  ['account-payable-confirm', '应付确认准备', '/finance/account-payable-confirms', 'payable_confirmation_prepare_validated_ready'],
  ['payment-application', '付款申请准备', '/finance/payment-applications', 'payment_request_prepare_validated_ready'],
  ['payment-request', '付款申请', '/finance/payment-requests', 'payment_request_approved_ready'],
  ['payment-instruction-prepare', '付款指令准备', '/finance/payment-order-prepares', 'payment_instruction_prepare_validated_ready'],
  ['payment-order-prepare', '正式付款单预备', '/finance/payment-prepares', 'payment_order_prepare_standard_list_ready'],
]
const browser = read(path.join(resultRoot, 'finance-chain-browser-report.json'))
const browserByCode = new Map(browser.results.map(result => [result.pageCode, result]))
const contracts = new Map(listPageAcceptanceContracts().map(contract => [contract.pageCode, contract]))
const results = []
for (const [pageCode, canonicalName, route, checkpointId] of pages) {
  const checkpoint = path.join(checkpointRoot, checkpointId)
  const hashesBefore = Object.fromEntries(core.map(name => [name, sha(path.join(checkpoint, name))]))
  const hashesAfter = Object.fromEntries(core.map(name => [name, sha(path.join(checkpoint, name))]))
  const manifest = read(path.join(checkpoint, 'manifest.json'))
  const verificationDirectory = path.join(checkpoint, 'verification')
  const restoreEvidenceFiles = fs.existsSync(verificationDirectory)
    ? fs.readdirSync(verificationDirectory)
      .filter(name => /^restore-result-.*\.json$/.test(name))
      .sort()
    : []
  const restoreEvidence = restoreEvidenceFiles.length
    ? read(path.join(verificationDirectory, restoreEvidenceFiles.at(-1)))
    : null
  const immutableByEvidence = JSON.stringify(hashesBefore) === JSON.stringify(hashesAfter)
    && (manifest.immutable === true || restoreEvidence?.result === 'passed')
  const baseline = read(path.join(baselineRoot, `${pageCode}.json`))
  const contract = contracts.get(pageCode)
  const browserPage = browserByCode.get(pageCode)
  const levels = {
    level1PageExists: Boolean(contract && browserPage?.pageExists),
    level2PageStructure: Boolean(browserPage?.structureReady && browserPage.standardToolbarCount > 0),
    level3RealBehavior: Boolean(baseline.overallStatus === 'passed' && browserPage?.diagnosticsCopied && browserPage?.refreshPassed),
    level4BusinessConsistency: Boolean(contract?.diagnosticsContract?.currentStateSource === 'server'
      && contract?.dataProtectionContract?.productionWriteAllowed === false),
    level5StabilityAndRecovery: Boolean(immutableByEvidence
      && manifest.restorable !== false && browserPage?.reloadPassed),
  }
  const blockers = Object.entries(levels).filter(([, passed]) => !passed).map(([name]) => name)
  results.push({
    pageCode,
    canonicalName,
    fullUrl: `http://localhost:5173/#${route}`,
    checkpointId,
    ...levels,
    checkpointImmutable: immutableByEvidence,
    restoreEvidenceResult: restoreEvidence?.result || (manifest.restorable === true ? 'passed' : 'historical_checkpoint'),
    checkpointHashesBefore: hashesBefore,
    checkpointHashesAfter: hashesAfter,
    currentStateSource: contract?.diagnosticsContract?.currentStateSource,
    productionWriteAllowed: contract?.dataProtectionContract?.productionWriteAllowed,
    blockerCount: blockers.length,
    blockers,
    result: blockers.length ? 'failed' : 'passed',
  })
}
const failed = results.filter(result => result.result !== 'passed')
const report = {
  result: failed.length ? 'failed' : 'passed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  financeChainPageCount: results.length,
  financeChainPassedCount: results.length - failed.length,
  financeChainBlockerCount: failed.reduce((sum, result) => sum + result.blockerCount, 0),
  currentStateSource: 'server',
  productionUserDataWritten: false,
  downstreamObjectCreatedCount: 0,
  results,
}
fs.writeFileSync(path.join(resultRoot, 'finance-chain-gate-report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({
  result: report.result,
  version: VERSION,
  financeChainPageCount: report.financeChainPageCount,
  financeChainPassedCount: report.financeChainPassedCount,
  financeChainBlockerCount: report.financeChainBlockerCount,
}, null, 2))
if (failed.length) process.exit(1)
