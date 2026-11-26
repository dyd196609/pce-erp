export const ENTERPRISE_DATA_BOUNDARY_RULESET_VERSION = 'PCE-ENTERPRISE-DATA-BOUNDARY-RULES-V1.0'

export const enterpriseDataBoundaryRules = Object.freeze([
  Object.freeze({
    ruleId: 'DATA-BOUNDARY-001',
    title: '主数据维护入口唯一',
    requirement: 'EMD为唯一维护入口；存在多个维护所有者时失败。',
  }),
  Object.freeze({
    ruleId: 'DATA-BOUNDARY-002',
    title: '数据引用中心不得出现编辑动作',
    requirement: '新增、编辑、删除按钮数量必须为0。',
  }),
  Object.freeze({
    ruleId: 'DATA-BOUNDARY-003',
    title: '基础资料名称禁止使用历史阶段前缀',
    requirement: '受治理源码与用户可见名称只允许使用“基础资料”或“基础资料维护”。',
  }),
  Object.freeze({
    ruleId: 'DATA-BOUNDARY-004',
    title: '制造数字化能力地图不得作为业务操作入口',
    requirement: '能力地图只展示产品架构，不得链接采购、库存、质量、付款、银行或财务操作页。',
  }),
  Object.freeze({
    ruleId: 'DATA-BOUNDARY-005',
    title: '业务模块不得维护主数据',
    requirement: '业务模块只能消费EMD主数据，不得声明主数据维护所有权。',
  }),
])

export function listEnterpriseDataBoundaryRules() {
  return enterpriseDataBoundaryRules.map(rule => ({ ...rule }))
}
