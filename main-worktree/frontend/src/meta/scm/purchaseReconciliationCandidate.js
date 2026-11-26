import { stableBusinessActionTextHash } from '../core/action-gate/businessActionGateIntegrity.js'

export const PURCHASE_RECONCILIATION_PRECHECK_VERSION = 'V1.14.2.8.4.7.36'
export const PURCHASE_RECONCILIATION_SOURCE_TYPE = 'supplier_settlement'
export const PURCHASE_RECONCILIATION_RUNTIME_CREATION_ALLOWED = false

export const purchaseReconciliationEvidenceStatuses = ['complete', 'incomplete', 'conflict', 'read_failed']
export const purchaseReconciliationEligibilityStatuses = ['eligible', 'blocked', 'already_exists', 'conflict', 'invalid_source']
export const purchaseReconciliationTargetExistenceStatuses = ['not_found', 'single_target', 'multiple_targets', 'read_failed']

export const purchaseReconciliationPrecheckRuleCodes = [
  'PRC_SOURCE_EXISTS', 'PRC_SOURCE_TYPE_VALID', 'PRC_SOURCE_STATUS_RECONCILING', 'PRC_CONTEXT_EXISTING_SETTLEMENT',
  'PRC_EVIDENCE_COMPLETE', 'PRC_SOURCE_SETTLEMENT_NO_PRESENT', 'PRC_SUPPLIER_ID_PRESENT', 'PRC_SUPPLIER_NAME_PRESENT',
  'PRC_LEGAL_ENTITY_PRESENT', 'PRC_LEDGER_BOOK_PRESENT', 'PRC_CURRENCY_PRESENT', 'PRC_EXCHANGE_RATE_VALID',
  'PRC_QUANTITY_VALID', 'PRC_UNIT_PRESENT', 'PRC_AMOUNT_VALID', 'PRC_PAYABLE_CHECK_RELATION_PRESENT',
  'PRC_PAYABLE_PREPARE_RELATION_PRESENT', 'PRC_PURCHASE_ORDER_RELATION_PRESENT', 'PRC_PRICE_APPROVAL_RELATION_PRESENT',
  'PRC_SUPPLIER_CONSISTENT', 'PRC_CURRENCY_CONSISTENT', 'PRC_AMOUNT_CONSISTENT', 'PRC_SOURCE_KEY_VALID',
  'PRC_NO_EXISTING_TARGET', 'PRC_SINGLE_TARGET_INVARIANT', 'PRC_RUNTIME_CREATION_DISABLED', 'PRC_ZERO_WRITE_INVARIANT',
]

const clone = (value) => JSON.parse(JSON.stringify(value ?? null))
const text = (value) => String(value ?? '').trim()
const identity = (value) => text(value).toUpperCase()
const currencyCode = (value) => identity(value)
const number = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}
const equalAmount = (left, right) => Math.abs(number(left) - number(right)) < 0.000001

