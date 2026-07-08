import { getFoundationState, previewNextCode } from './manufacturingFoundationStore.js'
import { exportRowsToCsv } from './foundationTableUtils.js'

const CODE_FIELDS = {
  employee: 'employeeNo',
  material: 'code',
  customer: 'code',
  supplier: 'code',
  workCenter: 'code',
  warehouse: 'code',
  process: 'processCode',
  routing: 'routingCode',
  equipment: 'equipmentCode',
  productCategory: 'categoryCode',
  supplierMaterialPrice: 'supplierMaterialCode',
  materialSupplierRelation: 'relationCode',
}

const COLLECTIONS = {
  employee: 'employees',
  material: 'materials',
  customer: 'customers',
  supplier: 'suppliers',
  workCenter: 'workCenters',
  warehouse: 'warehouses',
  process: 'processes',
  routing: 'routings',
  equipment: 'equipment',
  productCategory: 'productCategories',
  supplierMaterialPrice: 'supplierMaterialPrices',
  materialSupplierRelation: 'materialSupplierRelations',
}

function normalize(value) {
  return String(value ?? '').trim()
}

function boolValue(value) {
  const text = normalize(value).toLowerCase()
  if (['true', '1', 'yes', 'y', '是', '启用'].includes(text)) return true
  if (['false', '0', 'no', 'n', '否', '停用'].includes(text)) return false
  return value
}

function csvEscape(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function parseCsvLine(line) {
  const result = []
  let current = ''
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const next = line[index + 1]
    if (char === '"' && quoted && next === '"') {
      current += '"'
      index += 1
    } else if (char === '"') {
      quoted = !quoted
    } else if (char === ',' && !quoted) {
      result.push(current)
      current = ''
    } else {
      current += char
    }
  }
  result.push(current)
  return result
}

function getRowValue(row, column) {
  return normalize(
    row[column.key]
    ?? row[column.rawLabel]
    ?? row[column.label]
    ?? row[`${column.rawLabel || column.label}${column.required ? '*' : ''}`]
  )
}

function matchReference(list = [], value, codeKeys = ['code'], nameKeys = ['name']) {
  const text = normalize(value)
  if (!text) return null
  return list.find((item) => (
    codeKeys.some((key) => normalize(item[key]) === text)
    || nameKeys.some((key) => normalize(item[key]) === text)
  )) || null
}

function validStatus(entityType, value) {
  const text = normalize(value)
  if (!text) return true
  if (entityType === 'employee') return ['active', 'resigned', 'leave', 'borrowed'].includes(text)
  return ['enabled', 'disabled'].includes(text)
}

function codeExists(entityType, code) {
  const collection = COLLECTIONS[entityType]
  const codeField = CODE_FIELDS[entityType]
  if (!collection || !codeField || !code) return false
  return (getFoundationState()[collection] || []).some((item) => normalize(item[codeField]) === normalize(code))
}

function resolveReferences(entityType, row) {
  const state = getFoundationState()
  const matched = {}
  if (entityType === 'material') {
    const warehouseValue = row.defaultWarehouseId || row['默认仓库']
    const locationValue = row.defaultLocationId || row['默认库位']
    if (warehouseValue) matched.defaultWarehouse = matchReference(state.warehouses, warehouseValue, ['code'], ['name'])
    if (locationValue) matched.defaultLocation = matchReference((state.warehouses || []).flatMap((warehouse) => warehouse.locations || []), locationValue, ['code'], ['name'])
  }
  if (entityType === 'supplierMaterialPrice' || entityType === 'materialSupplierRelation') {
    matched.supplier = matchReference(state.suppliers, row.supplierId || row['供应商'], ['code'], ['name'])
    matched.material = matchReference(state.materials, row.materialId || row['物料'], ['code'], ['name'])
  }
  if (entityType === 'process' || entityType === 'equipment') {
    matched.workCenter = matchReference(state.workCenters, row.workCenterId || row['工作中心'] || row['默认工作中心'] || row['所属工作中心'], ['code'], ['name'])
  }
  if (entityType === 'routing') {
    matched.material = matchReference(state.materials, row.materialId || row['适用物料'], ['code'], ['name'])
    matched.productCategory = matchReference(state.productCategories, row.productCategory || row['产品类别'], ['categoryCode'], ['categoryName'])
  }
  return matched
}

