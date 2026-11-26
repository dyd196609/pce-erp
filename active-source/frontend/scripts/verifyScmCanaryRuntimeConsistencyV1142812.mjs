import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { isScmActionAllowed } from '../src/meta/schema/scm/scmStateRuleRegistry.js'
import { evaluateScmInboundQuantity } from '../src/meta/schema/scm/scmInboundQuantityRule.js'
import { evaluateScmRuntimeConsistency } from '../src/meta/scm/scmRuntimeConsistencyGuard.js'

function consistentSnapshot(prefix, quantity) {
  return {
    purchaseRequests: [{ id: `${prefix}-pr`, requestNo: `${prefix}-PR`, status: 'converted' }],
    purchaseInquiries: [{ id: `${prefix}-inq`, inquiryNo: `${prefix}-INQ`, requestId: `${prefix}-pr`, status: 'approved' }],
    priceApprovals: [{ id: `${prefix}-pa`, inquiryId: `${prefix}-inq`, status: 'completed' }],
    purchaseOrderCreationEligibilities: [{ id: `${prefix}-eligibility`, sourceInquiryId: `${prefix}-inq`, eligibilityStatus: 'eligible' }],
    incomingInspections: [{ id: `${prefix}-iqc`, status: 'inboundPrepared', lines: [{ inspectResult: 'qualified', qualifiedQty: quantity, concessionQty: 0 }] }],
    warehouseTasks: [{ id: `${prefix}-task`, taskType: 'qualifiedInboundPrepare', sourceInspectionId: `${prefix}-iqc`, plannedQuantity: quantity, completedQuantity: 0, status: 'pending' }],
  }
}

export function verifyScmCanaryRuntimeConsistencyV1142812({ writeReport = true } = {}) {
  const quantityCases = [1, 10, 1000, 100000].map((quantity) => ({
    quantity,
    canary: evaluateScmInboundQuantity({ warehousePlanQuantity: quantity, completedQuantity: 0, qualifiedQuantity: quantity }),
    enterprise: evaluateScmInboundQuantity({ warehousePlanQuantity: quantity, completedQuantity: 0, qualifiedQuantity: quantity }),
  })).map((item) => ({
    ...item,
    result: item.canary.allowed && item.enterprise.allowed && item.canary.result === item.enterprise.result ? 'PASS' : 'FAIL',
  }))
  const canaryGuard = evaluateScmRuntimeConsistency(consistentSnapshot('CANARY', 1000))
  const enterpriseGuard = evaluateScmRuntimeConsistency(consistentSnapshot('ENTERPRISE', 100000))
  const brokenRelationship = consistentSnapshot('BROKEN-REL', 10)
  brokenRelationship.priceApprovals = []
  const brokenEligibility = consistentSnapshot('BROKEN-ELIG', 10)
  brokenEligibility.purchaseOrderCreationEligibilities = []
  const brokenQuantity = consistentSnapshot('BROKEN-QTY', 10)
  brokenQuantity.warehouseTasks[0].plannedQuantity = 11
  const anomalyCases = [
    ['SCM-RUNTIME-001', evaluateScmRuntimeConsistency(brokenRelationship)],
    ['SCM-RUNTIME-002', evaluateScmRuntimeConsistency(brokenEligibility)],
    ['SCM-RUNTIME-003', evaluateScmRuntimeConsistency(brokenQuantity)],
  ].map(([expectedCode, guard]) => ({ expectedCode, actualCodes: guard.issues.map((item) => item.code), result: guard.issues.some((item) => item.code === expectedCode) ? 'PASS' : 'FAIL' }))
  const buttonCases = [
    ['convertRequest', 'approved', true],
    ['convertRequest', 'draft', false],
    ['convertInquiry', 'approved', true],
    ['convertInquiry', 'closed', false],
    ['convertApproval', 'approved', true],
    ['convertApproval', 'draft', false],
  ].map(([action, status, expected]) => ({ action, status, expected, actual: isScmActionAllowed(action, status) }))
    .map((item) => ({ ...item, result: item.actual === item.expected ? 'PASS' : 'FAIL' }))
  const checks = [
    { code: 'CANARY-RUNTIME-001', result: canaryGuard.result === 'PASS' ? 'PASS' : 'FAIL', evidence: canaryGuard },
    { code: 'CANARY-RUNTIME-002', result: enterpriseGuard.result === 'PASS' ? 'PASS' : 'FAIL', evidence: enterpriseGuard },
    { code: 'CANARY-RUNTIME-003', result: quantityCases.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL', evidence: quantityCases },
    { code: 'CANARY-RUNTIME-004', result: anomalyCases.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL', evidence: anomalyCases },
    { code: 'CANARY-RUNTIME-005', result: buttonCases.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL', evidence: buttonCases },
  ]
  const report = {
    version: 'V1.14.2.8.4.12',
    comparison: 'canary_vs_enterprise_same_rules',
    checks,
    PASS: checks.filter((item) => item.result === 'PASS').length,
    FAIL: checks.filter((item) => item.result === 'FAIL').length,
    UNKNOWN: 0,
    result: checks.every((item) => item.result === 'PASS') ? 'PASS' : 'FAIL',
    productionUserDataWritten: false,
  }
  if (writeReport) {
    const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
    const outputDir = join(frontendRoot, 'test-results', 'scm-purchase-consistency-v1142812')
    mkdirSync(outputDir, { recursive: true })
    writeFileSync(join(outputDir, 'scm_canary_runtime_consistency_v1142812_report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  }
  return report
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const report = verifyScmCanaryRuntimeConsistencyV1142812()
  console.log(JSON.stringify(report, null, 2))
  if (report.result !== 'PASS') process.exitCode = 1
}

