import {
  currentResultRemoteSelectOptionsProvider,
  materialMasterRemoteSelectOptionsProvider,
  supplierMasterRemoteSelectOptionsProvider,
} from '../runtime/remoteSelectOptionsProvider.js'

export const MASTER_DATA_GOVERNANCE_VERSION = 'V1.14.2.8.4.8.5.1'
export const MASTER_DATA_PROCESS_CODE = 'EMD_MASTER_DATA_MAINTENANCE'
export const ENTERPRISE_MASTER_DATA_CENTER = Object.freeze({
  moduleCode: 'EMD',
  moduleName: '企业主数据中心',
  englishName: 'Enterprise Master Data Center',
  abbreviation: 'EMD',
  responsibility: Object.freeze(['组织', '客户', '供应商', '物料', 'BOM', '工艺路线', '仓库']),
  excludedResponsibility: Object.freeze(['采购订单', '库存业务', '质量业务', '付款业务', '财务业务']),
  maintenanceEntry: '/master-data/organizations',
})

const statusOptions = [
  { label: '启用', value: '启用' },
  { label: '已发布', value: '已发布' },
]
const currentResultOptions = Object.freeze({
  optionsSource: 'currentResultDistinctValues',
  optionsProvider: 'currentResultDistinctValues',
})

const foundationStatusOptions = Object.freeze([
  Object.freeze({ value: 'enabled', label: '启用' }),
  Object.freeze({ value: 'disabled', label: '停用' }),
])
const employeeStatusOptions = Object.freeze([
  Object.freeze({ value: 'active', label: '在职' }),
  Object.freeze({ value: 'resigned', label: '离职' }),
  Object.freeze({ value: 'leave', label: '休假' }),
  Object.freeze({ value: 'borrowed', label: '借调' }),
])
const industryOptions = Object.freeze([
  Object.freeze({ value: 'printing', label: '印刷行业' }),
  Object.freeze({ value: 'wholeHouseWood', label: '全屋定制/整木' }),
  Object.freeze({ value: 'general', label: '通用制造' }),
])

export const MASTER_DATA_PAGE_ACTION_POLICIES = Object.freeze({
  fact: Object.freeze(['view']),
  readonlyMaster: Object.freeze(['view']),
  master: Object.freeze(['view', 'edit']),
  config: Object.freeze(['view', 'edit', 'toggle-status']),
})

function inferredFilterType(key, input = {}) {
  if (input.filterType) return input.filterType
  if (/Code$/.test(key) || ['employeeNo', 'priceFactId', 'relationCode'].includes(key)) return 'remote-select'
  return (
    input.type === 'number' ? 'numberRange'
      : input.type === 'date' ? 'daterange'
        : input.type === 'select' || input.type === 'checkbox' ? 'select' : 'text'
  )
}

function inferredRemoteProvider(key, input = {}) {
  if (input.optionsProvider && typeof input.optionsProvider === 'object') return input.optionsProvider
  if (/supplier/i.test(key)) return supplierMasterRemoteSelectOptionsProvider
  if (/material/i.test(key)) return materialMasterRemoteSelectOptionsProvider
  return currentResultRemoteSelectOptionsProvider
}

const field = (key, label, input = {}) => {
  const filterType = inferredFilterType(key, input)
  const options = Object.freeze(input.options || [])
  const remoteProvider = filterType === 'remote-select' ? inferredRemoteProvider(key, input) : null
  const optionsSource = input.optionsSource
    || remoteProvider?.providerCode
    || (options.length ? 'static' : filterType === 'select' ? 'currentResultDistinctValues' : 'none')
  const optionsProvider = input.optionsProvider
    || remoteProvider
    || (filterType === 'select' ? optionsSource : 'none')
  return Object.freeze({
    key,
    field: key,
    label,
    width: input.width || 150,
    ...input,
    filterType,
    options,
    optionsSource,
    optionsProvider,
  })
}