export const purchaseReconciliationMappingMatrix = [
  ['sourceSupplierSettlementNo', 'supplierSettlement', 'settlementNo', true, 'trim + uppercase', 'blocked'],
  ['supplierId', 'supplierSettlement', 'supplierId', true, 'trim + uppercase', 'blocked'],
  ['supplierName', 'supplierSettlement', 'supplierName', true, 'trim', 'blocked'],
  ['tenantId', 'supplierSettlement', 'tenantId', false, 'trim + uppercase', 'nullable'],
  ['legalEntityId', 'supplierSettlement/precheckSnapshot', 'legalEntityId', true, 'trim + uppercase', 'must_complete_before_generation'],
  ['legalEntityName', 'supplierSettlement/precheckSnapshot', 'legalEntityName', false, 'trim', 'nullable'],
  ['ledgerBookId', 'supplierSettlement/precheckSnapshot', 'ledgerBookId', true, 'trim + uppercase', 'must_complete_before_generation'],
  ['ledgerBookName', 'supplierSettlement/precheckSnapshot', 'ledgerBookName', false, 'trim', 'nullable'],
  ['businessUnitId', 'supplierSettlement/precheckSnapshot', 'businessUnitId', false, 'trim + uppercase', 'nullable'],
  ['businessUnitName', 'supplierSettlement/precheckSnapshot', 'businessUnitName', false, 'trim', 'nullable'],
  ['currency', 'supplierSettlement/precheckSnapshot', 'currency', true, 'trim + uppercase', 'must_complete_before_generation'],
  ['exchangeRate', 'supplierSettlement/precheckSnapshot', 'exchangeRate', true, 'number > 0', 'blocked'],
  ['quantity', 'supplierSettlement', 'settlementQuantity', true, 'number > 0', 'blocked'],
  ['unit', 'supplierSettlement', 'unit', true, 'trim', 'blocked'],
  ['amount', 'supplierSettlement', 'settlementAmount', true, 'number > 0; settlement amount basis', 'blocked'],
  ['taxAmount', 'supplierSettlement', 'taxAmount', false, 'number when present', 'nullable'],
  ['amountIncludingTax', 'supplierSettlement', 'amountIncludingTax', false, 'number when present', 'nullable'],
  ['amountExcludingTax', 'supplierSettlement', 'amountExcludingTax', false, 'number when present', 'nullable'],
  ['sourcePayableCheckNo', 'supplierSettlement upstream relation', 'sourcePayableCheckNo', true, 'trim + uppercase', 'blocked'],
  ['sourcePayablePrepareNo', 'supplierSettlement upstream relation', 'sourcePayablePrepareNo', true, 'trim + uppercase', 'blocked'],
  ['purchaseOrderNo', 'supplierSettlement upstream relation', 'sourcePurchaseOrderNo', true, 'trim + uppercase', 'blocked'],
  ['priceApprovalNo', 'supplierSettlement upstream relation', 'sourcePriceApprovalNo', true, 'trim + uppercase', 'blocked'],
  ['receiptNo', 'supplierSettlement upstream relation', 'sourceReceiveNo', true, 'trim + uppercase', 'blocked'],
  ['inspectionNo', 'supplierSettlement upstream relation', 'sourceInspectionNo', true, 'trim + uppercase', 'blocked'],
  ['warehouseTaskNo', 'supplierSettlement upstream relation', 'sourceWarehouseTaskNo', true, 'trim + uppercase', 'blocked'],
  ['inventoryTransactionNo', 'supplierSettlement upstream relation', 'sourceInventoryTransactionNos[0]', true, 'trim + uppercase', 'blocked'],
].map(([targetField, sourceObject, sourceField, required, normalization, missingHandling]) => ({ targetField, sourceObject, sourceField, required, normalization, missingHandling }))

export function normalizePurchaseReconciliationCandidateInput(input = {}) {
  const source = clone(input.sourceSettlement || {}) || {}
  const upstream = clone(input.upstreamEvidence || {}) || {}
  return {
    sourceExists: Boolean(input.sourceSettlement && typeof input.sourceSettlement === 'object'),
    sourceType: identity(input.sourceType || PURCHASE_RECONCILIATION_SOURCE_TYPE).toLowerCase(),
    contextState: text(input.contextState),
    sourceSettlement: {
      ...source,
      settlementNo: identity(source.settlementNo), supplierId: identity(source.supplierId), supplierName: text(source.supplierName),
      tenantId: identity(source.tenantId), legalEntityId: identity(source.legalEntityId), legalEntityName: text(source.legalEntityName),
      ledgerBookId: identity(source.ledgerBookId), ledgerBookName: text(source.ledgerBookName),
      businessUnitId: identity(source.businessUnitId), businessUnitName: text(source.businessUnitName),
      currency: currencyCode(source.currency), exchangeRate: number(source.exchangeRate),
      settlementQuantity: number(source.settlementQuantity), unit: text(source.unit), settlementAmount: number(source.settlementAmount),
      taxAmount: source.taxAmount == null ? null : number(source.taxAmount),
      amountIncludingTax: source.amountIncludingTax == null ? null : number(source.amountIncludingTax),
      amountExcludingTax: source.amountExcludingTax == null ? null : number(source.amountExcludingTax),
      sourcePayableCheckNo: identity(source.sourcePayableCheckNo), sourcePayablePrepareNo: identity(source.sourcePayablePrepareNo),
      sourcePurchaseOrderNo: identity(source.sourcePurchaseOrderNo || source.purchaseOrderNo), sourcePriceApprovalNo: identity(source.sourcePriceApprovalNo),
      sourceReceiveNo: identity(source.sourceReceiveNo || source.receiveNo), sourceInspectionNo: identity(source.sourceInspectionNo || source.inspectionNo),
      sourceWarehouseTaskNo: identity(source.sourceWarehouseTaskNo),
      sourceInventoryTransactionNos: (source.sourceInventoryTransactionNos || source.inventoryTransactionNos || []).map(identity).filter(Boolean),
      settlementStatus: text(source.settlementStatus),
    },
    upstreamEvidence: {
      ...upstream, supplierId: identity(upstream.supplierId), currency: currencyCode(upstream.currency), amount: number(upstream.amount),
    },
    targetEvidence: Array.isArray(input.targetEvidence) ? clone(input.targetEvidence) : null,
    writeMetrics: clone(input.writeMetrics || { purchaseReconciliationWrites: 0, supplierSettlementStatusWrites: 0, paymentObjectWrites: 0, formalNumberAllocations: 0, localStorageWrites: 0, networkWriteRequests: 0 }),
  }
}

