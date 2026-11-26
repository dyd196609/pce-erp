import { WorkflowSchema } from '../core/workflowSchema.js'

const freeze = value => Object.freeze(value)

const schemaField = field => freeze({ generated: false, importable: true,
  detailVisible: true, required: false, ...field })

// PurchaseOrder与PurchaseOrderItem的受治理字段定义是详情和导入模板的共同事实源。
export const PURCHASE_ORDER_HEADER_SCHEMA_FIELDS = freeze([
  schemaField({ key: 'objectNo', label: '采购订单编号', dataType: '文本', generated: true,
    importable: false, detailVisible: false, example: 'PO202606040002', description: '系统生成的正式采购订单业务编号' }),
  schemaField({ key: 'supplierName', label: '供应商', dataType: '主数据', required: true,
    example: '示例供应商', description: '供应商主数据名称', valueSources: ['supplierName', 'supplierId'] }),
  schemaField({ key: 'purchaseModeLabel', label: '采购模式', dataType: '枚举', required: true,
    importable: false, example: '标准采购', description: '订单服务端持久化采购模式' }),
  schemaField({ key: 'priceSourceLabel', label: '价格来源', dataType: '来源追踪',
    importable: false, example: '供应商物料有效价格', description: '订单执行价正式来源' }),
  schemaField({ key: 'supplierContact', label: '供应商联系人', dataType: '主数据', generated: true,
    importable: false, description: '来自SupplierMaster；缺失时不伪造' }),
  schemaField({ key: 'supplierPhone', label: '联系电话', dataType: '脱敏文本', generated: true,
    importable: false, description: '来自SupplierMaster并仅在展示时脱敏' }),
  schemaField({ key: 'supplierAddress', label: '供应商地址', dataType: '主数据', generated: true,
    importable: false, description: '来自SupplierMaster；缺失时不伪造' }),
  schemaField({ key: 'buyerName', label: '采购员', dataType: '主数据', required: true,
    example: '采购员甲', description: '采购员主数据名称', valueSources: ['buyerName', 'buyerId'] }),
  schemaField({ key: 'orderDate', label: '采购日期', dataType: '日期', required: true,
    example: '2026-08-09', description: '格式YYYY-MM-DD', valueSources: ['orderDate', 'purchaseDate'] }),
  schemaField({ key: 'plannedDeliveryDate', label: '计划到货日期', dataType: '日期', required: true,
    example: '2026-08-20', description: '格式YYYY-MM-DD',
    valueSources: ['plannedDeliveryDate', 'plannedArrivalDate', 'planDeliveryDate'] }),
  schemaField({ key: 'purchaseOrderType', label: '采购订单类型', dataType: '枚举', required: true,
    example: '标准采购', description: '由采购订单类型字典提供',
    valueSources: ['purchaseOrderTypeLabel', 'purchaseOrderType', 'purchaseType'] }),
  schemaField({ key: 'businessPurpose', label: '业务用途', dataType: '枚举', required: true,
    example: '生产采购', description: '采购订单的业务用途', valueSources: ['businessPurpose', 'purchasePurpose'] }),
  schemaField({ key: 'urgencyLevel', label: '紧急程度', dataType: '枚举',
    example: '一般', description: '仅接受受治理业务标签',
    valueSources: ['deliveryUrgencyLabel', 'deliveryUrgency', 'urgencyLevel'] }),
  schemaField({ key: 'currency', label: '币种', dataType: '文本', required: true,
    example: 'CNY', description: 'ISO币种编码' }),
  schemaField({ key: 'paymentTerms', label: '付款条件', dataType: '文本',
    example: '月结30天', description: '采购订单约定付款条件' }),
  schemaField({ key: 'deliveryAddress', label: '交付地址', dataType: '文本',
    example: '一号仓库', description: '供应商交付地点' }),
  schemaField({ key: 'deliveryRequirements', label: '交付要求', dataType: '文本',
    example: '按批次送货并附质检报告', description: '订单级交付要求',
    valueSources: ['deliveryRequirements', 'deliveryRequirement', 'receiptRequirement'] }),
  schemaField({ key: 'remark', label: '备注', dataType: '文本',
    example: '按订单要求交付', description: '采购订单头备注' }),
  schemaField({ key: 'status', label: '状态', dataType: '枚举', generated: true,
    importable: false, detailVisible: false, example: 'draft', description: '系统生命周期状态' }),
  schemaField({ key: 'createdAt', label: '创建时间', dataType: '日期时间', generated: true,
    importable: false, detailVisible: false, example: '2026-08-09 10:00:00', description: '系统创建时间' }),
])

