import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_LIFECYCLE } from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryStatusModel.js'
import { PURCHASE_INQUIRY_STATE_TRANSITION_RULES } from '../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryStateTransitionRules.js'
import { evaluatePurchaseInquiryTransitionGuard } from '../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryTransitionGuard.js'
import { PURCHASE_INQUIRY_BUSINESS_RULES } from '../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryBusinessRules.js'
import { PURCHASE_INQUIRY_DANGEROUS_ACTIONS, evaluatePurchaseInquiryActionGuard } from '../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryActionGuardRules.js'
import { PURCHASE_INQUIRY_FINANCIAL_BOUNDARY, evaluatePurchaseInquiryFinancialBoundary } from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryFinancialBoundary.js'
import { SCM_PURCHASE_INQUIRY_RULE_PROFILE } from '../src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.2'
export const TARGET_STATUS = 'PURCHASE_INQUIRY_RULE_ENGINE_READY'

const expectedLifecycle = ['draft', 'issued', 'quoted', 'evaluating', 'approved', 'closed']
const passingFacts = Object.freeze({
  'draft:issued': Object.freeze({ inquiryNo: 'INQ-DEFINITION', lineCount: 1, sourcePurchaseRequest: 'PR-DEFINITION', supplierScope: ['SUPPLIER-DEFINITION'] }),
  'issued:quoted': Object.freeze({ quoteCount: 1, supplierExists: true, quoteLineCount: 1, currencyConsistent: true }),
  'quoted:evaluating': Object.freeze({ validQuoteCount: 1, quoteComparison: 'COMPARISON-DEFINITION' }),
  'evaluating:approved': Object.freeze({ recommendedSupplier: 'SUPPLIER-DEFINITION', comparisonReason: 'definition-only evidence' }),
  'approved:closed': Object.freeze({ archiveCompleted: true, pendingActionCount: 0 }),
})
const verifyTransition = (fromStatus, toStatus) => evaluatePurchaseInquiryTransitionGuard({ fromStatus, toStatus, facts: passingFacts[`${fromStatus}:${toStatus}`] })
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyPurchaseInquiryRules() {
  const activation = activateAcceptanceFramework('SCM')
  const registeredProfile = activation.ruleProfiles?.find(profile => profile.profileCode === 'SCM_PURCHASE_INQUIRY_RULE_PROFILE')
  const rules = Object.freeze([
    rule('RULE-001', '状态链完整', JSON.stringify(PURCHASE_INQUIRY_LIFECYCLE) === JSON.stringify(expectedLifecycle) && PURCHASE_INQUIRY_STATE_TRANSITION_RULES.length === 5 && PURCHASE_INQUIRY_BUSINESS_RULES.length === 5 && registeredProfile === SCM_PURCHASE_INQUIRY_RULE_PROFILE, PURCHASE_INQUIRY_STATE_TRANSITION_RULES),
    rule('RULE-002', 'draft→issued', verifyTransition('draft', 'issued').result === 'PASS', verifyTransition('draft', 'issued')),
    rule('RULE-003', 'issued→quoted', verifyTransition('issued', 'quoted').result === 'PASS', verifyTransition('issued', 'quoted')),
    rule('RULE-004', 'quoted→evaluating', verifyTransition('quoted', 'evaluating').result === 'PASS', verifyTransition('quoted', 'evaluating')),
    rule('RULE-005', 'evaluating→approved', verifyTransition('evaluating', 'approved').result === 'PASS', verifyTransition('evaluating', 'approved')),
    rule('RULE-006', 'approved→closed', verifyTransition('approved', 'closed').result === 'PASS', verifyTransition('approved', 'closed')),
    rule('RULE-007', '逆向阻断', evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'approved', toStatus: 'evaluating' }).reason === 'reverse_transition_forbidden', evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'approved', toStatus: 'evaluating' })),
    rule('RULE-008', '跨级阻断', evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'quoted' }).reason === 'skip_transition_forbidden', evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'quoted' })),
    rule('RULE-009', '危险Action阻断', PURCHASE_INQUIRY_DANGEROUS_ACTIONS.every(action => evaluatePurchaseInquiryActionGuard({ status: 'draft', action }).result === 'FAIL'), PURCHASE_INQUIRY_DANGEROUS_ACTIONS),
    rule('RULE-010', 'Finance边界', PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.allowedFacts.every(fact => evaluatePurchaseInquiryFinancialBoundary({ fact }).result === 'PASS') && PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseInquiryFinancialBoundary({ action }).result === 'FAIL') && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, PURCHASE_INQUIRY_FINANCIAL_BOUNDARY),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    registry: Object.freeze({ activated: activation.activated, activationMode: registeredProfile?.activationMode, ruleProfileCode: registeredProfile?.profileCode, ruleProfileCount: activation.ruleProfileCount }),
    businessRuleCount: PURCHASE_INQUIRY_BUSINESS_RULES.length,
    actionGuardCount: 6,
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writePurchaseInquiryRulesVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-inquiry-rules'))
  const report = verifyPurchaseInquiryRules()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseInquiryRulesVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}
