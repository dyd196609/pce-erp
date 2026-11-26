export const ENTERPRISE_ENTRY_GOVERNANCE_VERSION = 'V1.14.2.8.4.8.5.2'

export const enterpriseEntryClasses = Object.freeze({
  EMD: Object.freeze({
    entryClass: 'A',
    name: '企业主数据中心',
    englishName: 'Enterprise Master Data Center',
    responsibility: '企业主数据维护',
    canonicalEntry: '/foundation',
    maintenanceDomains: Object.freeze(['组织', '客户', '供应商', '物料', 'BOM', '工艺路线', '仓库']),
  }),
  Reference: Object.freeze({
    entryClass: 'B',
    name: '数据引用中心',
    responsibility: '只读展示谁引用了哪些主数据',
    canonicalEntry: '/reference',
    forbiddenActions: Object.freeze(['新增', '编辑', '删除']),
  }),
  ManufacturingCapabilityMap: Object.freeze({
    entryClass: 'C',
    name: 'PCE制造数字化能力地图',
    responsibility: '数字化能力架构展示',
    canonicalEntry: '/manufacturing/modules',
    operationEntry: false,
  }),
  BusinessProcessCenter: Object.freeze({
    entryClass: 'D',
    name: '业务流程中心',
    responsibility: '业务流程导航',
    canonicalEntry: '/process-center',
    masterDataMaintenance: false,
  }),
})

export const legacyEnterpriseEntryMappings = Object.freeze([
  Object.freeze({
    legacyPath: '/foundation',
    legacyName: '基础资料旧导航',
    targetPath: '/foundation',
    targetName: '企业主数据中心',
    displayName: '企业基础资料',
    owner: 'EMD',
    compatibilityMode: 'canonical-alias',
  }),
  Object.freeze({
    legacyPath: '/foundation/business-partners',
    legacyName: '业务伙伴档案',
    targetPath: '/master-data/suppliers',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/suppliers',
    legacyName: '供应商档案',
    targetPath: '/master-data/suppliers',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/dealers',
    legacyName: '经销商档案',
    targetPath: '/master-data/customers',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/company-bank-accounts',
    legacyName: '企业银行账户旧入口',
    targetPath: '/reference/master-data',
    targetName: '数据引用中心',
    owner: 'Reference',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/erp/materials',
    legacyName: '物料档案旧入口',
    targetPath: '/master-data/materials',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/erp/customers',
    legacyName: '客户档案旧入口',
    targetPath: '/master-data/customers',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/erp/suppliers',
    legacyName: '供应商主数据旧入口',
    targetPath: '/master-data/suppliers',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/erp/warehouses',
    legacyName: '仓库档案旧入口',
    targetPath: '/master-data/warehouses',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/foundation/manufacturing/routings',
    legacyName: '工艺路线旧入口',
    targetPath: '/master-data/routings',
    targetName: '企业主数据中心',
    owner: 'EMD',
    compatibilityMode: 'redirect',
  }),
  Object.freeze({
    legacyPath: '/manufacturing',
    legacyName: '制造业核心模块旧入口',
    targetPath: '/manufacturing/modules',
    targetName: 'PCE制造数字化能力地图',
    owner: 'ManufacturingCapabilityMap',
    compatibilityMode: 'redirect',
  }),
])

export function findLegacyEnterpriseEntry(path = '') {
  return legacyEnterpriseEntryMappings.find(mapping => mapping.legacyPath === path) || null
}

export function listLegacyEnterpriseEntryMappings() {
  return legacyEnterpriseEntryMappings.map(mapping => ({ ...mapping }))
}
