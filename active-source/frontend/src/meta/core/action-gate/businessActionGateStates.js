export const businessActionReviewStates = ['not_created', 'review_pending', 'review_passed', 'review_blocked', 'review_stale', 'review_failed']
export const businessActionReviewDecisions = ['approved', 'blocked', 'stale', 'failed']
export const businessActionConditionStatuses = ['passed', 'blocked', 'warning', 'not_applicable']
export const businessActionConditionCategories = [
  '前置检查点', '候选对象', '模拟请求', '模拟结果', '结果完整性', '来源新鲜度', '目标唯一性',
  '主体一致性', '金额和币种', '审计证据', '风险', '运行时保护', '零写入不变式',
]
