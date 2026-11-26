import {
  PURCHASE_ORDER_BUSINESS_VIEW_VERSION_V1142842724,
  PURCHASE_ORDER_VIEW_ROLES_V1142842724,
} from './purchaseOrderViewModelV1142842724.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_EXPORT_TEMPLATE_VERSION_V1142842724 =
  PURCHASE_ORDER_BUSINESS_VIEW_VERSION_V1142842724

function escapeCsv(value) {
  const text = String(value ?? '')
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]))
}

export function buildPurchaseOrderExportTemplateV1142842724(viewModel = {}) {
  const role = viewModel.role || 'buyer'
  const columns = Array.isArray(viewModel.materialDetail?.columns)
    ? viewModel.materialDetail.columns : []
  const rows = Array.isArray(viewModel.materialDetail?.rows)
    ? viewModel.materialDetail.rows : []
  return Object.freeze({
    templateCode: `PURCHASE_ORDER_EXPORT_${String(role).toUpperCase()}`,
    templateLabel: PURCHASE_ORDER_VIEW_ROLES_V1142842724[role]?.exportLabel || '采购人员版',
    role,
    columns: Object.freeze(columns.map(column => Object.freeze({
      key: column.key, label: column.label,
    }))),
    rows: Object.freeze(rows.map(row => Object.freeze(
      Object.fromEntries(columns.map(column => [column.key, row[column.key]]))))),
    includesTechnicalFields: false,
    inheritsViewPermission: true,
    businessWriteCount: 0,
  })
}

export function purchaseOrderExportCsvV1142842724(template = {}) {
  const columns = Array.isArray(template.columns) ? template.columns : []
  const rows = Array.isArray(template.rows) ? template.rows : []
  return `\uFEFF${[
    columns.map(column => escapeCsv(column.label)).join(','),
    ...rows.map(row => columns.map(column => escapeCsv(row[column.key])).join(',')),
  ].join('\r\n')}`
}

export function buildPurchaseOrderPrintDocumentV11428427241(viewModel = {}) {
  const template = buildPurchaseOrderExportTemplateV1142842724(viewModel)
  const identity = viewModel.identity || {}
  const canonicalNumber = getPurchaseOrderNumber({ objectNo: identity.objectNo })
  const base = viewModel.baseInfo || {}
  const urgency = viewModel.urgency || {}
  const header = template.columns.map(column => `<th>${escapeHtml(column.label)}</th>`).join('')
  const rows = template.rows.map(row => `<tr>${template.columns
    .map(column => `<td>${escapeHtml(row[column.key])}</td>`).join('')}</tr>`).join('')
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(canonicalNumber)} 采购订单</title><style>body{font-family:Arial,"Microsoft YaHei",sans-serif;color:#111;padding:24px}h1{margin:0 0 16px}.meta{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:18px}.meta div{border:1px solid #bbb;padding:8px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #999;padding:7px;text-align:left}th{background:#f3f4f6}.boundary{margin-top:14px;color:#555}@media print{body{padding:0}}</style></head><body><h1>采购订单</h1><section class="meta"><div>采购订单编号：${escapeHtml(canonicalNumber)}</div><div>当前状态：${escapeHtml(base.statusLabel)}</div><div>供应商：${escapeHtml(base.supplierName)}</div><div>计划到货日期：${escapeHtml(base.plannedDeliveryDate)}</div><div>紧急程度：${escapeHtml(urgency.label)}</div></section><h2>采购物料明细</h2><table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table><p class="boundary">打印内容继承${escapeHtml(viewModel.roleLabel)}字段权限；技术字段和无权字段未输出。</p></body></html>`
}
