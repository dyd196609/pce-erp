import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { SUPPLIER_QUOTE_DOMAIN_MODEL, validateSupplierQuoteDomainModel } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteDomainModel.js'
import { SUPPLIER_QUOTE_LINE_DOMAIN_MODEL, validateSupplierQuoteLineDomainModel } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteLineDomainModel.js'
import { validateSupplierQuote } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteValidationRules.js'
import { evaluateQuoteComparison } from '../../src/meta/domain/scm/purchaseInquiry/quote/quoteComparisonRules.js'
import { evaluateSupplierRecommendation } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierRecommendationRules.js'
import { evaluateSupplierQuoteActionGuard } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteActionGuardRules.js'
import { evaluateSupplierQuoteFinancialBoundary } from '../../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteFinancialBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifySupplierQuoteComparisonModel, writeSupplierQuoteComparisonVerification } from '../../scripts/verifySupplierQuoteComparisonModelV1142853.mjs'

const baseQuote = () => ({ quoteNo: 'QUOTE-DEFINITION', inquiryNo: 'INQ-DEFINITION', supplierCode: 'SUPPLIER-DEFINITION', currency: 'CNY', validUntil: '2030-12-31T23:59:59.000Z', lines: [{ materialCode: 'MAT-DEFINITION', currency: 'CNY' }], valid: true })
const validationContext = { inquiryCurrency: 'CNY', asOfDate: '2026-08-02T00:00:00.000Z' }

test('SupplierQuote注册且保持定义型隔离', () => {
  assert.equal(SUPPLIER_QUOTE_DOMAIN_MODEL.objectCode, 'SCM_SUPPLIER_QUOTE')
  assert.equal(validateSupplierQuoteDomainModel().result, 'PASS')
  assert.equal(SUPPLIER_QUOTE_DOMAIN_MODEL.automaticCreation, false)
})

test('QuoteLine必须关联SupplierQuote且禁止独立创建', () => {
  assert.equal(validateSupplierQuoteLineDomainModel().result, 'PASS')
  assert.equal(SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.parentObject, 'SCM_SUPPLIER_QUOTE')
  assert.equal(SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.independentCreationAllowed, false)
})

test('空报价被阻断', () => {
  assert.equal(validateSupplierQuote({}, validationContext).result, 'FAIL')
})

test('无供应商报价被阻断', () => {
  const quote = baseQuote()
  quote.supplierCode = ''
  const result = validateSupplierQuote(quote, validationContext)
  assert.equal(result.result, 'FAIL')
  assert.equal(result.rules.find(rule => rule.ruleCode === 'QUOTE-RULE-002').result, 'FAIL')
})

test('过期报价被阻断', () => {
  const quote = baseQuote()
  quote.validUntil = '2026-08-01T23:59:59.000Z'
  const result = validateSupplierQuote(quote, validationContext)
  assert.equal(result.result, 'FAIL')
  assert.equal(result.rules.find(rule => rule.ruleCode === 'QUOTE-RULE-005').result, 'FAIL')
})

test('比价必须同时满足有效报价、比较条件和推荐依据', () => {
  const pass = evaluateQuoteComparison({ quoteList: [baseQuote()], evaluationCriteria: ['price'], recommendedSupplier: 'SUPPLIER-DEFINITION', comparisonReason: 'best price evidence' })
  assert.equal(pass.result, 'PASS')
  assert.equal(evaluateQuoteComparison({ quoteList: [baseQuote()], evaluationCriteria: [], recommendedSupplier: 'SUPPLIER-DEFINITION', comparisonReason: 'missing criteria' }).result, 'FAIL')
})

test('推荐供应商要求有效报价和已完成比价', () => {
  const pass = evaluateSupplierRecommendation({ validQuotes: [baseQuote()], comparisonCompleted: true, recommendedSupplier: 'SUPPLIER-DEFINITION', reason: 'best price evidence', evidence: ['QUOTE-DEFINITION'] })
  assert.equal(pass.result, 'PASS')
  assert.equal(evaluateSupplierRecommendation({ validQuotes: [baseQuote()], comparisonCompleted: false, recommendedSupplier: 'SUPPLIER-DEFINITION', reason: 'not completed', evidence: ['QUOTE-DEFINITION'] }).result, 'FAIL')
  assert.equal(pass.createsPurchaseOrder, false)
})

test('创建采购订单Action在所有状态被阻断', () => {
  for (const status of ['draft', 'received', 'valid', 'compared', 'closed']) assert.equal(evaluateSupplierQuoteActionGuard({ status, action: 'createPurchaseOrder' }).result, 'FAIL')
})

test('Finance执行动作被阻断', () => {
  for (const action of ['paymentExecution', 'bankTransfer', 'ledgerPosting', 'settlement']) assert.equal(evaluateSupplierQuoteFinancialBoundary({ action }).result, 'FAIL')
  assert.equal(evaluateSupplierQuoteFinancialBoundary({ fact: 'quoteAmount' }).result, 'PASS')
})

test('Acceptance Profile只读激活且验证归档无业务写入', async () => {
  const activation = activateAcceptanceFramework('SCM')
  const codes = activation.acceptanceProfiles.map(profile => profile.profileCode)
  assert.equal(codes.includes('SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE'), true)
  assert.equal(codes.includes('SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE'), true)
  assert.equal(activation.businessWriteCount, 0)
  assert.equal(activation.productionUserDataWritten, false)
  const report = verifySupplierQuoteComparisonModel()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'supplier-quote-comparison-'))
  await writeSupplierQuoteComparisonVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'SUPPLIER_QUOTE_COMPARISON_MODEL_READY')
  assert.equal(archived.productionUserDataWritten, false)
})
