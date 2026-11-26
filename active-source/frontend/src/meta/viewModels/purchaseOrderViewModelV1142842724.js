import { resolveCanonicalPurchaseOrderNumberV11428427211 } from
  './purchaseOrderBusinessNumberViewModelV1142842729.js'

export const PURCHASE_ORDER_BUSINESS_VIEW_VERSION_V1142842724 = 'V1.14.2.8.4.27.2.13'
export const PURCHASE_ORDER_DOCUMENT_VIEW_VERSION_V11428427242 = 'V1.14.2.8.4.27.2.4.2'
export const PURCHASE_ORDER_VIEW_PERMISSION_RULE_V1142842724 =
  'PURCHASE_ORDER_VIEW_PERMISSION-001'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0

export const PURCHASE_ORDER_VIEW_ROLES_V1142842724 = freeze({
  buyer: freeze({ code: 'buyer', label: '采购人员视图', exportLabel: '采购人员版' }),
  warehouse: freeze({ code: 'warehouse', label: '仓库视图', exportLabel: '仓库版' }),
  supplier: freeze({ code: 'supplier', label: '供应商视图', exportLabel: '供应商版' }),
  management: freeze({ code: 'management', label: '管理视图', exportLabel: '管理版' }),
})

const materialColumns = freeze({
  lineNo: freeze({ key: 'lineNo', label: '序号', width: 70 }),
  supplierName: freeze({ key: 'supplierName', label: '供应商', width: 180 }),
  materialCode: freeze({ key: 'materialCode', label: '物料编码', width: 130 }),
  materialName: freeze({ key: 'materialName', label: '物料名称', width: 160 }),
  specification: freeze({ key: 'specification', label: '规格', width: 140 }),
  unit: freeze({ key: 'unit', label: '单位', width: 80 }),
  quantity: freeze({ key: 'quantity', label: '数量', width: 100 }),
  unitPrice: freeze({ key: 'unitPrice', label: '采购执行单价', width: 130 }),
  amount: freeze({ key: 'amount', label: '金额', width: 120 }),
  priceSourceLabel: freeze({ key: 'priceSourceLabel', label: '价格来源', width: 150 }),
  plannedDeliveryDate: freeze({ key: 'plannedDeliveryDate', label: '计划到货日期', width: 140 }),
  deliverySourceLabel: freeze({ key: 'deliverySourceLabel', label: '交期来源', width: 160 }),
  receiptStatusLabel: freeze({ key: 'receiptStatusLabel', label: '收货状态', width: 110 }),
  remark: freeze({ key: 'remark', label: '备注', width: 180 }),
})

const columnKeysByRole = freeze({
  buyer: freeze(['lineNo', 'materialCode', 'materialName', 'specification', 'unit',
    'quantity', 'unitPrice', 'amount', 'plannedDeliveryDate', 'receiptStatusLabel', 'remark']),
  warehouse: freeze(['lineNo', 'materialCode', 'materialName', 'specification', 'unit',
    'quantity', 'plannedDeliveryDate', 'receiptStatusLabel']),
  supplier: freeze(['lineNo', 'materialCode', 'materialName', 'specification', 'unit',
    'quantity', 'unitPrice', 'amount', 'plannedDeliveryDate', 'receiptStatusLabel']),
  management: freeze(Object.keys(materialColumns)),
})

export const PURCHASE_ORDER_VIEW_PERMISSION_V1142842724 = freeze({
  buyer: freeze({ sourceTrace: true, approval: true, lifecycle: true, internalRemark: true,
    price: true, supplierEvaluation: false, recommendationEvidence: true }),
  warehouse: freeze({ sourceTrace: false, approval: false, lifecycle: true, internalRemark: false,
    price: false, supplierEvaluation: false, recommendationEvidence: false }),
  supplier: freeze({ sourceTrace: false, approval: false, lifecycle: true, internalRemark: false,
    price: true, supplierEvaluation: false, recommendationEvidence: false }),
  management: freeze({ sourceTrace: true, approval: true, lifecycle: true, internalRemark: true,
    price: true, supplierEvaluation: true, recommendationEvidence: true }),
})

const lifecycleLabels = freeze({
  draft: '草稿', pending_approval: '待审批', approved: '已审批', issued: '已下达',
  partially_received: '部分收货', completed: '完成', cancelled: '取消',
  submitted: '已提交', reviewed: '已审核', rechecked: '已复核', converted: '已转换',
  released: '已发布', ordered: '已订购', partiallyReceived: '部分收货', receiving: '收货中',
  received: '已收货', fullyReceived: '全部收货', closed: '已关闭',
})

