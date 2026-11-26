import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue')
const projection = read('backend/pde/calculation_batch_reuse.py')
const router = read('frontend/src/router/index.js')

test('恢复复用原正式页面与原路由而非创建第二页面', () => {
  assert.match(router, /path: 'pde\/engineering-calculations'/)
  assert.match(router, /PdeOrderEngineeringCalculationPage\.vue/)
  assert.match(page, /data-page-code="pde-order-engineering-calculation"/)
})

test('原施工单正式名称保持不变', () => {
  assert.match(page, /<h2>施工单／整单核算结果<\/h2>/)
})

test('结果页将订单行解析回唯一关联整单来源', () => {
  assert.match(page, /function linkedWholeOrderSummary\(orderNo\)/)
  assert.match(page, /matches\.length === 1 \? matches\[0\] : null/)
})

test('整单恢复只发生于结果页并保留工程录入行级语义', () => {
  assert.match(page, /activeBusinessPage\.value === 'results'/)
  assert.match(page, /page === 'results'/)
  assert.match(page, /销售订单第\$\{selectedOrder\.value\.lineNo\}行/)
})

test('结果页URL使用稳定sourceRecord而不是行级草稿', () => {
  assert.match(page, /locationContext\?\.isSourceTrial\) query\.sourceRecord/)
  assert.match(page, /query\.sourceRecord = String\(locationContext\.sourceRecordId\)/)
})

test('用户显式选择订单行时结果页立即提升为整单来源', () => {
  assert.match(page, /async function selectOrder\(\).*linkedWholeOrderSummary\(selectedOrder\.value\.orderNo\)/)
  assert.match(page, /if \(wholeOrder\) selection\.salesOrderItemId = wholeOrder\.salesOrderItemId/)
})

test('无上下文入口仍保持待选择且没有固定样例兜底', () => {
  assert.match(page, /selection\.salesOrderItemId = null/)
  assert.doesNotMatch(page, /SO202609180003/)
  assert.doesNotMatch(page, /stableDesignContext/)
  assert.doesNotMatch(page, /orders\.value\s*\[\s*0\s*\]/)
})

test('施工单行数只读取原activeDraft服务端投影', () => {
  assert.match(page, /const workOrderRows = computed\(\(\) => activeDraft\.value\?\.workOrderRows \|\| draftRows\.value\)/)
  assert.match(page, /:data-work-order-count="workOrderRows\.length"/)
})

test('服务端施工单复用产品设计事实且不持久化', () => {
  assert.match(projection, /def _work_order_rows\(source_rows, design_inputs\):/)
  assert.match(projection, /does not persist into the registered source draft/)
  assert.match(projection, /snapshot\['workOrderRows'\] = _work_order_rows/)
})

test('施工单投影保留订单项目空间安装位置和设计对象身份', () => {
  for (const field of ['orderNo', 'orderLineNo', 'projectReference', 'space', 'installationPosition', 'designItemNo']) {
    assert.match(projection, new RegExp(`'${field}':`), `missing ${field}`)
  }
})

test('施工单投影保留数量正式单位尺寸材料与规格', () => {
  for (const field of ['quantity', 'unitStatusLabel', 'dimensionSemantics', 'materialCode', 'materialName', 'specification']) {
    assert.match(projection, new RegExp(`'${field}':`), `missing ${field}`)
  }
})

test('施工单投影保留封边见光颜色工艺油漆和加工要求', () => {
  for (const field of ['edgeMode', 'visibleCondition', 'colorVersion', 'processConfigurationLabel', 'paintProcess', 'processingNote']) {
    assert.match(projection, new RegExp(`'${field}':`), `missing ${field}`)
  }
})

test('既有五金和玻璃要求进入只读施工单且不伪造层级', () => {
  assert.match(projection, /'hardware': design\.get\('hardware'\) or ''/)
  assert.match(projection, /'glass': design\.get\('glass'\) or ''/)
  assert.match(page, /五金／玻璃/)
  assert.doesNotMatch(page, /row\.hierarchy \|\|/)
})

test('施工单保持单一横向滚动拥有者和左侧固定业务身份', () => {
  assert.match(page, /data-scroll-owner="work-order-table"/)
  assert.match(page, /class="sticky-sequence">序号/)
  assert.match(page, /class="sticky-identity">订单／项目/)
  assert.match(page, /\.governed-scroll-table\{max-height:/)
})

test('车间施工单与工程管理388项结果明确分区', () => {
  assert.match(page, /车间施工单（整单只读投影）/)
  assert.match(page, /工程／管理整单核算结果/)
  assert.match(page, /data-section="source-engineering-results"/)
  assert.match(page, /sourceCalculationRows\.length/)
})

test('整单上下文服务显式报告零业务写入', () => {
  assert.match(projection, /'businessWriteSideEffectCount': 0/)
})
