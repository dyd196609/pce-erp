import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const frontendRoot = path.resolve(import.meta.dirname, '..', '..')
const repositoryRoot = path.resolve(frontendRoot, '..')
const read = file => fs.readFileSync(file, 'utf8')

test('sales order page exposes distinct delivery semantics and all-line planning handoff', () => {
  const page = read(path.join(frontendRoot, 'src', 'meta', 'pages', 'SalesOrderPage.vue'))
  for (const marker of ['客户要求交期', '企业承诺交期', '计划完成时间', '实际交付时间', '净需求待计划', '库存计算快照（未分配）', '订单未覆盖', '打开订单计划工作台', '未取得订单数据', '超计划', '超交付']) {
    assert.match(page, new RegExp(marker))
  }
  assert.match(page, /data-fact-load-status/)
  assert.match(page, /当前未登录或会话已失效/)
  assert.match(page, /associationIssues/)
  assert.match(page, /unmatchedBatches/)
  assert.match(page, /detailOrder\.deliveryFacts\?\.batches/)
  assert.match(page, /detailOrder\.planningChain\?\.lines/)
})

test('server projection iterates every item and keeps delivery batches tied to stable order-line identity', () => {
  const views = read(path.join(repositoryRoot, 'backend', 'sales', 'views.py'))
  assert.match(views, /for value in items:/)
  assert.match(views, /"salesOrderItemId": item\.pk/)
  assert.match(views, /"pendingPlanQty"/)
  assert.match(views, /"inventoryAllocationStatus"/)
  assert.match(views, /"uncoveredDemandQty"/)
  assert.match(views, /"associationConflictCount"/)
  assert.match(views, /"overDeliveredQty"/)
  assert.match(views, /successful_fact_load_facts/)
  assert.match(views, /"deliveryFacts": delivery/)
})

test('planning page keeps order trace filter and does not label missing prediction as a date', () => {
  const page = read(path.join(frontendRoot, 'src', 'meta', 'pages', 'PlanningCenterPage.vue'))
  assert.match(page, /item\.salesOrderNo === route\.query\.orderNo/)
  assert.match(page, /尚无法预测/)
  assert.match(page, /pendingNetPlanQty/)
  assert.match(page, /orderPlanningSchema/)
  assert.match(page, /未部署/)
  assert.match(page, /未取得计划数据/)
  assert.match(page, /planningQuantityStatus/)
  assert.match(page, /data-fact-load-status/)
})
