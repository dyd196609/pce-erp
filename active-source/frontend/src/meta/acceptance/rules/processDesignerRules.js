export const PROCESS_DESIGNER_RULESET_VERSION = 'V1.14.2.8.4.8.4.2'

export const processDesignerRules = Object.freeze([
  {
    ruleId: 'DESIGN-001',
    title: '流程设计中心必须使用businessProcessRegistry',
    severity: 'FAIL',
    requiredSource: 'businessProcessRegistry',
  },
  {
    ruleId: 'DESIGN-002',
    title: '流程设计中心禁止读取enterpriseOperationStore',
    severity: 'FAIL',
    forbiddenSource: 'enterpriseOperationStore',
  },
  {
    ruleId: 'DESIGN-003',
    title: '流程中心和设计中心流程数量必须一致',
    severity: 'FAIL',
    comparison: 'processCenterCount=processDesignerCount',
  },
  {
    ruleId: 'DESIGN-004',
    title: '流程中心和设计中心节点顺序必须一致',
    severity: 'FAIL',
    comparison: 'processCenterNodes=processDesignerNodes',
  },
  {
    ruleId: 'DESIGN-005',
    title: '流程及节点页面版本必须来自统一注册表',
    severity: 'FAIL',
    requiredFields: ['processVersion', 'pageVersion'],
  },
])

export function listProcessDesignerRules() {
  return processDesignerRules.map(rule => ({
    ...rule,
    requiredFields: [...(rule.requiredFields || [])],
  }))
}
