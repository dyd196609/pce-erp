import {
  getPurchaseOrderImportTemplateContract,
  PURCHASE_ORDER_IMPORT_RELATION_RULE,
  PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE,
} from '../contracts/purchaseOrderImportTemplateContract.js'

export const PURCHASE_ORDER_IMPORT_TEMPLATE_VERSION_V11428427212 =
  'V1.14.2.8.4.27.2.16'
export const PURCHASE_ORDER_IMPORT_TEMPLATE_RULE_V11428427212 =
  'PURCHASE-ORDER-IMPORT-TEMPLATE-002'
export const PURCHASE_ORDER_IMPORT_TEMPLATE_SCHEMA_BIND_RULE_V11428427213 =
  'IMPORT-TEMPLATE-SCHEMA-BIND-002'
export const PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE_V11428427214 =
  PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE
export const PURCHASE_ORDER_IMPORT_RELATION_RULE_V11428427215 =
  PURCHASE_ORDER_IMPORT_RELATION_RULE

const encoder = new TextEncoder()
const xml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
}[character]))

function columnName(index) {
  let value = index + 1
  let result = ''
  while (value > 0) {
    value -= 1
    result = String.fromCharCode(65 + (value % 26)) + result
    value = Math.floor(value / 26)
  }
  return result
}

function worksheetXml(rows) {
  const body = rows.map((row, rowIndex) => {
    const cells = row.map((value, columnIndex) => {
      const reference = `${columnName(columnIndex)}${rowIndex + 1}`
      if (typeof value === 'number') return `<c r="${reference}"><v>${value}</v></c>`
      return `<c r="${reference}" t="inlineStr"><is><t xml:space="preserve">${xml(value)}</t></is></c>`
    }).join('')
    return `<row r="${rowIndex + 1}">${cells}</row>`
  }).join('')
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`
}

const crcTable = (() => {
  const table = new Uint32Array(256)
  for (let index = 0; index < 256; index += 1) {
    let value = index
    for (let bit = 0; bit < 8; bit += 1) value = (value & 1)
      ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1)
    table[index] = value >>> 0
  }
  return table
})()

function crc32(bytes) {
  let value = 0xffffffff
  for (const byte of bytes) value = crcTable[(value ^ byte) & 0xff] ^ (value >>> 8)
  return (value ^ 0xffffffff) >>> 0
}

const uint16 = value => Uint8Array.of(value & 0xff, (value >>> 8) & 0xff)
const uint32 = value => Uint8Array.of(value & 0xff, (value >>> 8) & 0xff,
  (value >>> 16) & 0xff, (value >>> 24) & 0xff)

function concat(parts) {
  const result = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0))
  let offset = 0
  for (const part of parts) { result.set(part, offset); offset += part.length }
  return result
}

function zipStore(entries) {
  const localParts = []
  const centralParts = []
  let offset = 0
  for (const entry of entries) {
    const name = encoder.encode(entry.name)
    const data = encoder.encode(entry.content)
    const checksum = crc32(data)
    const local = concat([
      uint32(0x04034b50), uint16(20), uint16(0x0800), uint16(0), uint16(0), uint16(0),
      uint32(checksum), uint32(data.length), uint32(data.length), uint16(name.length), uint16(0),
      name, data,
    ])
    localParts.push(local)
    centralParts.push(concat([
      uint32(0x02014b50), uint16(20), uint16(20), uint16(0x0800), uint16(0),
      uint16(0), uint16(0), uint32(checksum), uint32(data.length), uint32(data.length),
      uint16(name.length), uint16(0), uint16(0), uint16(0), uint16(0), uint32(0),
      uint32(offset), name,
    ]))
    offset += local.length
  }
  const central = concat(centralParts)
  return concat([...localParts, central, uint32(0x06054b50), uint16(0), uint16(0),
    uint16(entries.length), uint16(entries.length), uint32(central.length), uint32(offset), uint16(0)])
}

export function getPurchaseOrderImportTemplateDefinitionV11428427212() {
  const contract = getPurchaseOrderImportTemplateContract()
  return Object.freeze({
    templateFileName: contract.templateFileName,
    basicSheetName: contract.basic.sheetName,
    itemSheetName: contract.detail.sheetName,
    instructionSheetName: contract.instruction.sheetName,
    headerFields: contract.basic.fields,
    itemFields: contract.detail.fields,
    fields: Object.freeze([...contract.basic.fields, ...contract.detail.fields]),
    excludedSystemFields: contract.excludedSystemFields,
    validationFlow: contract.validationFlow,
    schemaSource: Object.freeze({ basic: contract.basic.schemaSource,
      item: contract.detail.schemaSource }),
    contract,
  })
}

export function buildPurchaseOrderImportSheetRowsV11428427214() {
  const contract = getPurchaseOrderImportTemplateContract()
  const basicRows = [
    [...contract.basic.columns, ...contract.basic.fields.map(field => field.label)],
    [1, ...contract.basic.fields.map(() => '')],
  ]
  const detailRows = [
    [...contract.detail.columns, ...contract.detail.fields.map(field => field.label)],
    [1, ...contract.detail.fields.map(() => '')],
  ]
  const instructionFields = [
    ...contract.basic.fields.map(field => ({ field, sheetName: contract.basic.sheetName })),
    ...contract.detail.fields.map(field => ({ field, sheetName: contract.detail.sheetName })),
  ]
  const instructionRows = [
    [...contract.instruction.columns],
    ...instructionFields.map(({ field, sheetName }, index) => [
      index + 1, sheetName, field.label, field.key, field.required ? '是' : '否',
      field.dataType, field.description,
    ]),
  ]
  return Object.freeze({
    basicRows: Object.freeze(basicRows.map(row => Object.freeze(row))),
    detailRows: Object.freeze(detailRows.map(row => Object.freeze(row))),
    instructionRows: Object.freeze(instructionRows.map(row => Object.freeze(row))),
  })
}

export function buildPurchaseOrderImportWorkbookV11428427212() {
  const definition = getPurchaseOrderImportTemplateDefinitionV11428427212()
  const { basicRows, detailRows, instructionRows } =
    buildPurchaseOrderImportSheetRowsV11428427214()
  const contentTypes = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
  const workbookXml = `<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${xml(definition.basicSheetName)}" sheetId="1" r:id="rId1"/><sheet name="${xml(definition.itemSheetName)}" sheetId="2" r:id="rId2"/></sheets></workbook>`
  const workbookRelationships = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>'
  const entries = [
    { name: '[Content_Types].xml', content: contentTypes },
    { name: '_rels/.rels', content: '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>' },
    { name: 'xl/workbook.xml', content: workbookXml },
    { name: 'xl/_rels/workbook.xml.rels', content: workbookRelationships },
    { name: 'xl/worksheets/sheet1.xml', content: worksheetXml(basicRows) },
    { name: 'xl/worksheets/sheet2.xml', content: worksheetXml(detailRows) },
  ]
  return Object.freeze({ bytes: zipStore(entries), entries: Object.freeze(entries), definition,
    fileName: definition.templateFileName,
    headerFieldCount: definition.headerFields.length,
    itemFieldCount: definition.itemFields.length,
    fieldCount: definition.fields.length,
    sheetNames: Object.freeze([definition.basicSheetName, definition.itemSheetName]),
    rule: PURCHASE_ORDER_IMPORT_TEMPLATE_RULE_V11428427212,
    schemaBindRule: PURCHASE_ORDER_IMPORT_TEMPLATE_SCHEMA_BIND_RULE_V11428427213,
    strictMatchRule: PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE_V11428427214,
    relationRule: PURCHASE_ORDER_IMPORT_RELATION_RULE_V11428427215,
    businessWriteCount: 0 })
}