const approvalLabels = freeze({
  not_started: '未发起', pending_approval: '待审批', approved: '已审批',
  rejected: '已驳回', cancelled: '已取消', pending: '待审批', passed: '已通过',
})

const receiptLabels = freeze({
  not_received: '未收货', pending: '待收货', issued: '待收货', partially_received: '部分收货',
  partiallyReceived: '部分收货', receiving: '收货中', received: '已收货',
  fully_received: '全部收货', fullyReceived: '全部收货', completed: '全部收货',
})

const urgencyLabels = freeze({
  normal: '正常', general: '一般', warning: '一般', urgent: '紧急',
  critical: '特急', overdue: '特急', unknown: '未知/待确认',
})

function chineseLabel(value, labels, fallback = '待确认') {
  const source = text(value)
  if (!source) return fallback
  if (/[^\x00-\x7F]/.test(source)) return source
  return labels[source] || fallback
}

function uniqueTexts(values = []) {
  return freeze([...new Set(values.flatMap(value => Array.isArray(value) ? value : [value])
    .map(text).filter(Boolean))])
}

function collectSourceIds(purchaseOrder, orderLines, keys) {
  const relations = purchaseOrder.sourceRelations || purchaseOrder.SourceRelations || {}
  const sourceTrace = purchaseOrder.sourceTrace || {}
  const traceAliases = {
    sourcePurchaseRequestIds: 'purchaseRequestIds',
    sourceInquiryIds: 'inquiryIds',
    sourceQuoteComparisonIds: 'quoteComparisonIds',
    priceApprovalResultNo: 'priceApprovalResultIds',
    supplierMaterialPriceNo: 'supplierMaterialPriceIds',
  }
  return uniqueTexts([
    ...keys.map(key => purchaseOrder[key]),
    ...keys.map(key => relations[key]),
    ...keys.map(key => sourceTrace[key] || sourceTrace[traceAliases[key]]),
    ...orderLines.flatMap(line => keys.map(key => line[key])),
  ])
}

export function resolvePurchaseOrderViewAccessV1142842724(runtimeRole = 'manager') {
  const role = text(runtimeRole).toLowerCase()
  const direct = Object.keys(PURCHASE_ORDER_VIEW_ROLES_V1142842724).find(code => role === code)
  const activeRole = direct || (role.includes('warehouse') || role.includes('仓') ? 'warehouse'
    : role.includes('supplier') || role.includes('供应商') ? 'supplier'
      : role.includes('buyer') || role.includes('采购') ? 'buyer' : 'management')
  const allowedRoles = activeRole === 'management'
    ? Object.keys(PURCHASE_ORDER_VIEW_ROLES_V1142842724) : [activeRole]
  return freeze({
    runtimeRole: text(runtimeRole) || 'manager',
    activeRole,
    allowedRoles: freeze(allowedRoles),
    canPreviewRole: activeRole === 'management',
    permissionRule: PURCHASE_ORDER_VIEW_PERMISSION_RULE_V1142842724,
  })
}

