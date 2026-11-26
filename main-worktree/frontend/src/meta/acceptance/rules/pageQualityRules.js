export const PAGE_QUALITY_RULESET_VERSION = 'V1.14.2.8.4.8.4.1'

export const pageQualityRules = Object.freeze([
  {
    ruleId: 'PAGE-QUALITY-001',
    title: '页面必须有业务归属',
    severity: 'FAIL',
    requiredEvidence: ['moduleCode', 'moduleName'],
  },
  {
    ruleId: 'PAGE-QUALITY-002',
    title: '页面必须绑定流程节点',
    severity: 'FAIL',
    requiredEvidence: ['processCode', 'nodeCode', 'pageUrl'],
  },
  {
    ruleId: 'PAGE-QUALITY-003',
    title: '页面必须存在版本号',
    severity: 'FAIL',
    requiredEvidence: ['pageVersion'],
  },
  {
    ruleId: 'PAGE-QUALITY-004',
    title: '页面必须存在自动验收状态',
    severity: 'FAIL',
    requiredEvidence: ['acceptanceStatus'],
  },
  {
    ruleId: 'PAGE-QUALITY-005',
    title: '详情页禁止 JSON 展示',
    severity: 'FAIL',
    prohibitedPatterns: ['JSON.stringify(dialogRow', 'sourceObjectRefs', 'technicalState'],
  },
  {
    ruleId: 'PAGE-QUALITY-006',
    title: '详情必须使用 PceBusinessDetailCard',
    severity: 'FAIL',
    requiredComponent: 'PceBusinessDetailCard',
  },
  {
    ruleId: 'PAGE-QUALITY-007',
    title: '列表页面必须符合 PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
    severity: 'FAIL',
    requiredCapabilities: [
      'search',
      'advancedFilter',
      'exportCurrent',
      'fixedColumns',
      'horizontalScroll',
    ],
  },
])

export function listPageQualityRules() {
  return pageQualityRules.map(rule => ({
    ...rule,
    requiredEvidence: [...(rule.requiredEvidence || [])],
    prohibitedPatterns: [...(rule.prohibitedPatterns || [])],
    requiredCapabilities: [...(rule.requiredCapabilities || [])],
  }))
}