export function verifyPurchaseOrderImportRelationV11428427215() {
  const definition = getPurchaseOrderImportTemplateDefinitionV11428427212()
  const { basicRows, detailRows } = buildPurchaseOrderImportSheetRowsV11428427214()
  const relationLabel = definition.contract.relation.field.label
  const headerRelationRows = basicRows[0].filter(label => label === relationLabel)
  const detailRelationColumns = detailRows[0].filter(label => label === relationLabel)
  const passed = definition.basicSheetName === '采购订单基本信息'
    && definition.itemSheetName === '采购订单物料明细'
    && headerRelationRows.length === 1 && detailRelationColumns.length === 1
    && definition.contract.relation.headerField === definition.contract.relation.detailField
  return Object.freeze({ passed, relationLabel,
    relationField: definition.contract.relation.headerField,
    headerRelationCount: headerRelationRows.length,
    detailRelationCount: detailRelationColumns.length,
    sheetCount: 2,
    sheetNames: Object.freeze([definition.basicSheetName, definition.itemSheetName]),
    rule: PURCHASE_ORDER_IMPORT_RELATION_RULE_V11428427215,
    businessWriteCount: 0 })
}

export function verifyPurchaseOrderImportTemplateStrictMatchV11428427214() {
  const contract = getPurchaseOrderImportTemplateContract()
  const { basicRows, detailRows, instructionRows } =
    buildPurchaseOrderImportSheetRowsV11428427214()
  const expectedBasic = contract.basic.fields.map(field => field.label)
  const actualBasic = basicRows[0].slice(1)
  const expectedDetail = contract.detail.fields.map(field => field.label)
  const actualDetail = detailRows[0].slice(1)
  const expectedInstruction = contract.instruction.columns
  const actualInstruction = instructionRows[0]
  const countMatch = expectedBasic.length === actualBasic.length
    && expectedDetail.length === actualDetail.length
  const nameMatch = [...expectedBasic].sort().join('\u0000') === [...actualBasic].sort().join('\u0000')
    && [...expectedDetail].sort().join('\u0000') === [...actualDetail].sort().join('\u0000')
  const orderMatch = JSON.stringify(expectedBasic) === JSON.stringify(actualBasic)
    && JSON.stringify(expectedDetail) === JSON.stringify(actualDetail)
  const structureMatch = basicRows[0][0] === '序号'
    && detailRows[0][0] === '序号'
    && JSON.stringify(actualInstruction) === JSON.stringify(expectedInstruction)
  return Object.freeze({
    passed: countMatch && nameMatch && orderMatch && structureMatch,
    countMatch, nameMatch, orderMatch, structureMatch,
    expectedBasic: Object.freeze(expectedBasic), actualBasic: Object.freeze(actualBasic),
    expectedDetail: Object.freeze(expectedDetail), actualDetail: Object.freeze(actualDetail),
    rule: PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE_V11428427214,
    businessWriteCount: 0,
  })
}