export function getImportTemplateColumns(entityType, columns = []) {
  return columns
    .filter((column) => column.key !== 'locationCount' && !column.readonly)
    .map((column) => ({
      key: column.key,
      label: column.required ? `${column.label}*` : column.label,
      rawLabel: column.label,
      required: Boolean(column.required),
      type: column.type || 'text',
    }))
    .concat([{ key: 'remark', label: '备注', rawLabel: '备注', required: false, type: 'text' }])
}

export function downloadImportTemplate(entityType, columns = [], entityName = '基础资料') {
  const templateColumns = getImportTemplateColumns(entityType, columns)
  const example = {}
  templateColumns.forEach((column) => {
    if (column.key === CODE_FIELDS[entityType]) example[column.key] = ''
    else if (column.type === 'number') example[column.key] = 1
    else if (column.type === 'date') example[column.key] = '2026-07-01'
    else if (column.type === 'checkbox') example[column.key] = '是'
    else if (column.key === 'status') example[column.key] = entityType === 'employee' ? 'active' : 'enabled'
    else if (column.key === 'industryType') example[column.key] = 'general'
    else example[column.key] = `示例${column.rawLabel}`
  })
  exportRowsToCsv([example], templateColumns.map((column) => ({ key: column.key, label: column.label })), `${entityName}-导入模板.csv`)
}

export function parseCsvText(csvText) {
  const lines = String(csvText || '').replace(/^\uFEFF/, '').split(/\r?\n/).filter((line) => line.trim())
  if (!lines.length) return []
  const headers = parseCsvLine(lines[0]).map((header) => header.replace(/\*$/, '').trim())
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line)
    return headers.reduce((row, header, index) => ({ ...row, [header]: values[index] ?? '' }), {})
  })
}

export function validateImportRows(entityType, rows = [], columns = []) {
  const errors = []
  const warnings = []
  const codeField = CODE_FIELDS[entityType]
  const templateColumns = getImportTemplateColumns(entityType, columns)
  const seenCodes = new Set()
  rows.forEach((row, rowIndex) => {
    const rowNo = rowIndex + 1
    templateColumns.forEach((column) => {
      const value = getRowValue(row, column)
      if (column.required && !value) errors.push({ rowNo, field: column.rawLabel, message: `${column.rawLabel}不能为空` })
      if (column.type === 'number' && value !== '' && Number.isNaN(Number(value))) errors.push({ rowNo, field: column.rawLabel, message: `${column.rawLabel}必须是数字` })
      if (column.type === 'number' && value !== '' && Number(value) < 0) errors.push({ rowNo, field: column.rawLabel, message: `${column.rawLabel}不能小于0` })
      if (column.type === 'date' && value && Number.isNaN(new Date(value).getTime())) errors.push({ rowNo, field: column.rawLabel, message: `${column.rawLabel}日期格式不合法` })
    })
    const codeColumn = templateColumns.find((column) => column.key === codeField)
    const codeValue = codeColumn ? getRowValue(row, codeColumn) : normalize(row[codeField])
    if (codeValue) {
      if (seenCodes.has(codeValue)) errors.push({ rowNo, field: codeField, message: '导入文件内编码重复' })
      if (codeExists(entityType, codeValue)) errors.push({ rowNo, field: codeField, message: '编码与已有数据冲突' })
      seenCodes.add(codeValue)
    } else if (codeField) {
      warnings.push({ rowNo, field: codeField, message: `编码为空，将自动生成：${previewNextCode(entityType)}` })
    }
    const status = normalize(row.status || row['状态'] || row['人员状态'])
    if (!validStatus(entityType, status)) errors.push({ rowNo, field: '状态', message: entityType === 'employee' ? '人员状态必须是 active/resigned/leave/borrowed' : '状态必须是 enabled/disabled' })

    if (entityType === 'employee') {
      const idCardNo = normalize(row.idCardNo || row['身份证号'])
      const hireDate = normalize(row.hireDate || row['入职日期'])
      const leaveDate = normalize(row.leaveDate || row['离职日期'])
      if (idCardNo && ![15, 18].includes(idCardNo.length)) errors.push({ rowNo, field: '身份证号', message: '身份证号必须为15位或18位' })
      if (!hireDate) errors.push({ rowNo, field: '入职日期', message: '入职日期不能为空' })
      if (hireDate && leaveDate && new Date(leaveDate) < new Date(hireDate)) errors.push({ rowNo, field: '离职日期', message: '离职日期不能早于入职日期' })
    }
    if (entityType === 'material') {
      const safetyStock = Number(row.safetyStock || row['安全库存'] || 0)
      const maxStock = Number(row.maxStock || row['最高库存'] || 0)
      if (maxStock < safetyStock) errors.push({ rowNo, field: '最高库存', message: '最高库存必须大于等于安全库存' })
      const mrp = normalize(row.mrpEnabled || row['启用 MRP'])
      if (mrp && !['true', 'false', '是', '否', '1', '0'].includes(mrp.toLowerCase())) errors.push({ rowNo, field: '启用 MRP', message: '启用 MRP 必须是 true/false/是/否' })
    }
    if (entityType === 'supplier') {
      const onTimeRate = Number(row.onTimeRate || row['准时率'] || 0)
      if (onTimeRate < 0 || onTimeRate > 100) errors.push({ rowNo, field: '准时率', message: '准时率必须在0-100之间' })
    }
    if (entityType === 'process') {
      const industryType = normalize(row.industryType || row['行业类型'])
      if (industryType && !['printing', 'wholeHouseWood', 'general'].includes(industryType)) errors.push({ rowNo, field: '行业类型', message: '行业类型必须是 printing/wholeHouseWood/general' })
    }
    const refs = resolveReferences(entityType, row)
    Object.entries(refs).forEach(([key, value]) => {
      if (!value && normalize(row[key])) errors.push({ rowNo, field: key, message: '引用字段无法匹配已有基础资料' })
    })
  })
  return { errors, warnings }
}

