// Separate native server action contract. Legacy preview state transitions remain untouched.
export const NATIVE_QUOTE_ACTIONS = Object.freeze({
  register: Object.freeze({ actionCode: 'SAVE_QUOTE_COMPARISON', moduleCode: 'SCM',
    actionName: '登记报价比较并生成待核价准备', requiredPermission: 'procurement.quote_comparison.register',
    role: 'buyer', organizationScope: 'server-original-buyer-assignment',
    serverValidator: '/api/procurement/quote-comparisons/register/',
    allowed: context => context?.canRegister === true }),
  preparation: Object.freeze({ actionCode: 'OPEN_PRICE_APPROVAL_PREPARATION',
    actionName: '进入核价准备', nextRoute: '/scm/price-approval' }),
  comparison: Object.freeze({ actionCode: 'OPEN_QUOTE_COMPARISON_WORKBENCH',
    actionName: '返回报价比较', nextRoute: '/scm/quote-comparisons' }),
})
export const NATIVE_QUOTE_VIEW_ACTIONS = Object.freeze([
  Object.freeze({ actionCode: 'VIEW_NATIVE_QUOTE_SOURCE', actionName: '查看来源及版本', allowedStates: ['*'] }),
])