export function validatePurchaseOrderImportRelationRowsV11428427216({
  headerRows = [], detailRows = [],
} = {}) {
  const contract = getPurchaseOrderImportTemplateContract()
  const relationLabel = contract.relation.field.label
  const headerLabels = Array.isArray(headerRows[0]) ? headerRows[0] : []
  const detailLabels = Array.isArray(detailRows[0]) ? detailRows[0] : []
  const headerIndex = headerLabels.indexOf(relationLabel)
  const detailIndex = detailLabels.indexOf(relationLabel)
  const normalize = value => String(value ?? '').trim()
  const headerKeys = new Set((Array.isArray(headerRows) ? headerRows.slice(1) : [])
    .map(row => normalize(row?.[headerIndex])).filter(Boolean))
  const detailKeys = (Array.isArray(detailRows) ? detailRows.slice(1) : [])
    .map(row => normalize(row?.[detailIndex]))
  const emptyDetailRows = detailKeys.reduce((rows, key, index) => (
    key ? rows : [...rows, index + 2]), [])
  const orphanDetailKeys = [...new Set(detailKeys.filter(key => key && !headerKeys.has(key)))]
  return Object.freeze({
    passed: headerIndex > 0 && detailIndex > 0 && headerKeys.size > 0
      && emptyDetailRows.length === 0 && orphanDetailKeys.length === 0,
    relationLabel,
    headerKeyCount: headerKeys.size,
    detailKeyCount: detailKeys.length,
    emptyDetailRows: Object.freeze(emptyDetailRows),
    orphanDetailKeys: Object.freeze(orphanDetailKeys),
    rule: PURCHASE_ORDER_IMPORT_RELATION_RULE_V11428427215,
    businessWriteCount: 0,
  })
}

export function verifyPurchaseOrderImportTemplateSchemaBindingV11428427213() {
  const definition = getPurchaseOrderImportTemplateDefinitionV11428427212()
  const strictResult = verifyPurchaseOrderImportTemplateStrictMatchV11428427214()
  const headerSchemaFields = definition.contract.basic.fields.map(field => field.label)
  const templateHeaderFields = definition.headerFields.map(field => field.label)
  const detailSchemaFields = definition.contract.detail.fields.map(field => field.label)
  const templateDetailFields = definition.itemFields.map(field => field.label)
  const difference = (expected, actual) => expected.filter(field => !actual.includes(field))
  const result = {
    headerSchemaFields: Object.freeze(headerSchemaFields),
    templateHeaderFields: Object.freeze(templateHeaderFields),
    headerMissing: Object.freeze(difference(headerSchemaFields, templateHeaderFields)),
    headerUnexpected: Object.freeze(difference(templateHeaderFields, headerSchemaFields)),
    detailSchemaFields: Object.freeze(detailSchemaFields),
    templateDetailFields: Object.freeze(templateDetailFields),
    detailMissing: Object.freeze(difference(detailSchemaFields, templateDetailFields)),
    detailUnexpected: Object.freeze(difference(templateDetailFields, detailSchemaFields)),
  }
  return Object.freeze({ ...result,
    passed: strictResult.passed && !result.headerMissing.length && !result.headerUnexpected.length
      && !result.detailMissing.length && !result.detailUnexpected.length,
    rule: PURCHASE_ORDER_IMPORT_TEMPLATE_SCHEMA_BIND_RULE_V11428427213,
    businessWriteCount: 0 })
}

export function downloadPurchaseOrderImportTemplateV11428427212(documentRef = document) {
  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  const blob = new Blob([workbook.bytes], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const anchor = documentRef.createElement('a')
  anchor.href = url
  anchor.download = workbook.fileName
  documentRef.body.appendChild(anchor)
  anchor.click()
  documentRef.body.removeChild(anchor)
  URL.revokeObjectURL(url)
  return Object.freeze({ fileName: workbook.fileName,
    headerFieldCount: workbook.headerFieldCount, itemFieldCount: workbook.itemFieldCount,
    fieldCount: workbook.fieldCount, sheetNames: workbook.sheetNames,
    schemaSource: workbook.definition.schemaSource,
    rule: workbook.rule, strictMatchRule: workbook.strictMatchRule, businessWriteCount: 0 })
}
