import {
  buildBusinessPrintViewModelV11428427243,
} from './businessPrintViewModelV11428427243.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_PRINT_VIEW_MODEL_VERSION_V11428427243 =
  'V1.14.2.8.4.27.2.4.3'
export const PURCHASE_ORDER_PRINT_PERMISSION_RULE_V11428427243 =
  'PURCHASE_ORDER_PRINT_PERMISSION-001'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

export const PURCHASE_ORDER_PRINT_PERMISSION_V11428427243 = freeze({
  buyer: freeze({ roleLabel: '采购人员版', price: true, internalApproval: true,
    editableApproval: true, internalRemark: true }),
  warehouse: freeze({ roleLabel: '仓库版', price: false, internalApproval: false,
    editableApproval: false, internalRemark: false }),
  supplier: freeze({ roleLabel: '供应商版', price: true, internalApproval: false,
    editableApproval: false, internalRemark: false }),
  management: freeze({ roleLabel: '管理版', price: true, internalApproval: true,
    editableApproval: true, internalRemark: true }),
})

function baseFields(viewModel, permission) {
  const base = viewModel.baseInfo || {}
  const canonicalNumber = getPurchaseOrderNumber({ objectNo: viewModel.identity?.objectNo })
  return [
    { key: 'objectNo', label: '采购订单编号', value: canonicalNumber || '-' },
    { key: 'supplierName', label: '供应商', value: base.supplierName || '-' },
    { key: 'orderDate', label: '采购日期', value: base.orderDate || '-' },
    { key: 'statusLabel', label: '当前状态', value: base.statusLabel || '待确认' },
    { key: 'totalQuantity', label: '采购数量', value: base.totalQuantity ?? 0 },
    ...(permission.price ? [{ key: 'totalAmount', label: '订单金额',
      value: `${Number(base.totalAmount || 0).toFixed(2)} ${base.currency || 'CNY'}` }] : []),
    { key: 'plannedDeliveryDate', label: '计划到货日期', value: base.plannedDeliveryDate || '待确认' },
    { key: 'urgency', label: '紧急程度', value: viewModel.urgency?.label || '未知/待确认' },
    ...(permission.internalRemark ? [{ key: 'buyerName', label: '采购员', value: base.buyerName || '-' }] : []),
  ]
}

function detailColumns(viewModel, permission) {
  const allowed = new Set(['lineNo', 'materialCode', 'materialName', 'specification', 'unit',
    'quantity', 'plannedDeliveryDate', 'receiptStatusLabel'])
  if (permission.price) ['unitPrice', 'amount'].forEach(key => allowed.add(key))
  return (viewModel.materialDetail?.columns || []).filter(column => allowed.has(column.key))
}

function approvalSlots(viewModel, permission) {
  const maker = viewModel.documentMaker || {}
  const internal = permission.internalApproval ? [
    { code: 'approval', label: '审批', person: '', date: '', editable: permission.editableApproval },
    { code: 'review', label: '审核', person: '', date: '', editable: permission.editableApproval },
    { code: 'recheck', label: '复核', person: '', date: '', editable: permission.editableApproval },
  ] : []
  return [...internal, {
    code: 'maker', label: '制表', person: text(maker.createdBy), date: text(maker.createdAt),
    editable: permission.editableApproval,
  }]
}

export function buildPurchaseOrderPrintViewModelV11428427243({
  purchaseOrderViewModel = {}, companyName = '',
} = {}) {
  const role = PURCHASE_ORDER_PRINT_PERMISSION_V11428427243[purchaseOrderViewModel.role]
    ? purchaseOrderViewModel.role : 'buyer'
  const permission = PURCHASE_ORDER_PRINT_PERMISSION_V11428427243[role]
  const sourceRows = Array.isArray(purchaseOrderViewModel.materialDetail?.rows)
    ? purchaseOrderViewModel.materialDetail.rows : []
  const canonicalNumber = getPurchaseOrderNumber({
    objectNo: purchaseOrderViewModel.identity?.objectNo,
  })
  const columns = detailColumns(purchaseOrderViewModel, permission)
  const detailRows = sourceRows.map(row => Object.fromEntries(
    columns.map(column => [column.key, row[column.key]])))
  const remarks = permission.internalRemark && text(purchaseOrderViewModel.baseInfo?.remark)
    && purchaseOrderViewModel.baseInfo.remark !== '-'
    ? [{ key: 'remark', label: '备注', value: purchaseOrderViewModel.baseInfo.remark }] : []
  const supplierInfo = purchaseOrderViewModel.supplierInfo || {}
  const supplierFields = freeze([
    freeze({ key: 'supplierName', label: '供应商名称', value: text(supplierInfo.supplierName) || '-' }),
    freeze({ key: 'supplierContact', label: '联系人', value: text(supplierInfo.contactName) || '-' }),
    freeze({ key: 'supplierPhone', label: '联系电话', value: text(supplierInfo.contactPhone) || '-' }),
    freeze({ key: 'supplierAddress', label: '供应商地址', value: text(supplierInfo.registeredAddress) || '-' }),
    freeze({ key: 'supplierDeliveryAddress', label: '送货地址', value: text(supplierInfo.deliveryAddress) || '-' }),
  ])

  const model = buildBusinessPrintViewModelV11428427243({
    companyInfo: { companyName },
    documentInfo: {
      documentName: '采购订单',
      documentNo: canonicalNumber,
      documentNoField: 'objectNo',
    },
    basicInfo: { layout: 'six', fields: baseFields(purchaseOrderViewModel, permission),
      longText: remarks },
    detailRows,
    approvalInfo: { visible: true, editable: permission.editableApproval,
      slots: approvalSlots(purchaseOrderViewModel, permission) },
    printMeta: {
      printModel: 'PurchaseOrderPrintViewModel',
      permissionRule: PURCHASE_ORDER_PRINT_PERMISSION_RULE_V11428427243,
      role,
      roleLabel: permission.roleLabel,
      detailTitle: '采购物料明细',
      detailColumns: columns.map(column => ({ key: column.key, label: column.label })),
      purchaseOrderItemSource: purchaseOrderViewModel.materialDetail?.source || 'PurchaseOrderItem[]',
      purchaseOrderItemCount: purchaseOrderViewModel.materialDetail?.purchaseOrderItemCount
        ?? sourceRows.length,
      printDetailCount: detailRows.length,
      countConsistent: purchaseOrderViewModel.materialDetail?.countConsistent === true
        && detailRows.length === sourceRows.length,
      numberSourceValid: purchaseOrderViewModel.identity?.objectNoField === 'objectNo',
      prohibitedDetailSourcesUsed: false,
    },
  })
  return freeze({
    ...model,
    supplierInfo: freeze({
      fields: supplierFields,
      factSource: text(supplierInfo.factSource) || 'SupplierMaster',
    }),
    printPermission: permission,
  })
}