const foundationDefinitions = [
  {
    entityCode: 'supplier-price-analysis-history',
    metadataVersion: 'V1.14.2.8.4.27.2.37',
    metadataCode: 'PCE-MD-SUPPLIER-PRICE-ANALYSIS-HISTORY-LIST',
    pageCode: 'foundation-supplier-price-analysis',
    route: '/foundation/erp/supplier-price-analysis',
    collection: 'supplierPriceAnalysisHistory',
    title: '供应商价格历史',
    pageKind: 'fact',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.fact,
    primaryField: 'priceFactId',
    primaryLabel: '价格事实编号',
    fields: [
      field('priceFactId', '价格事实编号', { required: true, readonly: true, width: 190 }),
      field('supplierDisplay', '供应商', { required: true, filterType: 'remote-select', sourceKey: 'supplierCode', width: 220 }),
      field('materialDisplay', '物料', { required: true, filterType: 'remote-select', sourceKey: 'materialCode', width: 220 }),
      field('unitPrice', '执行价格', { type: 'number', required: true, width: 120 }),
      field('currency', '币种', { type: 'select', width: 100 }),
      field('sourceType', '价格来源', { type: 'select', width: 170 }),
      field('effectiveDate', '执行日期', { type: 'date', width: 130 }),
      field('previousPrice', '上次价格', { type: 'number', width: 120 }),
      field('changeRatioDisplay', '环比变化', { filterable: false, width: 120 }),
      field('trendLabel', '趋势', { type: 'select', width: 100 }),
    ],
  },
  {
    entityCode: 'supplier-price-comparison',
    metadataVersion: 'V1.14.2.8.4.27.2.37',
    metadataCode: 'PCE-MD-SUPPLIER-PRICE-COMPARISON-LIST',
    pageCode: 'foundation-supplier-price-analysis',
    route: '/foundation/erp/supplier-price-analysis',
    collection: 'supplierPriceComparisons',
    title: '供应商价格比较',
    pageKind: 'fact',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.fact,
    primaryField: 'comparisonId',
    primaryLabel: '比较编号',
    fields: [
      field('comparisonId', '比较编号', { required: true, readonly: true, width: 220 }),
      field('materialDisplay', '物料', { required: true, filterType: 'remote-select', sourceKey: 'materialCode', width: 220 }),
      field('supplierDisplay', '供应商', { required: true, filterType: 'remote-select', sourceKey: 'supplierCode', width: 220 }),
      field('unitPrice', '最近价格', { type: 'number', width: 120 }),
      field('currency', '币种', { type: 'select', width: 100 }),
      field('sourceType', '价格来源', { type: 'select', width: 170 }),
      field('effectiveDate', '价格日期', { type: 'date', width: 130 }),
      field('supplierCandidateCount', '可比供应商数', { type: 'number', width: 130 }),
      field('deviationDisplay', '偏离均价', { filterable: false, width: 120 }),
      field('comparisonStatusLabel', '比较状态', { type: 'select', width: 120 }),
    ],
  },
  {
    entityCode: 'supplier-price-facts',
    metadataVersion: 'V1.14.2.8.4.27.2.34',
    metadataCode: 'PCE-MD-SUPPLIER-PRICE-FACT-LIST',
    pageCode: 'foundation-supplier-price-facts',
    route: '/foundation/erp/supplier-price-facts',
    collection: 'supplierPriceFacts',
    title: '供应商价格事实',
    pageKind: 'fact',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.fact,
    primaryField: 'priceFactId',
    primaryLabel: '价格事实编号',
    fields: [
      field('priceFactId', '价格事实编号', { required: true, readonly: true, width: 190 }),
      field('supplierDisplay', '供应商', { required: true, filterType: 'remote-select', sourceKey: 'supplierCode', width: 220 }),
      field('materialDisplay', '物料', { required: true, filterType: 'remote-select', sourceKey: 'materialCode', width: 220 }),
      field('unitPrice', '价格', { type: 'number', required: true, width: 120 }),
      field('currency', '币种', { type: 'select', width: 100 }),
      field('unit', '单位', { type: 'select', width: 100 }),
      field('taxRate', '税率', { type: 'number', width: 100 }),
      field('deliveryPeriod', '交货周期（天）', { type: 'number', width: 140 }),
      field('sourceType', '来源类型', { type: 'select', options: [
        { value: 'SupplierQuotation', label: '供应商报价' },
        { value: 'SupplierMaterialPrice', label: '供应商物料价格' },
        { value: 'PurchaseOrderHistory', label: '历史采购订单' },
        { value: 'TEST_BASE_PRICE', label: '测试基础价格' },
      ], width: 170 }),
      field('sourceReference', '来源单据', { width: 260 }),
      field('effectiveDate', '生效日期', { type: 'date', width: 130 }),
      field('expiryDate', '失效日期', { type: 'date', width: 130 }),
      field('status', '状态', { type: 'select', options: [
        { value: 'ACTIVE', label: '有效报价' },
        { value: 'PENDING_VALIDITY', label: '待补有效期' },
        { value: 'HISTORICAL', label: '历史执行价' },
        { value: 'TEST_BASE_PRICE', label: '测试基础价格' },
      ], statusField: true, width: 140 }),
    ],
  },
  {
    entityCode: 'employees',
    metadataCode: 'PCE-MD-EMPLOYEE-LIST',
    pageCode: 'foundation-employees',
    route: '/foundation/pfm/employees',
    collection: 'employees',
    title: '员工档案',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.master,
    primaryField: 'employeeNo',
    primaryLabel: '工号',
    fields: [
      field('employeeNo', '工号', { required: true, readonly: true, width: 160 }),
      field('name', '姓名', { required: true, width: 140 }),
      field('idCardNo', '身份证号', { width: 190 }),
      field('nativePlace', '籍贯'),
      field('department', '部门', { required: true }),
      field('role', '岗位', { required: true }),
      field('jobGrade', '职等', { width: 110 }),
      field('jobLevel', '职级', { width: 110 }),
      field('hireDate', '入职日期', { type: 'date', width: 140 }),
      field('leaveDate', '离职日期', { type: 'date', width: 140 }),
      field('workYears', '工龄', { type: 'number', readonly: true, width: 110 }),
      field('status', '人员状态', { type: 'select', options: employeeStatusOptions, statusField: true, width: 130 }),
      field('phone', '电话', { width: 150 }),
    ],
  },
  {
    entityCode: 'supplier-material-prices',
    metadataVersion: 'V1.14.2.8.4.27.2.45.8',
    metadataCode: 'PCE-MD-SUPPLIER-MATERIAL-PRICE-LIST',
    pageCode: 'foundation-supplier-material-prices',
    route: '/foundation/erp/supplier-material-prices',
    collection: 'supplierMaterialPrices',
    title: '供应商有效价格',
    pageKind: 'config',
    actionPolicy: Object.freeze(['view', 'edit']),
    primaryField: 'priceId',
    primaryLabel: '价格记录编码',
    fields: [
      field('priceId', '价格记录编码', { required: true, readonly: true, width: 180 }),
      field('supplierDisplay', '供应商', { required: true, filterType: 'remote-select', sourceKey: 'supplierCode', width: 220 }),
      field('materialDisplay', '物料', { required: true, filterType: 'remote-select', sourceKey: 'materialCode', width: 220 }),
      field('unitPrice', '含税单价', { type: 'number', required: true, readonly: true, width: 130 }),
      field('taxRate', '税率（%）', { type: 'select', options: [
        { value: '0', label: '0%' }, { value: '3', label: '3%' }, { value: '6', label: '6%' },
        { value: '9', label: '9%' }, { value: '13', label: '13%' },
      ], width: 110 }),
      field('currency', '币种', { type: 'select', width: 110 }),
      field('effectiveDate', '生效日期', { type: 'date', width: 130 }),
      field('expiryDate', '失效日期', { type: 'date', width: 130 }),
      field('statusLabel', '状态', { type: 'select', statusField: true, width: 120 }),
      field('versionStatusLabel', '价格版本状态', { type: 'select', width: 150 }),
      field('versionNo', '版本序号', { type: 'number', width: 110 }),
      field('overlapStatus', '有效期重叠状态', { type: 'select', width: 230 }),
      field('overlapClassification', '重叠分类', { type: 'select', width: 240 }),
      field('overlappingPriceNos', '重叠价格编号', { width: 260 }),
      field('effectiveIdentityStatus', '当前价格身份治理', { type: 'select', width: 230 }),
      field('sourceTypeLabel', '价格来源', { type: 'select', width: 160 }),
      field('priceApprovalResultId', '核价决策结果', { width: 220 }),
      field('originalSourceTypeLabel', '原始来源类型', { type: 'select', width: 180 }),
      field('sourceReference', '来源编号', { width: 220 }),
      field('approvalStatusLabel', '审批状态', { type: 'select', width: 130 }),
      field('confirmedBy', '确认人', { width: 130 }),
      field('confirmedAt', '确认时间', { type: 'date', width: 180 }),
      field('createdAt', '创建时间', { type: 'date', width: 180 }),
      field('taxModifiedBy', '最近修改人', { width: 130 }),
      field('taxModifiedAt', '最近修改时间', { type: 'date', width: 180 }),
      field('taxModificationReason', '最近修改原因', { width: 220 }),
      field('modificationAuditCount', '维护审计数', { type: 'number', width: 120 }),
    ],
  },
  {
    entityCode: 'processes',
    metadataCode: 'PCE-MD-PROCESS-LIST',
    pageCode: 'foundation-processes',
    route: '/foundation/manufacturing/processes',
    collection: 'processes',
    title: '工序资料',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.master,
    primaryField: 'processCode',
    primaryLabel: '工序编码',
    fields: [
      field('processCode', '工序编码', { required: true, readonly: true, width: 160 }),
      field('processName', '工序名称', { required: true, width: 180 }),
      field('industryType', '行业类型', { type: 'select', options: industryOptions, width: 160 }),
      field('workCenterId', '工作中心', { type: 'select', width: 160 }),
      field('standardHours', '标准工时', { type: 'number', width: 130 }),
      field('skillRequired', '技能要求', { width: 160 }),
      field('qualityCheckRequired', '质检要求', { type: 'checkbox', options: [{ value: true, label: '是' }, { value: false, label: '否' }], width: 130 }),
      field('status', '状态', { type: 'select', options: foundationStatusOptions, statusField: true, width: 120 }),
    ],
  },
  {
    entityCode: 'routings-foundation',
    metadataCode: 'PCE-MD-ROUTING-LIST',
    pageCode: 'foundation-routings',
    route: '/foundation/manufacturing/routings',
    collection: 'routings',
    title: '工艺路线',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.master,
    primaryField: 'routingCode',
    primaryLabel: '工艺路线编码',
    fields: [
      field('routingCode', '工艺路线编码', { required: true, readonly: true, width: 180 }),
      field('routingName', '工艺路线名称', { required: true, width: 190 }),
      field('industryType', '行业类型', { type: 'select', options: industryOptions, width: 160 }),
      field('productCategory', '产品类别', { type: 'select', width: 160 }),
      field('materialId', '适用物料', { filterType: 'remote-select', width: 180 }),
      field('version', '版本', { width: 110 }),
      field('status', '状态', { type: 'select', options: foundationStatusOptions, statusField: true, width: 120 }),
    ],
  },
  {
    entityCode: 'equipment',
    metadataCode: 'PCE-MD-EQUIPMENT-LIST',
    pageCode: 'foundation-equipment',
    route: '/foundation/manufacturing/equipment',
    collection: 'equipment',
    title: '设备资料',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.master,
    primaryField: 'equipmentCode',
    primaryLabel: '设备编码',
    fields: [
      field('equipmentCode', '设备编码', { required: true, readonly: true, width: 160 }),
      field('equipmentName', '设备名称', { required: true, width: 180 }),
      field('industryType', '行业类型', { type: 'select', options: industryOptions, width: 160 }),
      field('workCenterId', '工作中心', { required: true, type: 'select', width: 160 }),
      field('equipmentType', '设备类型', { type: 'select', width: 150 }),
      field('capacityPerHour', '每小时产能', { type: 'number', width: 140 }),
      field('status', '状态', { type: 'select', options: foundationStatusOptions, statusField: true, width: 120 }),
    ],
  },
]