function materialRow(line, purchaseOrder, index) {
  const quantity = number(line.confirmedQuantity ?? line.quantity ?? line.planQuantity)
  const unitPrice = number(line.confirmedPrice ?? line.planPrice ?? line.price ?? line.unitPrice)
  const receiptStatus = text(line.receiptStatus || line.receivingStatus
    || purchaseOrder.receiptStatus || purchaseOrder.lifecycleStatus || purchaseOrder.status)
  return freeze({
    id: text(line.id) || `purchase-order-line-${index + 1}`,
    purchaseOrderId: text(line.purchaseOrderId),
    purchaseOrderItemId: text(line.id),
    lineNo: number(line.lineNo) || index + 1,
    supplierName: text(line.supplierName || purchaseOrder.supplierName) || '-',
    materialCode: text(line.materialCode) || '-',
    materialName: text(line.materialName) || '-',
    specification: text(line.specification || line.spec) || '-',
    unit: text(line.unit) || '-',
    purchaseRequestItemId: text(line.purchaseRequestItemId),
    sourcePurchaseRequestNo: text(line.sourcePurchaseRequestNo),
    materialMasterId: text(line.materialMasterId),
    materialMasterBound: line.materialMasterBound === true,
    materialMaintenanceStatus: text(line.materialMaintenanceStatus),
    sourceTrace: line.sourceTrace || null,
    quantity,
    unitPrice,
    amount: number(line.amount ?? line.planAmount),
    priceSource: text(line.priceSource),
    priceSourceLabel: text(line.priceSourceLabel) || '来源未追溯',
    supplierMaterialPriceId: text(line.supplierMaterialPriceId),
    supplierMaterialPriceNo: text(line.supplierMaterialPriceNo),
    priceApprovalResultId: text(line.priceApprovalResultId),
    priceApprovalResultNo: text(line.priceApprovalResultNo),
    priceEffectiveDate: text(line.priceEffectiveDate) || '-',
    taxRate: text(line.taxRate) || '-',
    currency: text(line.currency) || '-',
    plannedDeliveryDate: text(line.confirmedDeliveryDate || line.plannedDeliveryDate
      || line.plannedArrivalDate || line.planDeliveryDate || line.expectedDeliveryDate
      || line.expectedDate || purchaseOrder.plannedArrivalDate) || '待确认',
    deliverySource: text(line.deliverySource),
    deliverySourceLabel: text(line.deliverySourceLabel) || '来源未追溯',
    receiptStatusLabel: chineseLabel(receiptStatus, receiptLabels, '未收货'),
    remark: text(line.remark || line.supplierRemark) || '-',
  })
}