export function buildPurchaseReconciliationSourceKey(input = {}) {
  const normalized = input.sourceSettlement ? normalizePurchaseReconciliationCandidateInput(input) : input
  const source = normalized.sourceSettlement || {}
  if (!source.legalEntityId || !source.ledgerBookId || !source.settlementNo) return ''
  return [source.legalEntityId, source.ledgerBookId, PURCHASE_RECONCILIATION_SOURCE_TYPE, source.settlementNo].map(identity).join('::')
}

export function resolvePurchaseReconciliationTargetExistence(sourceKey, targetEvidence = []) {
  if (!Array.isArray(targetEvidence)) return { status: 'read_failed', targetCount: 0, targetNos: [] }
  const matches = targetEvidence.filter((item) => identity(item.sourceKey) === identity(sourceKey))
  const targetNos = matches.map((item) => text(item.targetNo || item.purchaseReconciliationNo)).filter(Boolean)
  if (matches.length === 0) return { status: 'not_found', targetCount: 0, targetNos }
  if (matches.length === 1) return { status: 'single_target', targetCount: 1, targetNos }
  return { status: 'multiple_targets', targetCount: matches.length, targetNos }
}

export function mapSupplierSettlementToReconciliationCandidate(input = {}) {
  const normalized = normalizePurchaseReconciliationCandidateInput(input)
  const source = normalized.sourceSettlement
  const sourceKey = buildPurchaseReconciliationSourceKey(normalized)
  const candidate = {
    candidateId: sourceKey ? `PRC-CAND-${stableBusinessActionTextHash(sourceKey)}` : '', sourceKey,
    sourceType: PURCHASE_RECONCILIATION_SOURCE_TYPE, sourceSupplierSettlementNo: source.settlementNo,
    tenantId: source.tenantId, legalEntityId: source.legalEntityId, legalEntityName: source.legalEntityName,
    ledgerBookId: source.ledgerBookId, ledgerBookName: source.ledgerBookName,
    businessUnitId: source.businessUnitId, businessUnitName: source.businessUnitName,
    supplierId: source.supplierId, supplierName: source.supplierName, supplierSettlementNo: source.settlementNo,
    currency: source.currency, exchangeRate: source.exchangeRate, quantity: source.settlementQuantity, unit: source.unit,
    amount: source.settlementAmount, amountBasis: 'settlement_amount', taxAmount: source.taxAmount,
    amountIncludingTax: source.amountIncludingTax, amountExcludingTax: source.amountExcludingTax,
    sourcePayableCheckNo: source.sourcePayableCheckNo, sourcePayablePrepareNo: source.sourcePayablePrepareNo,
    purchaseOrderNo: source.sourcePurchaseOrderNo, priceApprovalNo: source.sourcePriceApprovalNo,
    receiptNo: source.sourceReceiveNo, inspectionNo: source.sourceInspectionNo, warehouseTaskNo: source.sourceWarehouseTaskNo,
    inventoryTransactionNo: source.sourceInventoryTransactionNos[0] || '',
  }
  const mapping = purchaseReconciliationMappingMatrix.map((definition) => ({
    ...definition, actual: candidate[definition.targetField] ?? '',
    mappingResult: definition.required && (candidate[definition.targetField] === '' || candidate[definition.targetField] == null) ? 'missing' : 'mapped',
  }))
  return { normalized, candidate, mapping }
}

function rule(code, passed, actual, expected, sourceField, message, severity = 'error') {
  return { code, status: passed ? 'passed' : 'blocked', severity, message, actual, expected, sourceField }
}

