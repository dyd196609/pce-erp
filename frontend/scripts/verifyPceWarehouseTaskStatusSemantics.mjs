import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const page = read('src/meta/pages/WmsPage.vue')
const store = read('src/meta/wms/wmsStore.js')
const spec = read('tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

assert(page.includes("done: '已完成'"), 'done通用中文映射必须保持已完成')
assert(!page.includes("done: '已入库'"), '禁止将done全局映射为已入库')
assert(store.includes("businessStatus: getWarehouseTaskBusinessType(task) === 'qualifiedInboundPrepare' ? '已入库' : task.businessStatus"), '合格入库任务缺少真实业务状态写入')
assert(page.includes("status: 'warehouse-task-detail-status'"), '任务状态唯一字段缺失')
assert(page.includes("businessStatus: 'warehouse-task-detail-business-status'"), '业务状态唯一字段缺失')
assert(spec.includes("getWarehouseTaskStatusField(page)).toHaveText('已完成')"), '测试缺少通用状态断言')
assert(spec.includes("getWarehouseTaskBusinessStatusField(page)).toHaveText('已入库')"), '测试缺少业务状态断言')
for (const evidence of [
  'expect(after.task.status).toBe(\'done\')',
  'expect(after.task.completedQuantity).toBe(1)',
  'expect(after.balances[0].quantity).toBe(1)',
  'expect(after.transactions).toHaveLength(1)',
  "expect(after.inspection.status).toBe('inventoryPosted')",
  'expect(after.purchaseReceive.inventoryPosted).toBe(true)',
]) assert(spec.includes(evidence), `业务状态缺少真实证据断言：${evidence}`)

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.30',
  gate: 'warehouse_task_status_semantics',
  genericStatus: { raw: 'done', text: '已完成' },
  qualifiedInboundBusinessStatus: { field: 'businessStatus', text: '已入库' },
  distinctDomFields: true,
  inventoryEvidenceRequired: true,
  overall: 'passed',
}, null, 2))
