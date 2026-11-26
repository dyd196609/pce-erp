export const MODULE_STRUCTURE_RULESET_VERSION = 'V1.14.2.8.4.8.4.1'

export const moduleStructureRules = Object.freeze([
  {
    ruleId: 'MODULE-001',
    title: 'PDE必须存在',
    severity: 'FAIL',
    requiredModuleCode: 'PDE',
  },
  {
    ruleId: 'MODULE-002',
    title: 'PDE必须位于SCM之前',
    severity: 'FAIL',
    beforeModule: 'PDE',
    afterModule: 'SCM',
  },
  {
    ruleId: 'MODULE-003',
    title: '业务模块必须有唯一排序',
    severity: 'FAIL',
    requiredField: 'order',
  },
  {
    ruleId: 'MODULE-004',
    title: '流程节点必须具备模块、流程和节点编码',
    severity: 'FAIL',
    requiredFields: ['moduleCode', 'processCode', 'nodeCode'],
  },
  {
    ruleId: 'MODULE-005',
    title: 'PDE页面状态不能伪造',
    severity: 'FAIL',
    expectedPageStatus: 'planned',
    expectedAcceptanceStatus: 'not_started',
    expectedPageUrl: '',
  },
])

export function listModuleStructureRules() {
  return moduleStructureRules.map(rule => ({
    ...rule,
    requiredFields: [...(rule.requiredFields || [])],
  }))
}
