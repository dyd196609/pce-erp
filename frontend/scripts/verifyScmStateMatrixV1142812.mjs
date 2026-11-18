import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import {
  evaluateScmStateCombination,
  SCM_STATE_RULE_REGISTRY_VERSION,
} from '../src/meta/schema/scm/scmStateRuleRegistry.js'

const cases = Object.freeze([
  ['purchaseRequest', 'draft', 'mayCreateInquiry', false],
  ['purchaseRequest', 'approved', 'mayCreateInquiry', true],
  ['purchaseRequest', 'converted', 'mayCreatePriceApproval', true],
  ['purchaseRequest', 'closed', 'mayCreateInquiry', false],
  ['purchaseInquiry', 'draft', 'mayCreateEligibility', false],
  ['purchaseInquiry', 'approved', 'mayCreateEligibility', true],
  ['purchaseInquiry', 'closed', 'mayCreateEligibility', false],
  ['priceApproval', 'draft', 'mayCreatePurchaseOrder', false],
  ['priceApproval', 'processing', 'mayCreatePurchaseOrder', false],
  ['priceApproval', 'completed', 'mayCreatePurchaseOrder', true],
  ['purchaseOrder', 'draft', 'mayReceive', false],
  ['purchaseOrder', 'issued', 'mayReceive', true],
  ['purchaseOrder', 'partial_received', 'mayReceive', true],
  ['purchaseOrder', 'completed', 'mayReceive', false],
  ['quality', 'pending', 'mayInbound', false],
  ['quality', 'qualified', 'mayInbound', true],
  ['quality', 'rejected', 'mayInbound', false],
  ['inbound', 'planned', 'mayComplete', true],
  ['inbound', 'completed', 'mayComplete', false],
])

export function verifyScmStateMatrixV1142812({ writeReport = true } = {}) {
  const results = cases.map(([documentType, status, capability, expectedAllowed]) => {
    const evaluated = evaluateScmStateCombination(documentType, status, capability)
    const passed = evaluated.result === 'PASS' && evaluated.allowed === expectedAllowed
    return { documentType, status, capability, expectedAllowed, actualAllowed: evaluated.allowed, result: passed ? 'PASS' : 'FAIL', reason: passed ? '' : evaluated.reason }
  })
  const report = {
    version: SCM_STATE_RULE_REGISTRY_VERSION,
    ruleCount: results.length,
    PASS: results.filter((item) => item.result === 'PASS').length,
    FAIL: results.filter((item) => item.result === 'FAIL').length,
    UNKNOWN: 0,
    result: results.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL',
    results,
  }
  if (writeReport) {
    const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
    const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-consistency-v1142812')
    mkdirSync(outputDir, { recursive: true })
    writeFileSync(join(outputDir, 'scm_state_matrix_v1142812_report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  }
  return report
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const report = verifyScmStateMatrixV1142812()
  console.log(JSON.stringify(report, null, 2))
  if (report.result !== 'PASS') process.exitCode = 1
}

