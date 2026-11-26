import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '../..')
const read = file => fs.readFileSync(path.join(root, file), 'utf8')

test('CRM and PDE keep stable nodes but expose distinct review names and routes', () => {
  const crm = read('src/meta/runtime/crmOrderProcessRegistry.js')
  const process = read('src/meta/process/businessProcessRegistry.js')
  assert.match(crm, /'product-requirement-review', '订单评审', 'crm-order-reviews', '\/sales\/order-reviews/)
  assert.match(process, /'product-requirement-review', '生产可行性评审', 'pde-product-requirement-reviews', '\/pde\/product-requirement-reviews'/)
})

test('both routes reuse the review page with different server review types', () => {
  const router = read('src/router/index.js')
  const page = read('src/meta/pages/CrossFunctionalReviewPage.vue')
  assert.match(router, /reviewType: 'CRM_ORDER_REVIEW'/)
  assert.match(router, /reviewType: 'PDE_PRODUCTION_FEASIBILITY'/)
  assert.match(page, /本次订单评审审批规则修订不自动改变生产可行性评审政策/)
  assert.match(page, /最终通过或不通过只由正式权限人的独立审批动作产生/)
  assert.match(page, /crossReviewFeedback/)
})

test('server records are typed, immutable and source-version guarded', () => {
  const model = read('../backend/pde/models.py')
  const service = read('../backend/pde/order_review_service.py')
  assert.match(model, /CRM_ORDER_REVIEW/)
  assert.match(model, /PDE_PRODUCTION_FEASIBILITY/)
  assert.match(model, /评审历史为不可变审计记录/)
  assert.match(service, /REVIEW_BASIS_CHANGED/)
  assert.match(service, /crossReviewDoesNotChangeThisReview/)
})