export function evaluatePurchaseReconciliationEligibility(input = {}) {
  const { normalized, candidate, mapping } = mapSupplierSettlementToReconciliationCandidate(input)
  const source = normalized.sourceSettlement
  const upstream = normalized.upstreamEvidence
  const sourceKey = candidate.sourceKey
  const existence = resolvePurchaseReconciliationTargetExistence(sourceKey, normalized.targetEvidence)
  const requiredMappingMissing = mapping.filter((item) => item.required && item.mappingResult === 'missing')
  const supplierConsistent = !upstream.supplierId || upstream.supplierId === source.supplierId
  const currencyConsistent = !upstream.currency || upstream.currency === source.currency
  const amountConsistent = !upstream.amount || equalAmount(upstream.amount, source.settlementAmount)
  const zeroWrite = Object.values(normalized.writeMetrics || {}).every((value) => number(value) === 0)
  const provisionalEvidenceComplete = normalized.sourceExists && requiredMappingMissing.length === 0 && supplierConsistent && currencyConsistent && amountConsistent && existence.status !== 'read_failed'
  const rules = [
    rule('PRC_SOURCE_EXISTS', normalized.sourceExists, normalized.sourceExists, true, 'sourceSettlement', '供应商结算来源必须存在'),
    rule('PRC_SOURCE_TYPE_VALID', normalized.sourceType === PURCHASE_RECONCILIATION_SOURCE_TYPE, normalized.sourceType, PURCHASE_RECONCILIATION_SOURCE_TYPE, 'sourceType', '直接来源类型必须是供应商结算'),
    rule('PRC_SOURCE_STATUS_RECONCILING', source.settlementStatus === 'reconciling', source.settlementStatus, 'reconciling', 'settlementStatus', '供应商结算必须处于可进入采购对账的状态'),
    rule('PRC_CONTEXT_EXISTING_SETTLEMENT', normalized.contextState === 'existing_settlement', normalized.contextState, 'existing_settlement', 'contextState', '来源上下文必须已解析到供应商结算目标'),
    rule('PRC_EVIDENCE_COMPLETE', provisionalEvidenceComplete, provisionalEvidenceComplete, true, 'mapping', '必要来源证据必须完整且一致'),
    rule('PRC_SOURCE_SETTLEMENT_NO_PRESENT', Boolean(candidate.sourceSupplierSettlementNo), candidate.sourceSupplierSettlementNo, 'non-empty', 'settlementNo', '供应商结算编号必须存在'),
    rule('PRC_SUPPLIER_ID_PRESENT', Boolean(candidate.supplierId), candidate.supplierId, 'non-empty', 'supplierId', '供应商编号必须存在'),
    rule('PRC_SUPPLIER_NAME_PRESENT', Boolean(candidate.supplierName), candidate.supplierName, 'non-empty', 'supplierName', '供应商名称必须存在'),
    rule('PRC_LEGAL_ENTITY_PRESENT', Boolean(candidate.legalEntityId), candidate.legalEntityId, 'non-empty', 'legalEntityId', '法人维度必须在正式生成前补齐'),
    rule('PRC_LEDGER_BOOK_PRESENT', Boolean(candidate.ledgerBookId), candidate.ledgerBookId, 'non-empty', 'ledgerBookId', '账套维度必须在正式生成前补齐'),
    rule('PRC_CURRENCY_PRESENT', Boolean(candidate.currency), candidate.currency, 'ISO currency code', 'currency', '币种必须存在'),
    rule('PRC_EXCHANGE_RATE_VALID', candidate.exchangeRate > 0, candidate.exchangeRate, '> 0', 'exchangeRate', '汇率必须大于0'),
    rule('PRC_QUANTITY_VALID', candidate.quantity > 0, candidate.quantity, '> 0', 'settlementQuantity', '数量必须大于0'),
    rule('PRC_UNIT_PRESENT', Boolean(candidate.unit), candidate.unit, 'non-empty', 'unit', '单位必须存在'),
    rule('PRC_AMOUNT_VALID', candidate.amount > 0, candidate.amount, '> 0', 'settlementAmount', '结算金额必须大于0'),
    rule('PRC_PAYABLE_CHECK_RELATION_PRESENT', Boolean(candidate.sourcePayableCheckNo), candidate.sourcePayableCheckNo, 'non-empty', 'sourcePayableCheckNo', '应付核对关系必须存在'),
    rule('PRC_PAYABLE_PREPARE_RELATION_PRESENT', Boolean(candidate.sourcePayablePrepareNo), candidate.sourcePayablePrepareNo, 'non-empty', 'sourcePayablePrepareNo', '应付预备关系必须存在'),
    rule('PRC_PURCHASE_ORDER_RELATION_PRESENT', Boolean(candidate.purchaseOrderNo), candidate.purchaseOrderNo, 'non-empty', 'sourcePurchaseOrderNo', '采购订单关系必须存在'),
    rule('PRC_PRICE_APPROVAL_RELATION_PRESENT', Boolean(candidate.priceApprovalNo), candidate.priceApprovalNo, 'non-empty', 'sourcePriceApprovalNo', '核价关系必须存在'),
    rule('PRC_SUPPLIER_CONSISTENT', supplierConsistent, upstream.supplierId || candidate.supplierId, candidate.supplierId, 'upstreamEvidence.supplierId', '供应商必须与上游证据一致'),
    rule('PRC_CURRENCY_CONSISTENT', currencyConsistent, upstream.currency || candidate.currency, candidate.currency, 'upstreamEvidence.currency', '币种必须与上游证据一致'),
    rule('PRC_AMOUNT_CONSISTENT', amountConsistent, upstream.amount || candidate.amount, candidate.amount, 'upstreamEvidence.amount', '结算金额必须与来源证据一致'),
    rule('PRC_SOURCE_KEY_VALID', Boolean(sourceKey), sourceKey, 'non-empty deterministic key', 'sourceKey', '唯一来源键必须有效'),
    rule('PRC_NO_EXISTING_TARGET', existence.status === 'not_found', existence.targetCount, 0, 'targetEvidence', '不得已有采购对账目标'),
    rule('PRC_SINGLE_TARGET_INVARIANT', existence.targetCount <= 1, existence.targetCount, '<= 1', 'targetEvidence', '同一来源最多对应一个目标'),
    rule('PRC_RUNTIME_CREATION_DISABLED', PURCHASE_RECONCILIATION_RUNTIME_CREATION_ALLOWED === false, false, false, 'runtimeExecutionAllowed', '本版本固定禁止运行时创建'),
    rule('PRC_ZERO_WRITE_INVARIANT', zeroWrite, normalized.writeMetrics, 'all zero', 'writeMetrics', '预检查必须保持零写入'),
  ]
  let evidenceStatus = 'complete'
  if (!normalized.sourceExists || existence.status === 'read_failed') evidenceStatus = 'read_failed'
  else if (requiredMappingMissing.length) evidenceStatus = 'incomplete'
  else if (!supplierConsistent || !currencyConsistent || !amountConsistent || existence.status === 'multiple_targets') evidenceStatus = 'conflict'
  let businessEligibility = 'eligible'
  if (!normalized.sourceExists || normalized.sourceType !== PURCHASE_RECONCILIATION_SOURCE_TYPE) businessEligibility = 'invalid_source'
  else if (existence.status === 'multiple_targets') businessEligibility = 'conflict'
  else if (existence.status === 'single_target') businessEligibility = 'already_exists'
  else if (rules.some((item) => item.status === 'blocked' && !['PRC_NO_EXISTING_TARGET'].includes(item.code))) businessEligibility = 'blocked'
  return {
    candidate: { ...candidate, evidenceStatus, businessEligibility, runtimeExecutionAllowed: false, targetExistenceStatus: existence.status,
      blockingReasonCodes: rules.filter((item) => item.status === 'blocked').map((item) => item.code), warningCodes: [],
      mappingCompleteness: mapping.filter((item) => item.mappingResult === 'mapped').length / mapping.length },
    mapping, rules, evidenceStatus, businessEligibility, runtimeExecutionAllowed: false,
    targetExistenceStatus: existence.status, targetCount: existence.targetCount, targetNos: existence.targetNos,
    amountComparison: { sourceAmount: upstream.amount, candidateAmount: candidate.amount, difference: number(candidate.amount) - number(upstream.amount) },
    writeMetrics: normalized.writeMetrics,
  }
}

export function buildPurchaseReconciliationPrecheckResult(input = {}) {
  return evaluatePurchaseReconciliationEligibility(input)
}
