import assert from 'node:assert/strict'
import {
  REVIEW_LOAD_STATES,
  classifyOrderReviewFailure,
  reviewLoadPresentation,
  validateOrderReviewFacts,
} from './orderReviewLoadState.js'

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'AUTHENTICATION_FAILED', message: '数据库运行上下文已变化，请重新登录。' },
  meta: { status: 401 },
}).state, REVIEW_LOAD_STATES.UNAUTHENTICATED)

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'VIEW_PERMISSION_DENIED', message: '当前角色未获得该业务动作权限。' },
  meta: { status: 403 },
}).state, REVIEW_LOAD_STATES.FORBIDDEN)

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'REVIEW_OBJECT_ACCESS_REQUIRED', message: '已具备模块查看资格，但尚未分配当前评审。' },
  meta: { status: 403 },
}).state, REVIEW_LOAD_STATES.ASSIGNMENT_REQUIRED)

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'REVIEW_SCOPE_DENIED', message: '公司或数据范围不匹配。' },
  meta: { status: 403 },
}).state, REVIEW_LOAD_STATES.SCOPE_DENIED)

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'ECONNABORTED', message: 'timeout of 15000ms exceeded' },
}).state, REVIEW_LOAD_STATES.TIMEOUT)

assert.equal(classifyOrderReviewFailure({
  success: false,
  error: { code: 'REVIEW_OBJECT_REQUIRED', message: '请选择评审对象。' },
}).state, REVIEW_LOAD_STATES.OBJECT_REQUIRED)

assert.match(reviewLoadPresentation(REVIEW_LOAD_STATES.LOADING).description, /项目数量.*“—”/)
assert.match(reviewLoadPresentation(REVIEW_LOAD_STATES.UNAUTHENTICATED, '请重新登录。').title, /登录状态已失效/)
assert.match(validateOrderReviewFacts(null), /未返回/)
assert.match(validateOrderReviewFacts({ source: {}, orderContext: {}, review: { template: {}, templateItems: [] } }), /没有可用项目/)
assert.equal(validateOrderReviewFacts({ source: {}, orderContext: {}, review: { template: { version: 'V1' }, templateItems: [{}] } }), '')

console.log('orderReviewLoadState: 11 assertions passed')
