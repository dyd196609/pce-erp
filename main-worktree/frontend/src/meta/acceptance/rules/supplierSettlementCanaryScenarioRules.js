export const SUPPLIER_SETTLEMENT_CANARY_RULESET_VERSION = 'PCE-SUPPLIER-SETTLEMENT-CANARY-V861'

export const supplierSettlementCanaryScenarioRules = Object.freeze([
  Object.freeze({ ruleId: 'CANARY-001', title: '标准流程通过' }),
  Object.freeze({ ruleId: 'CANARY-002', title: '质量异常正确阻断' }),
  Object.freeze({ ruleId: 'CANARY-003', title: '差异流程正确生成' }),
  Object.freeze({ ruleId: 'CANARY-004', title: '金额链一致' }),
  Object.freeze({ ruleId: 'CANARY-005', title: '供应商绩效来源正确' }),
  Object.freeze({ ruleId: 'CANARY-006', title: '采购员绩效来源正确' }),
  Object.freeze({ ruleId: 'CANARY-007', title: '禁止进入银行发送' }),
  Object.freeze({ ruleId: 'CANARY-008', title: '禁止产生财务影响' }),
])

const result = (ruleId, passed, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  title: supplierSettlementCanaryScenarioRules
    .find(rule => rule.ruleId === ruleId)?.title || '',
  evidence,
})

export function evaluateSupplierSettlementCanaryScenarioRules(group = {}) {
  const scenarios = group.scenarios || {}
  const standardOrders = (group.purchaseOrders || []).filter(row => row.scenario === 'A')
  const standardSupplierCount = new Set(standardOrders.map(row => row.supplierId)).size
  const standardMaterialCount = new Set(standardOrders.flatMap(row => row.materialIds)).size
  const standardPass = standardOrders.length >= 10
    && standardSupplierCount >= 5
    && standardMaterialCount >= 20
    && standardOrders.every(row => row.flowStatus === 'completed')
  const returnedInspection = (group.inspections || []).find(row => row.disposition === 'return')
  const concessionInspection = (group.inspections || []).find(row => row.disposition === 'concession_accept')
  const qualityPass = returnedInspection?.settlementEligible === false
    && concessionInspection?.approvalStatus === 'approved'
    && concessionInspection?.settlementEligible === true
  const quantityDifference = (group.differences || []).find(row => row.type === 'quantity')
  const priceDifference = (group.differences || []).find(row => row.type === 'price')
  const differencePass = quantityDifference?.workflow?.join('>') === 'difference_analysis>supplier_confirmation'
    && priceDifference?.paymentEligible === false
  const approvedPayments = (group.paymentRequests || []).filter(row => row.status === 'approved')
  const invalidPayments = (group.paymentRequests || []).filter(row => row.blockedReason === 'amount_mismatch')
  const amountPass = approvedPayments.length > 0
    && approvedPayments.every(row => row.requestAmount === row.payableAmount)
    && invalidPayments.length > 0
    && invalidPayments.every(row => row.paymentEligible === false)
  const supplierPerformancePass = (group.supplierPerformance || []).length >= 10
    && group.supplierPerformance.every(row => (
      row.factSource === 'server-persisted'
      && row.sourceType === 'SupplierSettlementCompletion'
      && row.sourceIds.length > 0
    ))
  const buyerPerformancePass = (group.buyerPerformance || []).length >= 5
    && group.buyerPerformance.every(row => (
      row.factSource === 'server-persisted'
      && row.sourceType === 'SupplierSettlementCompletion'
      && row.sourceIds.length > 0
      && row.buyerId
    ))
  const protection = group.dataProtection || {}

  return [
    result('CANARY-001', standardPass, {
      supplierCount: standardSupplierCount,
      purchaseOrderCount: standardOrders.length,
      materialCount: standardMaterialCount,
      fullFlowPassed: standardPass,
    }),
    result('CANARY-002', qualityPass, {
      returnBlocked: returnedInspection?.settlementEligible === false,
      concessionApproved: concessionInspection?.approvalStatus === 'approved',
      concessionSettlementEligible: concessionInspection?.settlementEligible === true,
    }),
    result('CANARY-003', differencePass, {
      quantityDifferenceGenerated: Boolean(quantityDifference),
      priceDifferenceGenerated: Boolean(priceDifference),
      priceDifferencePaymentBlocked: priceDifference?.paymentEligible === false,
    }),
    result('CANARY-004', amountPass, {
      approvedPaymentCount: approvedPayments.length,
      amountMismatchBlockedCount: invalidPayments.length,
    }),
    result('CANARY-005', supplierPerformancePass, {
      recordCount: (group.supplierPerformance || []).length,
      sourceType: 'SupplierSettlementCompletion',
    }),
    result('CANARY-006', buyerPerformancePass, {
      recordCount: (group.buyerPerformance || []).length,
      buyerCount: new Set((group.buyerPerformance || []).map(row => row.buyerId)).size,
      sourceType: 'SupplierSettlementCompletion',
    }),
    result('CANARY-007', protection.bankSendWriteCount === 0, {
      bankSendWriteCount: protection.bankSendWriteCount,
      paymentExecutionWriteCount: protection.paymentExecutionWriteCount,
    }),
    result(
      'CANARY-008',
      protection.fundDeductionCount === 0 && protection.financialImpactWriteCount === 0,
      {
        fundDeductionCount: protection.fundDeductionCount,
        financialImpactWriteCount: protection.financialImpactWriteCount,
      },
    ),
  ]
}