export function buildPurchaseOrderViewModelV1142842724({
  purchaseOrder = {}, orderLines = [], lifecycleDetail = {}, viewRole = 'buyer',
} = {}) {
  const role = PURCHASE_ORDER_VIEW_ROLES_V1142842724[viewRole] ? viewRole : 'buyer'
  const permissions = PURCHASE_ORDER_VIEW_PERMISSION_V1142842724[role]
  const lines = Array.isArray(orderLines) ? orderLines : []
  const materialRows = freeze(lines.map((line, index) => materialRow(line, purchaseOrder, index)))
  const sourceTrace = { ...(purchaseOrder.sourceTrace || {}), ...(lifecycleDetail.sourceTrace || {}) }
  const canonicalNumber = resolveCanonicalPurchaseOrderNumberV11428427211(purchaseOrder)
  const objectNo = canonicalNumber.value
  const gateReference = text(purchaseOrder.sourceRelations?.gateReference
    || sourceTrace.sourceGateId || purchaseOrder.sourceGateId)
  const sourceGroups = freeze([
    freeze({ nodeCode: 'purchase_request', label: '采购申请', values: uniqueTexts([
      sourceTrace.sourcePurchaseRequestIds,
      collectSourceIds(purchaseOrder, lines, ['sourcePurchaseRequestId',
        'sourcePurchaseRequestIds', 'sourcePurchaseRequestNo', 'sourcePurchaseRequestNos',
        'purchaseRequestId', 'purchaseRequestIds']),
    ]) }),
    freeze({ nodeCode: 'purchase_inquiry', label: '询价', values: collectSourceIds(purchaseOrder, lines,
      ['sourceInquiryId', 'sourceInquiryIds', 'sourcePurchaseInquiryId',
        'sourcePurchaseInquiryIds', 'purchaseInquiryId', 'purchaseInquiryIds']) }),
    freeze({ nodeCode: 'quote_comparison', label: '报价比较', values: collectSourceIds(purchaseOrder, lines,
      ['sourceQuoteComparisonId', 'sourceQuoteComparisonIds', 'quoteComparisonId',
        'quoteComparisonIds']) }),
    freeze({ nodeCode: 'price_approval', label: '核价', values: collectSourceIds(purchaseOrder, lines,
      ['sourcePriceApprovalId', 'sourcePriceApprovalIds', 'priceApprovalId', 'priceApprovalIds',
        'priceApprovalResultId', 'priceApprovalResultNo']) }),
    freeze({ nodeCode: 'supplier_material_price', label: '供应商物料有效价格', values:
      collectSourceIds(purchaseOrder, lines, ['supplierMaterialPriceId', 'supplierMaterialPriceNo']) }),
    freeze({ nodeCode: 'supplier_recommendation', label: '供应商推荐', values: collectSourceIds(purchaseOrder, lines,
      ['sourceRecommendationId', 'sourceRecommendationIds', 'supplierRecommendationId',
        'supplierRecommendationIds']) }),
    freeze({ nodeCode: 'purchase_order_gate', label: '采购订单准入Gate', values: uniqueTexts([
      gateReference,
      collectSourceIds(purchaseOrder, lines, ['sourceGateId', 'sourceGateIds',
        'gateId', 'gateIds']),
    ]) }),
    freeze({ nodeCode: 'purchase_order', label: '采购订单', values: uniqueTexts([objectNo]) }),
  ])
  const summarizedSourceGroups = freeze(sourceGroups.map(group => freeze({
    ...group,
    summary: group.values.length ? `已关联（${group.values.length}条）` : '历史数据不可追溯',
    fullEvidence: group.values.join('；'),
  })))
  const status = text(purchaseOrder.lifecycleStatus || purchaseOrder.status)
  const urgencyCode = text(purchaseOrder.deliveryUrgencyCode || purchaseOrder.deliveryUrgency)
  const urgencyLabel = chineseLabel(purchaseOrder.deliveryUrgencyLabel || urgencyCode,
    urgencyLabels, '未知/待确认')
  const columns = freeze(columnKeysByRole[role].map(key => materialColumns[key]))
  const totalQuantity = materialRows.reduce((sum, row) => sum + row.quantity, 0)
  const totalAmount = materialRows.reduce((sum, row) => sum + row.amount, 0)
  const lifecycleHistory = freeze((lifecycleDetail.lifecycleHistory || []).map(item => freeze({
    ...item,
    statusLabel: chineseLabel(item.statusLabel || item.status, lifecycleLabels),
  })))
  const approvalHistory = freeze((lifecycleDetail.approvalDisplay?.history || []).map(item => freeze({
    resultLabel: chineseLabel(item.resultLabel || item.result || item.status, approvalLabels),
    approvedBy: text(item.approvedBy || item.actor) || '-',
    approvedAt: text(item.approvedAt || item.at) || '-',
    opinion: text(item.opinion || item.comment || item.reason) || '-',
  })))

  return freeze({
    version: PURCHASE_ORDER_BUSINESS_VIEW_VERSION_V1142842724,
    role,
    roleLabel: PURCHASE_ORDER_VIEW_ROLES_V1142842724[role].label,
    permissions,
    identity: freeze({
      objectNo: objectNo || '-',
      objectId: text(purchaseOrder.id),
      objectIdVisible: false,
      objectNoField: canonicalNumber.field || 'unavailable',
      identitySource: 'PurchaseOrder.objectNo',
      businessNoParsed: false,
      numberSeparated: true,
    }),
    baseInfo: freeze({
      objectNo: objectNo || '-',
      supplierName: text(purchaseOrder.supplierName || lifecycleDetail.baseInfo?.supplierName
        || purchaseOrder.supplierId) || '-',
      purchaseModeLabel: text(purchaseOrder.purchaseModeLabel) || '-',
      priceSourceLabel: text(purchaseOrder.priceSourceLabel) || '-',
      buyerName: text(purchaseOrder.buyerName || purchaseOrder.buyerId) || '-',
      orderDate: text(purchaseOrder.purchaseDate || purchaseOrder.orderDate
        || purchaseOrder.createdAt) || '-',
      plannedDeliveryDate: text(purchaseOrder.plannedDeliveryDate || purchaseOrder.deliveryDate
        || purchaseOrder.plannedArrivalDate || purchaseOrder.planDeliveryDate) || '待确认',
      statusLabel: chineseLabel(status, lifecycleLabels),
      totalQuantity,
      totalAmount,
      currency: text(purchaseOrder.currency) || 'CNY',
      purchaseOrderType: text(purchaseOrder.purchaseOrderTypeLabel
        || purchaseOrder.purchaseOrderType || purchaseOrder.purchaseType) || '标准采购',
      businessPurpose: text(purchaseOrder.businessPurpose || purchaseOrder.purchasePurpose)
        || '常规采购执行',
      urgencyLabel,
      urgencyLevel: urgencyLabel,
      paymentTerms: text(purchaseOrder.paymentTerms) || '-',
      deliveryAddress: text(purchaseOrder.deliveryAddress) || '-',
      deliveryRequirements: text(purchaseOrder.deliveryRequirements
        || purchaseOrder.deliveryRequirement || purchaseOrder.receiptRequirement) || '-',
      remark: permissions.internalRemark ? text(purchaseOrder.remark) || '-' : '按角色权限隐藏',
      orderTypeLabel: text(lifecycleDetail.baseInfo?.orderTypeLabel) || '采购订单',
    }),
    supplierInfo: freeze({
      supplierName: text(purchaseOrder.supplierName) || '-',
      contactName: text(purchaseOrder.supplierContact) || '-',
      contactPhone: text(purchaseOrder.supplierPhone) || '-',
      registeredAddress: text(purchaseOrder.supplierAddress) || '-',
      deliveryAddress: text(purchaseOrder.supplierDeliveryAddress) || '-',
      factSource: text(purchaseOrder.supplierInformationSource) || 'SupplierMaster',
      manuallyEditable: false,
    }),
    urgency: freeze({
      code: urgencyCode || 'unknown',
      label: urgencyLabel,
      factSource: text(purchaseOrder.deliveryUrgencySource) || '权威交期风险事实未接入',
      calculatedByPage: false,
      manuallyEditable: false,
    }),
    sourceTrace: freeze({
      visible: permissions.sourceTrace,
      traceable: sourceTrace.traceable === true || purchaseOrder.priceTraceStatus === 'CURRENT_LINKED',
      sourceLabel: '采购申请 → 询价 → 报价比较 → 核价 → 供应商物料有效价格 → Gate准入 → 采购订单',
      groups: summarizedSourceGroups,
    }),
    materialDetail: freeze({
      columns,
      rows: materialRows,
      source: lifecycleDetail.purchaseOrderItemSource || 'PurchaseOrderItem[]',
      purchaseOrderItemCount: number(lifecycleDetail.materialCountConsistency?.purchaseOrderItemCount
        ?? materialRows.length),
      displayCount: materialRows.length,
      countConsistent: lifecycleDetail.materialCountConsistency?.consistent !== false
        && number(lifecycleDetail.materialCountConsistency?.purchaseOrderItemCount
          ?? materialRows.length) === materialRows.length,
      fallbackSourceUsed: false,
    }),
    lifecycle: freeze({
      ...lifecycleDetail.lifecycle,
      lifecycleStatusLabel: chineseLabel(lifecycleDetail.lifecycle?.lifecycleStatusLabel || status, lifecycleLabels),
      steps: freeze((lifecycleDetail.lifecycle?.steps || []).map(step => freeze({
        ...step, label: chineseLabel(step.label || step.status, lifecycleLabels),
      }))),
      history: lifecycleHistory,
      nextAction: freeze({
        ...(lifecycleDetail.nextAction || {}),
        label: text(lifecycleDetail.nextAction?.label) || '无可用动作',
      }),
    }),
    approval: freeze({
      visible: permissions.approval,
      statusLabel: chineseLabel(lifecycleDetail.approvalStatusLabel
        || lifecycleDetail.approvalDisplay?.status, approvalLabels),
      approvedBy: text(lifecycleDetail.approvalDisplay?.approvedBy) || '-',
      approvedAt: text(lifecycleDetail.approvalDisplay?.approvedAt) || '-',
      opinion: text(lifecycleDetail.approvalDisplay?.opinion) || '-',
      history: approvalHistory,
    }),
    documentMaker: freeze({
      createdBy: text(lifecycleDetail.documentMaker?.createdBy
        || purchaseOrder.createdBy || purchaseOrder.creatorName
        || purchaseOrder.buyerName || purchaseOrder.buyerId) || '-',
      createdAt: text(lifecycleDetail.documentMaker?.createdAt
        || purchaseOrder.createdAt || purchaseOrder.orderDate) || '-',
    }),
    priceBoundary: freeze({
      displayName: '采购执行价格',
      qualifiedMaterialPriceVisible: false,
      materialMasterAutoUpdate: false,
      message: '合格采购价格归属物料档案价格历史；采购订单仅展示采购执行价格。',
    }),
    exportTemplate: freeze({
      templateCode: `PURCHASE_ORDER_EXPORT_${role.toUpperCase()}`,
      templateLabel: PURCHASE_ORDER_VIEW_ROLES_V1142842724[role].exportLabel,
      columns,
      inheritsViewPermission: true,
    }),
    dataProtection: freeze({ projectionOnly: true, businessWriteCount: 0,
      purchaseOrderChanged: false, legacyOrderChanged: false, databaseChanged: false }),
  })
}
