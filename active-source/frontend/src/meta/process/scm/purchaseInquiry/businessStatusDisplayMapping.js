export const BUSINESS_STATUS_DISPLAY_MAPPING_VERSION = 'V1.14.2.8.18.8.1'

const STATUS_LABELS = Object.freeze({ active: '有效', enabled: '启用', disabled: '停用' })
const CATEGORY_LABELS = Object.freeze({ unclassified: '未分类' })
const SOURCE_LABELS = Object.freeze({
  purchase_request_suggestion: '采购申请建议供应商',
  supplier_master: '供应商主数据',
  'Supplier Master': '供应商主数据',
})

const resolveLabel = (mapping, value, fallback = '未提供') => mapping[value] || value || fallback

export const resolveSupplierStatusLabel = value => resolveLabel(STATUS_LABELS, value)
export const resolveSupplierCategoryLabel = value => resolveLabel(CATEGORY_LABELS, value)
export const resolveSupplierSourceLabel = value => resolveLabel(SOURCE_LABELS, value)

export function createSupplierBusinessDisplay(candidate = {}) {
  return Object.freeze({
    supplierStatusLabel: resolveSupplierStatusLabel(candidate.supplierStatus),
    supplierCategoryLabel: resolveSupplierCategoryLabel(candidate.supplierCategory),
    sourceLabel: resolveSupplierSourceLabel(candidate.source),
  })
}