export const foundationListMetadataRegistry = Object.freeze(
  foundationDefinitions.map(definition => Object.freeze({
    ...definition,
    metadataVersion: definition.metadataVersion || 'V1.14.2.8.4.27.2.32',
    metadataSource: 'masterDataRegistry',
    columns: Object.freeze(definition.fields.filter(item => item.key !== definition.primaryField)),
    filterSchema: Object.freeze(definition.fields.map(item => Object.freeze({
      field: item.key,
      label: item.label,
      filterType: item.filterType,
      options: item.options || Object.freeze([]),
      optionsSource: item.optionsSource,
      optionsProvider: item.optionsProvider,
      sourceKey: item.sourceKey || item.key,
    }))),
    searchFields: Object.freeze(definition.fields.map(item => item.key)),
  })),
)

export function findFoundationListMetadata(collection = '') {
  return foundationListMetadataRegistry.find(item => item.collection === String(collection)) || null
}

function normalizeMasterFilterField(input = {}) {
  const fieldName = String(input.field || '')
  const remoteProvider = /supplierCode$/i.test(fieldName)
    ? supplierMasterRemoteSelectOptionsProvider
    : /materialCode$/i.test(fieldName)
      ? materialMasterRemoteSelectOptionsProvider
      : /Code$/.test(fieldName)
        ? currentResultRemoteSelectOptionsProvider
        : null
  const filterType = remoteProvider ? 'remote-select' : input.filterType
  const options = Object.freeze(input.options || [])
  const optionsSource = input.optionsSource
    || remoteProvider?.providerCode
    || (options.length ? 'static' : filterType === 'select' ? 'currentResultDistinctValues' : 'none')
  return {
    ...input,
    filterType,
    options,
    optionsSource,
    optionsProvider: input.optionsProvider || remoteProvider || (filterType === 'select' ? optionsSource : 'none'),
    sourceKey: input.sourceKey || fieldName,
  }
}