export const PURCHASE_ORDER_SUPPLIER_SCHEMA_FIELDS = freeze([
  freeze({ key: 'supplierName', label: '供应商名称',
    businessField: 'SupplierMaster.name', runtimeField: 'PurchaseOrderRuntimeModel.supplierName' }),
  freeze({ key: 'supplierContact', label: '联系人',
    businessField: 'SupplierMaster.contact_person', runtimeField: 'PurchaseOrderRuntimeModel.supplierContact' }),
  freeze({ key: 'supplierPhone', label: '联系电话',
    businessField: 'SupplierMaster.contact_phone', runtimeField: 'PurchaseOrderRuntimeModel.supplierPhone' }),
  freeze({ key: 'supplierAddress', label: '供应商地址',
    businessField: 'SupplierMaster.address', runtimeField: 'PurchaseOrderRuntimeModel.supplierAddress' }),
  freeze({ key: 'supplierDeliveryAddress', label: '送货地址',
    businessField: 'SupplierMaster.delivery_address', runtimeField: 'PurchaseOrderRuntimeModel.supplierDeliveryAddress' }),
])

export const PURCHASE_ORDER_ITEM_SCHEMA_FIELDS = freeze([
  schemaField({ key: 'purchaseRequestItemId', label: '来源采购申请明细', dataType: '关系',
    generated: true, importable: false, detailVisible: false,
    description: '服务端解析的PurchaseRequestItem唯一标识' }),
  schemaField({ key: 'sourcePurchaseRequestNo', label: '来源采购申请', dataType: '关系',
    generated: true, importable: false, detailVisible: false,
    description: 'PurchaseRequestItem所属采购申请业务编号' }),
  schemaField({ key: 'materialMasterId', label: '物料主数据', dataType: '主数据',
    generated: true, importable: false, detailVisible: false,
    description: '企业基础数据MaterialMaster唯一标识' }),
  schemaField({ key: 'supplierName', label: '供应商', dataType: '主数据', generated: true,
    importable: false, description: '由PurchaseOrder关联的SupplierMaster提供' }),
  schemaField({ key: 'materialCode', label: '物料编码', dataType: '文本', required: true,
    example: 'MAT-001', description: '物料主数据编码' }),
  schemaField({ key: 'materialName', label: '物料名称', dataType: '文本',
    example: '轴承', description: '物料主数据名称' }),
  schemaField({ key: 'specification', label: '规格', dataType: '文本',
    example: '6204-2RS', description: '物料规格型号', valueSources: ['specification', 'spec'] }),
  schemaField({ key: 'unit', label: '单位', dataType: '文本', required: true,
    example: '件', description: '采购计量单位' }),
  schemaField({ key: 'quantity', label: '数量', dataType: '数字', required: true,
    example: 100, description: '必须大于0' }),
  schemaField({ key: 'unitPrice', label: '采购执行单价', dataType: '数字', required: true,
    example: 12.5, description: '不得小于0', valueSources: ['confirmedPrice', 'planPrice', 'price', 'unitPrice'] }),
  schemaField({ key: 'amount', label: '金额', dataType: '数字', required: true,
    example: 1250, description: '数量乘采购执行单价', valueSources: ['amount', 'planAmount'] }),
  schemaField({ key: 'priceSourceLabel', label: '价格来源', dataType: '来源追踪', generated: true,
    importable: false, description: '服务端验证的SupplierMaterialPrice正式价格来源' }),
  schemaField({ key: 'supplierMaterialPriceNo', label: '有效价格编号', dataType: '关系', generated: true,
    importable: false, description: 'PurchaseOrderItem引用的SupplierMaterialPrice编号' }),
  schemaField({ key: 'priceApprovalResultNo', label: '核价结果', dataType: '关系', generated: true,
    importable: false, description: 'SupplierMaterialPrice对应的PriceApprovalResult编号' }),
  schemaField({ key: 'priceEffectiveDate', label: '价格生效日期', dataType: '日期', generated: true,
    importable: false, description: '下单时引用有效价格的生效日期' }),
  schemaField({ key: 'taxRate', label: '税率(%)', dataType: '数字', generated: true,
    importable: false, description: '下单时固化的税率快照' }),
  schemaField({ key: 'currency', label: '币种', dataType: '文本', generated: true,
    importable: false, description: '下单时固化的币种快照' }),
  schemaField({ key: 'plannedDeliveryDate', label: '计划到货日期', dataType: '日期', required: true,
    example: '2026-08-20', description: '格式YYYY-MM-DD',
    valueSources: ['confirmedDeliveryDate', 'plannedArrivalDate', 'planDeliveryDate', 'expectedDeliveryDate'] }),
  schemaField({ key: 'deliverySourceLabel', label: '交期来源', dataType: '来源追踪', generated: true,
    importable: false, description: '服务端验证的供应商交期或采购申请需求日期' }),
  schemaField({ key: 'receiptStatusLabel', label: '收货状态', dataType: '枚举', generated: true,
    importable: false, example: '未收货', description: '由收货运行状态生成' }),
])

