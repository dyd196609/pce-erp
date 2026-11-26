import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.54.3'
const root = process.cwd()
const readIfPresent = relative => {
  const target = path.join(root, relative)
  return fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : ''
}
const targets = [
  {
    canonicalName: '正式付款单',
    moduleCode: 'formal_payment_order',
    backend: '../backend/formal_payment_order',
    frontend: [
      'src/meta/runtime/formalPaymentOrderRuntime.js',
      'src/meta/pages/FormalPaymentOrderPage.vue',
    ],
  },
  {
    canonicalName: '付款申请',
    moduleCode: 'payment_request',
    backend: '../backend/payment_request',
    frontend: [
      'src/meta/runtime/paymentRequestRuntime.js',
      'src/meta/pages/PaymentRequestPage.vue',
    ],
  },
  {
    canonicalName: '付款准备',
    moduleCode: 'payment_request_prepare',
    backend: '../backend/payment_request_prepare',
    frontend: [
      'src/meta/runtime/paymentRequestPrepareRuntime.js',
      'src/meta/pages/PaymentApplicationPage.vue',
    ],
  },
  {
    canonicalName: '付款指令准备',
    moduleCode: 'payment_instruction_prepare',
    backend: '../backend/payment_instruction_prepare',
    frontend: [
      'src/meta/runtime/paymentInstructionPrepareRuntime.js',
      'src/meta/pages/PaymentInstructionPreparePage.vue',
    ],
  },
  {
    canonicalName: '付款单草稿',
    moduleCode: 'payment_order_draft',
    backend: '../backend/payment_order_draft',
    frontend: [
      'src/meta/runtime/paymentOrderDraftRuntime.js',
      'src/meta/pages/PaymentOrderDraftPage.vue',
    ],
  },
  {
    canonicalName: '正式付款单预备',
    moduleCode: 'payment_order_prepare',
    backend: '../backend/payment_order_prepare',
    frontend: [
      'src/meta/runtime/paymentOrderPrepareRuntime.js',
      'src/meta/pages/PaymentOrderPreparePage.vue',
    ],
  },
]

const collectFiles = target => {
  if (!fs.existsSync(target)) return []
  const stat = fs.statSync(target)
  if (stat.isFile()) return [target]
  return fs.readdirSync(target, { withFileTypes: true }).flatMap(entry => (
    entry.name === '__pycache__' || entry.name === 'migrations'
      ? []
      : collectFiles(path.join(target, entry.name))
  ))
}

const moduleReports = targets.map(target => {
  const backendFiles = collectFiles(path.join(root, target.backend))
    .filter(file => file.endsWith('.py'))
  const frontendFiles = target.frontend
    .map(relative => path.join(root, relative))
    .filter(file => fs.existsSync(file))
  const files = [...backendFiles, ...frontendFiles]
  const source = files.map(file => fs.readFileSync(file, 'utf8')).join('\n')
  const historyReferences = (
    source.match(/statusTransitionHistory|status_transition_history/g) || []
  ).length
  const countReferences = (
    source.match(/statusTransitionCount|status_transition_count/g) || []
  ).length
  const exposesHistory = historyReferences > 0
  const exposesCount = countReferences > 0
  const usesPublicServerBuilder = source.includes('status_transition_facts(')
  const usesClientRuntimeAssertion = source.includes(
    'assertStatusTransitionCountMatchesHistory',
  )
  const silentZeroFallbackCount = (
    source.match(
      /Number\([^\r\n]*statusTransitionCount[^\r\n]*\|\|\s*0|statusTransitionCount\s*:\s*0/g,
    ) || []
  ).length
  const clientCalculatedCount = (
    source.match(
      /statusTransitionCount\s*:\s*[^\r\n]*statusTransitionHistory[^\r\n]*\.length/g,
    ) || []
  ).length
  let classification = 'transition-count-contract-not-exposed'
  let riskLevel = 'legacy-observability-gap'
  if (exposesHistory !== exposesCount) {
    classification = 'incomplete-transition-statistics'
    riskLevel = 'high'
  } else if (exposesHistory && exposesCount) {
    classification = (
      usesPublicServerBuilder
      && usesClientRuntimeAssertion
      && silentZeroFallbackCount === 0
      && clientCalculatedCount === 0
    )
      ? 'count-history-contract-compliant'
      : 'count-history-contract-incomplete'
    riskLevel = classification.endsWith('compliant') ? 'controlled' : 'high'
  }
  return {
    canonicalName: target.canonicalName,
    moduleCode: target.moduleCode,
    scannedFileCount: files.length,
    historyReferences,
    countReferences,
    exposesHistory,
    exposesCount,
    usesPublicServerBuilder,
    usesClientRuntimeAssertion,
    silentZeroFallbackCount,
    clientCalculatedCount,
    sameStatisticalMismatchFound: (
      exposesHistory
      && exposesCount
      && classification !== 'count-history-contract-compliant'
    ),
    classification,
    riskLevel,
  }
})

const report = {
  result: moduleReports.some(row => row.sameStatisticalMismatchFound)
    ? 'failed'
    : 'passed',
  version: VERSION,
  scanName: 'state-transition-count-fact-scan',
  moduleCount: moduleReports.length,
  compliantModuleCount: moduleReports.filter(
    row => row.classification === 'count-history-contract-compliant',
  ).length,
  contractNotExposedModuleCount: moduleReports.filter(
    row => row.classification === 'transition-count-contract-not-exposed',
  ).length,
  sameStatisticalMismatchCount: moduleReports.filter(
    row => row.sameStatisticalMismatchFound,
  ).length,
  allModulesTransitionFactMigrated: moduleReports.every(
    row => row.classification === 'count-history-contract-compliant',
  ),
  moduleReports,
}
const resultRoot = path.join(
  root,
  'test-results',
  'formal-payment-order-v543',
)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'transition-count-scan-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exit(1)