const definitions = [
  {
    entityCode: 'organizations',
    masterDataCode: 'MD-ORG',
    pageCode: 'master-data-organizations',
    nodeCode: 'organization-data',
    title: '组织主数据',
    listTitle: '组织主数据列表',
    primaryField: 'organizationCode',
    primaryLabel: '组织编码',
    searchFields: ['organizationCode', 'organizationName', 'organizationType', 'parentOrganization'],
    columns: [
      ['organizationName', '组织名称', 220],
      ['organizationType', '组织类型', 150],
      ['parentOrganization', '上级组织', 220],
      ['businessStatus', '组织状态', 130],
    ],
    filterSchema: [
      { field: 'organizationCode', label: '组织编码', filterType: 'text' },
      { field: 'organizationName', label: '组织名称', filterType: 'text' },
      { field: 'organizationType', label: '组织类型', filterType: 'select', options: ['公司', '工厂', '部门', '工作中心'].map(value => ({ label: value, value })) },
      { field: 'businessStatus', label: '组织状态', filterType: 'select', options: statusOptions },
    ],
  },
  {
    entityCode: 'customers',
    masterDataCode: 'MD-CUSTOMER',
    pageCode: 'master-data-customers',
    nodeCode: 'customer-data',
    title: '客户主数据',
    listTitle: '客户主数据列表',
    primaryField: 'customerCode',
    primaryLabel: '客户编码',
    searchFields: ['customerCode', 'customerName', 'creditLevel', 'contactName'],
    columns: [
      ['customerName', '客户名称', 240],
      ['creditLevel', '信用等级', 130],
      ['contactName', '联系人', 150],
      ['contactPhone', '联系信息', 180],
      ['businessStatus', '客户状态', 130],
    ],
    filterSchema: [
      { field: 'customerCode', label: '客户编码', filterType: 'text' },
      { field: 'customerName', label: '客户名称', filterType: 'text' },
      { field: 'creditLevel', label: '信用等级', filterType: 'select', options: ['A', 'B', 'C'].map(value => ({ label: value, value })) },
      { field: 'businessStatus', label: '客户状态', filterType: 'select', options: statusOptions },
    ],
  },
  {
    entityCode: 'suppliers',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.readonlyMaster,
    maintenanceRoute: '/foundation/erp/suppliers',
    masterDataCode: 'MD-SUPPLIER',
    pageCode: 'master-data-suppliers',
    nodeCode: 'supplier-data',
    title: '供应商主数据',
    listTitle: '供应商列表',
    primaryField: 'supplierCode',
    primaryLabel: '供应商编码',
    searchFields: ['supplierCode', 'supplierName', 'category', 'contactName', 'address', 'deliveryAddress', 'supplierLevel'],
    columns: [
      ['supplierName', '供应商名称', 250],
      ['category', '分类', 160],
      ['contactName', '联系人', 140],
      ['contactPhone', '联系信息', 180],
      ['address', '地址', 220],
      ['deliveryAddress', '送货地址', 220],
      ['businessStatus', '供应商状态', 130],
      ['supplierLevel', '供应商等级', 140],
      ['usageCount', '业务引用次数', 130],
      ['mappingStatus', '映射状态', 160],
    ],
    filterSchema: [
      { field: 'supplierCode', label: '供应商编码', filterType: 'text' },
      { field: 'supplierName', label: '供应商名称', filterType: 'text' },
      { field: 'category', label: '分类', filterType: 'select', ...currentResultOptions },
      { field: 'businessStatus', label: '供应商状态', filterType: 'select', ...currentResultOptions },
      { field: 'supplierLevel', label: '供应商等级', filterType: 'select', ...currentResultOptions },
    ],
  },
  {
    entityCode: 'materials',
    pageKind: 'master',
    actionPolicy: MASTER_DATA_PAGE_ACTION_POLICIES.master,
    maintenanceRoute: '/foundation/erp/materials',
    masterDataCode: 'MD-MATERIAL',
    pageCode: 'master-data-materials',
    nodeCode: 'material-data',
    title: '物料主数据',
    listTitle: '物料主数据列表',
    primaryField: 'materialCode',
    primaryLabel: '物料编码',
    searchFields: ['materialCode', 'materialName', 'specification', 'category', 'materialType'],
    columns: [
      ['materialName', '物料名称', 230],
      ['specification', '规格', 180],
      ['unit', '单位', 100],
      ['category', '分类', 160],
      ['materialType', '类型', 140],
      ['businessStatus', '物料状态', 130],
    ],
    filterSchema: [
      { field: 'materialCode', label: '物料编码', filterType: 'text' },
      { field: 'materialName', label: '物料名称', filterType: 'text' },
      { field: 'materialType', label: '类型', filterType: 'select', ...currentResultOptions },
      { field: 'category', label: '分类', filterType: 'text' },
      { field: 'businessStatus', label: '物料状态', filterType: 'select', ...currentResultOptions },
    ],
  },
  {
    entityCode: 'boms',
    masterDataCode: 'MD-BOM',
    pageCode: 'master-data-boms',
    nodeCode: 'bom-data',
    title: 'BOM基础数据',
    listTitle: 'BOM基础数据列表',
    primaryField: 'bomNo',
    primaryLabel: 'BOM编号',
    searchFields: ['bomNo', 'productName', 'bomVersion', 'componentName'],
    columns: [
      ['productName', '产品', 220],
      ['bomVersion', 'BOM版本', 130],
      ['componentName', '子件', 220],
      ['quantity', '数量', 110],
      ['unit', '单位', 100],
      ['businessStatus', 'BOM状态', 130],
    ],
    filterSchema: [
      { field: 'bomNo', label: 'BOM编号', filterType: 'text' },
      { field: 'productName', label: '产品', filterType: 'text' },
      { field: 'bomVersion', label: 'BOM版本', filterType: 'select', options: [{ label: 'V1.0', value: 'V1.0' }] },
      { field: 'businessStatus', label: 'BOM状态', filterType: 'select', options: statusOptions },
    ],
  },
  {
    entityCode: 'routings',
    masterDataCode: 'MD-ROUTING',
    pageCode: 'master-data-routings',
    nodeCode: 'routing-data',
    title: '工艺路线基础数据',
    listTitle: '工艺路线基础数据列表',
    primaryField: 'routingNo',
    primaryLabel: '路线编号',
    searchFields: ['routingNo', 'operationName', 'workCenter'],
    columns: [
      ['operationName', '工序', 220],
      ['sequence', '顺序', 100],
      ['workCenter', '工作中心', 220],
      ['standardHours', '标准工时', 140],
      ['businessStatus', '工艺路线状态', 130],
    ],
    filterSchema: [
      { field: 'routingNo', label: '路线编号', filterType: 'text' },
      { field: 'operationName', label: '工序', filterType: 'text' },
      { field: 'workCenter', label: '工作中心', filterType: 'text' },
      { field: 'standardHours', label: '标准工时', filterType: 'numberRange' },
      { field: 'businessStatus', label: '工艺路线状态', filterType: 'select', ...currentResultOptions },
    ],
  },
  {
    entityCode: 'warehouses',
    masterDataCode: 'MD-WAREHOUSE',
    pageCode: 'master-data-warehouses',
    nodeCode: 'warehouse-data',
    title: '仓库基础数据',
    listTitle: '仓库基础数据列表',
    primaryField: 'warehouseCode',
    primaryLabel: '仓库编码',
    searchFields: ['warehouseCode', 'warehouseName', 'zoneName', 'locationCode'],
    columns: [
      ['warehouseName', '仓库', 220],
      ['zoneName', '库区', 200],
      ['locationCode', '库位', 160],
      ['businessStatus', '仓库状态', 130],
    ],
    filterSchema: [
      { field: 'warehouseCode', label: '仓库编码', filterType: 'text' },
      { field: 'warehouseName', label: '仓库', filterType: 'text' },
      { field: 'zoneName', label: '库区', filterType: 'text' },
      { field: 'locationCode', label: '库位', filterType: 'text' },
      { field: 'businessStatus', label: '仓库状态', filterType: 'select', options: statusOptions },
    ],
  },
]