export const PURCHASE_ORDER_LIST_SCHEMA_COLUMNS = freeze([
  freeze({ field: 'objectNo', key: 'objectNo', label: '采购订单编号', width: 180,
    businessField: 'PurchaseOrder.objectNo', runtimeField: 'PurchaseOrderRuntimeModel.objectNo',
    canonical: true, fallbackAllowed: false }),
  freeze({ field: 'supplierName', key: 'supplierName', label: '供应商名称', width: 180 }),
  freeze({ field: 'purchaseDate', key: 'purchaseDate', label: '采购日期', width: 130 }),
  freeze({ field: 'status', key: 'status', label: '状态' }),
  freeze({ field: 'totalQuantity', key: 'totalQuantity', label: '数量' }),
  freeze({ field: 'totalAmount', key: 'totalAmount', label: '金额' }),
  freeze({ field: 'earliestArrivalDate', key: 'earliestArrivalDate', label: '交期', width: 130 }),
  freeze({ field: 'deliveryUrgencyLabel', key: 'deliveryUrgencyLabel', label: '紧急程度', width: 110 }),
])

export const PURCHASE_ORDER_SYSTEM_GENERATED_FIELDS = freeze(
  [...PURCHASE_ORDER_HEADER_SCHEMA_FIELDS, ...PURCHASE_ORDER_ITEM_SCHEMA_FIELDS]
    .filter(field => field.generated))
export const PURCHASE_ORDER_HEADER_IMPORT_SCHEMA_FIELDS = freeze(
  PURCHASE_ORDER_HEADER_SCHEMA_FIELDS.filter(field => field.importable))
export const PURCHASE_ORDER_ITEM_IMPORT_SCHEMA_FIELDS = freeze(
  PURCHASE_ORDER_ITEM_SCHEMA_FIELDS.filter(field => field.importable))

export const PURCHASE_ORDER_IMPORT_SCHEMA_FIELDS = freeze([
  ...PURCHASE_ORDER_HEADER_IMPORT_SCHEMA_FIELDS,
  ...PURCHASE_ORDER_ITEM_IMPORT_SCHEMA_FIELDS,
])

const purchaseOrderSchema = {
  name: 'purchaseOrder',
  labels: {
    en: 'Purchase Orders',
    'zh-CN': '采购订单',
  },

  meta: {
    module: 'purchase_order',
    title: '采购订单',
  },

  api: {
    module: 'purchaseOrder',
  },

  ui: {
    list: {
      columns: [
        { key: 'index', label: '序号', type: 'index', sortable: false, filter: false },
        ...PURCHASE_ORDER_LIST_SCHEMA_COLUMNS,
      ],

      actions: [
        { key: 'detail', label: '详情', type: 'route', to: '/purchase/order/:id' },
        { key: 'edit', label: '编辑', type: 'route', to: '/purchase/order/:id/edit' },
        { key: 'delete', label: '删除', type: 'event', event: 'delete' },
        { key: 'SUBMIT', label: '提交', type: 'workflow', workflowAction: 'SUBMIT' },
        { key: 'APPROVE', label: '审批', type: 'workflow', workflowAction: 'APPROVE' },
        { key: 'RECEIVE', label: '收货', type: 'workflow', workflowAction: 'RECEIVE' },
        { key: 'STOCK', label: '入库', type: 'workflow', workflowAction: 'STOCK' },
      ],
    },

    detail: {},
    form: {},
    import: {
      templateFileName: '采购订单导入模板.xlsx',
      basicSheetName: '基本信息',
      itemSheetName: '物料明细',
      instructionSheetName: '字段说明',
      headerFields: PURCHASE_ORDER_HEADER_IMPORT_SCHEMA_FIELDS,
      itemFields: PURCHASE_ORDER_ITEM_IMPORT_SCHEMA_FIELDS,
      fields: PURCHASE_ORDER_IMPORT_SCHEMA_FIELDS,
      systemGeneratedFields: PURCHASE_ORDER_SYSTEM_GENERATED_FIELDS,
      validationFlow: ['校验', '预览', '确认'],
    },
  },

  workflow: {
    ...WorkflowSchema,
    entity: 'purchaseOrder',
    stateField: 'workflow_state',
    states: ['draft', 'submitted', 'approved', 'received', 'closed'],
    transitions: [
      { from: 'draft', to: 'submitted' },
      { from: 'submitted', to: 'approved' },
      { from: 'approved', to: 'received' },
      { from: 'received', to: 'closed' },
    ],
    actions: {
      SUBMIT: ['draft'],
      APPROVE: ['submitted'],
      RECEIVE: ['approved'],
      CLOSE: ['received'],
    },
  },
}

export default purchaseOrderSchema
