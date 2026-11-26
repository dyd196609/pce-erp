export const ENTERPRISE_ENTRY_RULESET_VERSION = 'PCE-ENTERPRISE-ENTRY-GOVERNANCE-RULES-V1.0'

export const enterpriseEntryRules = Object.freeze([
  Object.freeze({
    ruleId: 'ENTRY-001',
    title: '一个主数据只能存在一个维护入口',
    requirement: '组织、客户、供应商、物料、BOM、工艺路线、仓库分别只有一个EMD维护入口。',
  }),
  Object.freeze({
    ruleId: 'ENTRY-002',
    title: 'Reference必须只读',
    requirement: '数据引用中心不提供创建、修改或移除动作。',
  }),
  Object.freeze({
    ruleId: 'ENTRY-003',
    title: '能力地图不能存在业务执行按钮',
    requirement: '能力地图只允许产品能力架构展示。',
  }),
  Object.freeze({
    ruleId: 'ENTRY-004',
    title: '旧入口必须有迁移关系',
    requirement: '每个旧入口必须声明目标入口与兼容方式。',
  }),
  Object.freeze({
    ruleId: 'ENTRY-005',
    title: '页面名称不得使用阶段、临时或复制型命名',
    requirement: '入口页面名称必须使用正式企业级名称。',
  }),
  Object.freeze({
    ruleId: 'ENTRY-006',
    title: '业务流程中心不能直接维护主数据',
    requirement: '业务流程中心只负责业务流程导航。',
  }),
])

export function listEnterpriseEntryRules() {
  return enterpriseEntryRules.map(rule => ({ ...rule }))
}