export const masterDataRegistry = Object.freeze(
  definitions.map(definition => Object.freeze({
    ...definition,
    pageKind: definition.pageKind || 'master',
    actionPolicy: definition.actionPolicy || MASTER_DATA_PAGE_ACTION_POLICIES.master,
    columns: Object.freeze(definition.columns.map(column => Object.freeze(column))),
    filterSchema: Object.freeze(definition.filterSchema.map(field => Object.freeze(normalizeMasterFilterField(field)))),
    pageUrl: `/master-data/${definition.entityCode}`,
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
    processCode: MASTER_DATA_PROCESS_CODE,
    pageVersion: MASTER_DATA_GOVERNANCE_VERSION,
    acceptanceStatus: 'PASS',
  })),
)

export function findMasterDataDefinition(entityCode = '') {
  return masterDataRegistry.find(item => item.entityCode === String(entityCode)) || null
}

export function listMasterDataDefinitions() {
  return masterDataRegistry.map(item => ({
    ...item,
    columns: item.columns.map(column => [...column]),
    filterSchema: item.filterSchema.map(field => ({ ...field })),
  }))
}

export function createMasterDataPageGovernance(entityCode = '') {
  const definition = findMasterDataDefinition(entityCode)
  if (!definition) throw new Error(`Unknown enterprise master-data entity: ${entityCode}`)
  const flowSteps = ['组织数据', '客户数据', '供应商数据', '物料数据', 'BOM数据', '工艺路线', '仓库数据']
  const currentFlowStep = {
    'organization-data': '组织数据',
    'customer-data': '客户数据',
    'supplier-data': '供应商数据',
    'material-data': '物料数据',
    'bom-data': 'BOM数据',
    'routing-data': '工艺路线',
    'warehouse-data': '仓库数据',
  }[definition.nodeCode]
  return Object.freeze({
    version: definition.pageVersion,
    frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
    businessModule: 'EMD',
    pageName: definition.title,
    pageCode: definition.pageCode,
    purpose: '维护并查看企业统一基础对象的服务端治理事实。',
    allowed: ['✓ 查看主数据', '✓ 搜索与筛选', '✓ 导出当前结果', '✓ 查看详情'],
    forbidden: ['× 推进采购交易', '× 付款执行', '× 银行发送', '× 财务影响'],
    flowSteps,
    currentFlowStep,
    navigation: { previous: '企业主数据中心', next: '业务模块引用' },
  })
}
