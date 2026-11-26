export const ENGINEERING_RULE_STATUS_OPTIONS = Object.freeze([
  Object.freeze({ value: 'draft', label: '草稿' }),
  Object.freeze({ value: 'reviewed', label: '已评审' }),
  Object.freeze({ value: 'released', label: '已发布' }),
  Object.freeze({ value: 'obsolete', label: '已失效' }),
])

export const ENGINEERING_RULE_KIND_LABELS = Object.freeze({
  formula: '安全表达式',
  lookup: '受控查表',
  decision: '受控判断',
  mapping: '受控映射',
  aggregation: '受控聚合',
})

function distinctOptions(rows = [], field, labelFactory) {
  const values = new Map()
  for (const row of rows) {
    const value = String(row?.[field] ?? '').trim()
    if (!value || values.has(value)) continue
    values.set(value, Object.freeze({ value, label: labelFactory(row, value) }))
  }
  return [...values.values()]
}

const authorizedFormalRows = ({ rows = [] } = {}) => rows.filter(row => row?.id != null)

export const ENGINEERING_RULE_FILTER_SCHEMA = Object.freeze([
  Object.freeze({
    field: 'rule_code',
    label: '规则编码',
    filterType: 'select',
    matchMode: 'contains',
    allowCustomValue: true,
    placeholder: '选择完整编码或输入关键词',
    optionsSource: ({ rows }) => distinctOptions(
      authorizedFormalRows({ rows }),
      'rule_code',
      (row, value) => `${value} · ${row.rule_name || '名称未提供'}`,
    ),
  }),
  Object.freeze({
    field: 'rule_name',
    label: '规则名称',
    filterType: 'select',
    matchMode: 'contains',
    allowCustomValue: true,
    placeholder: '选择规则名称或输入关键词',
    optionsSource: ({ rows }) => distinctOptions(
      authorizedFormalRows({ rows }),
      'rule_name',
      (row, value) => `${value} · ${row.rule_code || '编码未提供'}`,
    ),
  }),
  Object.freeze({
    field: 'version',
    label: '规则版本',
    filterType: 'select',
    placeholder: '选择实际版本',
    optionsSource: ({ rows }) => distinctOptions(
      authorizedFormalRows({ rows }),
      'version',
      (_row, value) => value,
    ),
  }),
  Object.freeze({
    field: 'status',
    label: '工程规则状态',
    filterType: 'select',
    placeholder: '选择规则状态',
    options: ENGINEERING_RULE_STATUS_OPTIONS,
    optionsSource: 'engineering-rule-status-contract',
  }),
])

export function engineeringRuleStatusLabel(status) {
  return ENGINEERING_RULE_STATUS_OPTIONS.find(option => option.value === status)?.label || status || '未提供'
}

export function canEditEngineeringRule(row, authorization = {}) {
  return row?.status === 'draft'
    && Boolean(authorization['production.engineering.rule.update_draft']?.allowed)
}

export function canTransitionEngineeringRule(row, authorization = {}) {
  return ['draft', 'reviewed', 'released'].includes(row?.status)
    && Boolean(authorization['production.engineering.rule.release']?.allowed)
}