export function previewImportRows(entityType, rows = [], columns = []) {
  const validation = validateImportRows(entityType, rows, columns)
  const codeField = CODE_FIELDS[entityType]
  return rows.map((row, index) => {
    const rowNo = index + 1
    const rowErrors = validation.errors.filter((error) => error.rowNo === rowNo)
    const rowWarnings = validation.warnings.filter((warning) => warning.rowNo === rowNo)
    return {
      rowNo,
      status: rowErrors.length ? '错误' : rowWarnings.length ? '警告' : '可导入',
      message: [...rowErrors, ...rowWarnings].map((item) => item.message).join('；'),
      codePreview: normalize(row[codeField]) || previewNextCode(entityType),
      raw: row,
      matched: resolveReferences(entityType, row),
      suggestion: rowErrors.length ? '请修正后重新导入' : '可确认导入',
    }
  })
}

export function confirmImportRows(entityType, rows = []) {
  return rows
}

export function exportImportErrors(errors = [], filename = 'import-errors.csv') {
  exportRowsToCsv(errors, [
    { key: 'rowNo', label: '序号' },
    { key: 'field', label: '字段' },
    { key: 'message', label: '错误说明' },
  ], filename)
}

export function mapImportRowToPayload(entityType, row = {}, columns = []) {
  const payload = {}
  columns.forEach((column) => {
    const value = getRowValue(row, column)
    if (value === '') return
    if (column.type === 'number') payload[column.key] = Number(value)
    else if (column.type === 'checkbox') payload[column.key] = boolValue(value)
    else payload[column.key] = value
  })
  if (!payload.status) payload.status = entityType === 'employee' ? 'active' : 'enabled'
  const matched = resolveReferences(entityType, payload)
  if (matched.defaultWarehouse) payload.defaultWarehouseId = matched.defaultWarehouse.id
  if (matched.defaultLocation) payload.defaultLocationId = matched.defaultLocation.id
  if (matched.supplier) payload.supplierId = matched.supplier.id
  if (matched.material) payload.materialId = matched.material.id
  if (matched.workCenter) payload.workCenterId = matched.workCenter.id
  if (matched.productCategory) payload.productCategory = matched.productCategory.categoryName
  return payload
}
