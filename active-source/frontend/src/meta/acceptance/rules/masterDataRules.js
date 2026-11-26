export const MASTER_DATA_RULESET_VERSION = 'PCE-MASTER-DATA-GOVERNANCE-RULES-V1.0'

export const masterDataRules = Object.freeze([
  { ruleId: 'MASTER-001', title: '所有主数据页面必须绑定业务模块' },
  { ruleId: 'MASTER-002', title: '所有主数据页面必须绑定流程节点' },
  { ruleId: 'MASTER-003', title: '所有主数据页面必须存在页面版本' },
  { ruleId: 'MASTER-004', title: '所有主数据页面必须存在AcceptanceStatus' },
  { ruleId: 'MASTER-005', title: '所有主数据页面必须使用企业列表模板' },
  { ruleId: 'MASTER-006', title: '详情禁止JSON并必须使用PceBusinessDetailCard' },
  { ruleId: 'MASTER-007', title: 'API、页面、诊断、StrictFacts和AcceptanceFacts事实来源必须为server' },
])

export function listMasterDataRules() {
  return masterDataRules.map(rule => ({ ...rule }))
}
