const profile = (requiredRegions, overrides = {}) => Object.freeze({
  requiredRegions: Object.freeze(requiredRegions),
  requiredActions: Object.freeze(['refresh-page', 'copy-diagnostics', 'return-process-center']),
  requiredListCapabilities: Object.freeze([]),
  requiredDiagnosticCapabilities: Object.freeze(['完整URL', '版本', '当前状态来源', '数据保护声明']),
  ...overrides,
})

export const PCE_PAGE_TYPE_PROFILES = Object.freeze({
  list: profile([
    '页面框架标题区', '当前业务动作说明', '模块主流程', '业务流程导航', '页面动作栏',
    '业务摘要或容量', '标准工具栏', '正式列表', '后续边界', '下游零对象保护',
  ], {
    requiredListCapabilities: Object.freeze([
      '快速搜索', '高级筛选', '多选', '排序', '导出当前结果', '冻结列', '横向滚动',
    ]),
  }),
  detail: profile(['页面框架标题区', '来源', '当前状态', '业务字段', '规则和校验', '版本、幂等与审计', '后续边界', '诊断']),
  create: profile(['页面框架标题区', '来源与上下文', '可编辑业务字段', '预检查', '保存边界', '幂等与审计说明', '诊断']),
  edit: profile(['页面框架标题区', '来源与上下文', '可编辑业务字段', '预检查', '保存边界', '幂等与审计说明', '诊断']),
  approval: profile(['申请信息', '审批路线', '当前任务', '审批历史', '职责分离', '按钮权限', '下游资格']),
  plan: profile(['计划日期', '要求交期', '进度', '剩余时间', '逾期天数', '紧急程度', '颜色和文字警示', '风险排序', '图例']),
  preview: profile(['只读标识', '来源证据', '预览内容', '未生成正式对象声明', '零写入保护']),
  diagnostic: profile(['事实来源', '查询上下文', '当前状态', '校验与阻断', '幂等、编号、事务与审计', '数据保护说明']),
})

export const PCE_PAGE_TYPE_REQUIRED_REGIONS = Object.freeze(Object.fromEntries(
  Object.entries(PCE_PAGE_TYPE_PROFILES).map(([pageType, value]) => [pageType, value.requiredRegions]),
))

export const pcePageTypeProfiles = PCE_PAGE_TYPE_PROFILES
