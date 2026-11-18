import {
  PURCHASE_ORDER_HEADER_SCHEMA_FIELDS,
  PURCHASE_ORDER_ITEM_SCHEMA_FIELDS,
  PURCHASE_ORDER_SYSTEM_GENERATED_FIELDS,
} from '../schema/purchase/purchaseOrder.js'

export const PURCHASE_ORDER_IMPORT_TEMPLATE_CONTRACT_VERSION =
  'V1.14.2.8.4.27.2.16'
export const PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE =
  'IMPORT-TEMPLATE-STRICT-MATCH-001'
export const PURCHASE_ORDER_IMPORT_RELATION_RULE =
  'IMPORT-RELATION-002'

const freezeFields = fields => Object.freeze(fields
  .filter(field => field.importable !== false)
  .map(field => Object.freeze({ ...field })))

const canonicalNumberSchemaField = PURCHASE_ORDER_HEADER_SCHEMA_FIELDS
  .find(field => field.key === 'objectNo')
if (!canonicalNumberSchemaField) throw new Error('PurchaseOrder Schema缺少objectNo。')
const relationField = Object.freeze({ ...canonicalNumberSchemaField,
  generated: false, importable: true, required: true, relationKey: true,
  description: '导入批次Header与Detail关联键；正式objectNo仍由Domain校验与生成',
})

// Schema -> Contract -> Excel。Contract不维护第二份业务字段清单。
export const PURCHASE_ORDER_IMPORT_TEMPLATE_CONTRACT = Object.freeze({
  contractCode: 'PURCHASE_ORDER_IMPORT_TEMPLATE_CONTRACT',
  version: PURCHASE_ORDER_IMPORT_TEMPLATE_CONTRACT_VERSION,
  templateFileName: '采购订单导入模板.xlsx',
  basic: Object.freeze({
    sheetName: '采购订单基本信息',
    layout: 'tabular',
    columns: Object.freeze(['序号']),
    fields: Object.freeze([relationField, ...freezeFields(PURCHASE_ORDER_HEADER_SCHEMA_FIELDS)]),
    schemaSource: 'PurchaseOrder Schema',
  }),
  detail: Object.freeze({
    sheetName: '采购订单物料明细',
    layout: 'tabular',
    columns: Object.freeze(['序号']),
    fields: Object.freeze([relationField, ...freezeFields(PURCHASE_ORDER_ITEM_SCHEMA_FIELDS)]),
    schemaSource: 'PurchaseOrderItem Schema',
  }),
  instruction: Object.freeze({
    sheetName: '字段说明',
    columns: Object.freeze([
      '序号', 'Sheet名称', '显示名称', '系统字段名', '是否必填', '数据类型', '说明',
    ]),
  }),
  relation: Object.freeze({ field: relationField, headerField: 'objectNo', detailField: 'objectNo' }),
  excludedSystemFields: Object.freeze(PURCHASE_ORDER_SYSTEM_GENERATED_FIELDS
    .filter(field => field.key !== relationField.key)
    .map(field => Object.freeze({ ...field }))),
  validationFlow: Object.freeze(['校验', '预览', '确认']),
  strictMatchRule: PURCHASE_ORDER_IMPORT_TEMPLATE_STRICT_MATCH_RULE,
  relationRule: PURCHASE_ORDER_IMPORT_RELATION_RULE,
})

export function getPurchaseOrderImportTemplateContract() {
  return PURCHASE_ORDER_IMPORT_TEMPLATE_CONTRACT
}
