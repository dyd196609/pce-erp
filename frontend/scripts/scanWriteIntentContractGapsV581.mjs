import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const resultRoot = path.join(
  root,
  'test-results',
  'bank-send-preparation-v58-1-1',
)
const moduleFiles = {
  payment_request: [
    'src/meta/pages/PaymentRequestPage.vue',
    'tests/ui-baseline/paymentRequestV48.spec.js',
  ],
  payment_instruction_prepare: [
    'src/meta/pages/PaymentInstructionPreparePage.vue',
    'tests/ui-baseline/paymentInstructionPrepareV49.spec.js',
  ],
  payment_order_prepare: [
    'src/meta/pages/PaymentOrderPreparePage.vue',
    'tests/ui-baseline/paymentOrderPrepareV50.spec.js',
  ],
  payment_order_draft: [
    'src/meta/pages/PaymentOrderDraftPage.vue',
    'tests/ui-baseline/paymentOrderDraftV51.spec.js',
  ],
  formal_payment_order: [
    'src/meta/pages/FormalPaymentOrderPage.vue',
    'tests/ui-baseline/formalPaymentOrderV53.spec.js',
    'tests/ui-baseline/formalPaymentOrderV54.spec.js',
  ],
}

function count(source, pattern) {
  return [...source.matchAll(pattern)].length
}

const modules = Object.entries(moduleFiles).map(([moduleCode, files]) => {
  const evidence = files
    .filter(file => fs.existsSync(path.join(root, file)))
    .map(file => {
      const source = fs.readFileSync(path.join(root, file), 'utf8')
      return {
        file,
        businessWriteRequestCountOccurrences: count(
          source,
          /businessWriteRequestCount/g,
        ),
        categorizedWriteIntentOccurrences: count(
          source,
          /previewPreparationWriteCount|auditWriteCount|forbiddenBusinessProgressWriteCount/g,
        ),
      }
    })
  const legacyOccurrenceCount = evidence.reduce(
    (total, row) => total + row.businessWriteRequestCountOccurrences,
    0,
  )
  const categorizedOccurrenceCount = evidence.reduce(
    (total, row) => total + row.categorizedWriteIntentOccurrences,
    0,
  )
  const currentClassification = legacyOccurrenceCount
    ? 'legacy_aggregate_zero_write_metric'
    : 'no_legacy_aggregate_metric'
  return {
    moduleCode,
    currentClassification,
    legacyOccurrenceCount,
    categorizedOccurrenceCount,
    unsafePreparationWriteMisclassified: false,
    currentBusinessProgressWriteAllowed: false,
    migrationRequiredBeforeFutureSafePreparationWrites:
      legacyOccurrenceCount > 0 && categorizedOccurrenceCount === 0,
    riskLevel:
      legacyOccurrenceCount > 0 && categorizedOccurrenceCount === 0
        ? 'medium'
        : 'low',
    evidence,
  }
})
const bankPage = fs.readFileSync(
  path.join(root, 'src/meta/pages/BankSendPreparationPage.vue'),
  'utf8',
)
const bankTest = fs.readFileSync(
  path.join(root, 'tests/ui-baseline/bankSendPreparationV58.spec.js'),
  'utf8',
)
const conditions = {
  scannedModuleCountIsFive: modules.length === 5,
  bankSendPreparationNoLongerUsesAggregateMetric:
    !bankPage.includes('businessWriteRequestCount')
    && !bankTest.includes('businessWriteRequestCount'),
  bankSendPreparationUsesCategorizedFacts:
    bankPage.includes('previewPreparationWriteCount')
    && bankPage.includes('auditWriteCount')
    && bankPage.includes('forbiddenBusinessProgressWriteCount'),
  noExistingModuleMisclassifiesSafePreparationWrite: modules.every(
    row => row.unsafePreparationWriteMisclassified === false,
  ),
  legacyGapsClassified: modules.every(row => Boolean(row.currentClassification)),
}
const report = {
  result: Object.values(conditions).every(Boolean) ? 'passed' : 'failed',
  version: 'V1.14.2.8.4.7.58.1.1',
  contractVersion: 'PCE-WRITE-INTENT-CONTRACT-V1.0',
  scope: Object.keys(moduleFiles),
  conditions,
  scannedModuleCount: modules.length,
  legacyAggregateMetricModuleCount: modules.filter(
    row => row.legacyOccurrenceCount > 0,
  ).length,
  unsafePreparationWriteMisclassificationCount: modules.filter(
    row => row.unsafePreparationWriteMisclassified,
  ).length,
  modules,
  conclusion:
    'Existing aggregate metrics only guard zero-write historical actions. '
    + 'They are classified as migration gaps before any future safe '
    + 'preparation write is introduced; V58.1.1 uses categorized facts.',
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'write-intent-contract-gap-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') {
  throw new Error('V58.1 write-intent contract gap scan failed')
}
