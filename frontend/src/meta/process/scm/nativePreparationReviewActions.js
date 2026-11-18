export const PREPARATION_REVIEW_ACTIONS = Object.freeze(Object.fromEntries([
  ['START_REVIEW', '进入核价准备审核'],
  ['SUBMIT_REVIEW', '提交核价审核结论'],
  ['REOPEN_REVIEW', '调整后重新核价'],
].map(([actionCode, actionName]) => [actionCode, Object.freeze({
  actionCode, actionName, moduleCode: 'SCM',
  requiredPermission: 'procurement.price_approval_preparation.review',
  role: 'purchase_manager', organizationScope: 'server-original-role-scope',
  serverValidator: '/api/procurement/price-approval-preparations/{preparationId}/transition/',
  allowed: context => Array.isArray(context?.availableActions) && context.availableActions.includes(actionCode),
})])))
export const PREPARATION_REVIEW_RESULTS = Object.freeze([
  { value: 'pass', label: '通过' }, { value: 'reject', label: '不同意' },
  { value: 'adjust', label: '调整后重新核价' },
])
