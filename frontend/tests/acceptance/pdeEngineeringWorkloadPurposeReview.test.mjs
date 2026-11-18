import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

const componentPath = new URL('../../src/meta/pages/components/EngineeringWorkloadPurposeReview.vue', import.meta.url)
const source = fs.readFileSync(componentPath, 'utf8')
const page = fs.readFileSync(new URL('../../src/meta/pages/PdeOrderEngineeringCalculationPage.vue', import.meta.url), 'utf8')
const descriptor = parse(source, { filename: componentPath.pathname }).descriptor
const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const execute = new Function('computed', 'reactive', 'defineProps', 'defineEmits', 'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime',
  `${script}\nreturn { review, readFailure, groupRows, loadRows, historyRows, lists, value, reasonLabel, sourceObjectName }`)
function runtime(facts) {
  const props = Vue.reactive({ facts })
  return { props, ...execute(Vue.computed, Vue.reactive, () => props, () => {}, createPceEnterpriseListContract, usePceEnterpriseListRuntime) }
}
const serverFacts = (extra = {}) => ({ contractVersion: 'PCE-ENGINEERING-WORKLOAD-PURPOSE-REVIEW-V1', factSource: 'server',
  readStatus: 'loaded', statusLabel: '只读评审', planningAccess: { allowed: true, statusLabel: '计划查看已授权' },
  groups: [], operationLoads: [], historyRequirements: [], ...extra })
async function cellHtml(name, row, review = serverFacts(), extra = {}) {
  const cell = source.match(new RegExp(`<div(?: v-if="[^"]+")? data-cell="${name}">([\\s\\S]*?)<\\/div>`))
  assert.ok(cell, `production ${name} cell must exist`)
  const render = new Function('Vue', compile(cell[0], { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const before = JSON.stringify({ row, review })
  const { value, reasonLabel, readFailure, sourceObjectName } = runtime(review)
  const html = await renderToString(Vue.createSSRApp({ data: () => ({ row, review, value, reasonLabel, sourceObjectName, readFailure: readFailure.value, ...extra }), render }))
  assert.equal(JSON.stringify({ row, review }), before, 'read-only rendering must preserve authoritative facts')
  return html
}

test('原页面与新增局部组件可编译，现有汇总入口及原来源列表保持', () => {
  for (const [filename, content] of [['EngineeringWorkloadPurposeReview.vue', source], ['PdeOrderEngineeringCalculationPage.vue', page]]) {
    const parsed = parse(content, { filename })
    assert.deepEqual(parsed.errors, [])
    const scriptResult = compileScript(parsed.descriptor, { id: filename })
    const compiled = compileTemplate({ source: parsed.descriptor.template.content, filename, id: filename,
      compilerOptions: { bindingMetadata: scriptResult.bindings } })
    assert.deepEqual(compiled.errors, [])
  }
  assert.match(page, /<EngineeringWorkloadPurposeReview :facts="engineeringWorkloadSummary\.purposeReview"/)
  for (const existing of ['来源工程事实与预览', '已保存工程事实与工序需求关联', 'engineeringWorkloadLoadedScope', 'includeWorkloadSummary: activeBusinessPage.value === \'scheduling\'']) assert.ok(page.includes(existing))
  assert.doesNotMatch(source, /pdeApi|axios|fetch\(|localStorage|router\.push/)
})

test('用途投影严格接受完整服务端当前合同，未知不伪装为有效空结果', () => {
  const facts = serverFacts()
  const r = runtime(facts)
  assert.equal(Vue.toRaw(r.review.value), facts)
  for (const replacement of [null, { ...facts, factSource: 'client' }, { ...facts, readStatus: 'read_failed' },
    { ...facts, contractVersion: 'INVALID' }, { ...facts, groups: null }, { ...facts, operationLoads: null }, { ...facts, historyRequirements: null }]) {
    r.props.facts = replacement
    assert.equal(r.review.value, null)
  }
  assert.match(source, /v-if="!review"[\s\S]*候选量、计划量和负荷未知，未补为零/)
})

test('同用途不同版本、单位及相同值均保持服务端独立分组，历史不混入有效负荷', () => {
  const groups = [{ key: 'A', purposeLabel: '来源物理量', dimensions: { routingCode: 'SIM', routingVersionLabel: 'Version43', uomLabel: '扇' }, engineeringCandidate: { quantity: '5' } },
    { key: 'B', purposeLabel: '来源物理量', dimensions: { routingCode: 'SIM', routingVersionLabel: 'Version31', uomLabel: '套' }, engineeringCandidate: { quantity: '3' } },
    { key: 'C', purposeLabel: '开料面积', engineeringCandidate: { quantity: '1.939650' } },
    { key: 'D', purposeLabel: '油漆来源面积', engineeringCandidate: { quantity: '1.939650' } }]
  const operationLoads = [{ key: 'effective', effectiveQuantity: '1.939650', requirementIds: [1243, 1244, 1245] }]
  const historyRequirements = [{ key: 'history', id: 378, statusLabel: '已替代' }]
  const facts = serverFacts({ groups, operationLoads, historyRequirements })
  const before = JSON.stringify(facts)
  const r = runtime(facts)
  assert.equal(Vue.toRaw(r.groupRows.value), groups)
  assert.equal(Vue.toRaw(r.loadRows.value), operationLoads)
  assert.equal(Vue.toRaw(r.historyRows.value), historyRequirements)
  assert.equal(r.lists[0].runtime.filteredRows.length, 4)
  r.lists[0].runtime.updateFilter('routingVersionLabel', 'Version31')
  assert.deepEqual(r.lists[0].runtime.filteredRows.map(row => row.key), ['B'])
  r.lists[0].runtime.clearFilters()
  r.lists[0].runtime.quickSearch = '油漆'
  r.lists[0].runtime.applySearch()
  assert.deepEqual(r.lists[0].runtime.filteredRows.map(row => row.key), ['D'])
  assert.equal(JSON.stringify(facts), before)
})

test('服务端用途读取失败保留中文原因，数量保持未知且不恢复旧行', async () => {
  const failed = serverFacts({ readStatus: 'read_failed', statusLabel: '用途评审读取失败', missingReasons: [{ statusLabel: '正式来源证明读取失败，范围未改变' }] })
  const r = runtime(failed)
  assert.equal(r.review.value, null)
  assert.equal(Vue.toRaw(r.readFailure.value), failed)
  assert.deepEqual(r.groupRows.value, [])
  const html = await cellHtml('purpose-read-failure', {}, failed)
  assert.match(html, /用途评审读取失败/)
  assert.match(html, /正式来源证明读取失败，范围未改变/)
  assert.doesNotMatch(html, />0 /)
})

test('真实单元格区分未知与正式零值，并保持套数和面积各自单位', async () => {
  const unknown = await cellHtml('engineering-candidate', { engineeringCandidate: { quantity: null, uomLabel: '平方米', statusLabel: '对应数量未知' } })
  assert.match(unknown, /未知.*平方米/)
  assert.doesNotMatch(unknown, />0 /)
  const zero = await cellHtml('engineering-candidate', { engineeringCandidate: { quantity: '0.000000', uomLabel: '套', statusLabel: '正式零量' } })
  assert.match(zero, /0\.000000 套/)
  const plan = await cellHtml('confirmed-plan', { confirmedPlan: { quantity: '3.000000', uomLabel: '套', scopeLabel: '第2行确认计划', statusLabel: '已确认', sourceLabel: '正式计划数量服务' } })
  assert.match(plan, /3\.000000 套/)
  assert.match(plan, /第2行确认计划/)
  assert.doesNotMatch(plan, /平方米/)
})

test('计划查看权限受限明确显示服务端原因，不泄露数量或伪造零', async () => {
  const restricted = serverFacts({ planningAccess: { allowed: false, statusLabel: '缺少既有计划查看权限' } })
  const row = { key: 'restricted', confirmedPlan: { quantity: '3.000000', uomLabel: '套', statusLabel: '计划查看受限', plans: [{ id: 2, planNo: 'SIM-PRIVATE', quantity: '3.000000', uomLabel: '套' }] }, comparison: { allowed: true, difference: '3.000000' } }
  const html = await cellHtml('confirmed-plan', row, restricted)
  assert.match(html, /缺少既有计划查看权限/)
  assert.doesNotMatch(html, /3\.000000|>0 /)
  assert.doesNotMatch(await cellHtml('plan-trace', row, restricted), /SIM-PRIVATE|3\.000000/)
  assert.doesNotMatch(await cellHtml('quantity-comparison', row, restricted), /差额|3\.000000/)
  const priorDocument = globalThis.document, priorWindow = globalThis.window
  globalThis.document = { createElement: () => ({ click() {}, remove() {} }), body: { appendChild() {} } }
  globalThis.window = { setTimeout: callback => callback() }
  try {
    const r = runtime({ ...restricted, groups: [row] })
    const exported = r.lists[0].runtime.exportCurrent()
    assert.match(exported.csv, /缺少既有计划查看权限/)
    assert.doesNotMatch(exported.csv, /3\.000000|SIM-PRIVATE/)
  } finally {
    if (priorDocument === undefined) delete globalThis.document; else globalThis.document = priorDocument
    if (priorWindow === undefined) delete globalThis.window; else globalThis.window = priorWindow
  }
})

test('正式来源物理量保留，但缺用途映射时不冒充工程候选量', async () => {
  const row = { engineeringCandidate: { quantity: null, sourceQuantity: '3', sourceQuantityLabel: '正式来源物理量', uomLabel: '套', statusLabel: '生产用途、生产组及模式尚未证明，候选量未知' } }
  const html = await cellHtml('engineering-candidate', row)
  assert.match(html, /未知 套/)
  assert.match(html, /正式来源物理量 3 套/)
  assert.match(html, /候选量未知/)
  const known = await cellHtml('engineering-candidate', { engineeringCandidate: { quantity: '1.939650', sourceQuantity: '1.939650', uomLabel: '平方米', statusLabel: '正式油漆来源面积' } })
  assert.match(known, /1\.939650 平方米/)
  assert.doesNotMatch(known, /正式来源量/)
})

test('只有服务端证明同口径可比时才显示服务端差额', async () => {
  const incompatible = await cellHtml('quantity-comparison', { comparison: { allowed: false, difference: '999', statusLabel: '计划套数不能换算油漆面积' } })
  assert.match(incompatible, /计划套数不能换算油漆面积/)
  assert.doesNotMatch(incompatible, /999|差额/)
  const comparable = await cellHtml('quantity-comparison', { comparison: { allowed: true, difference: '0.000000', statusLabel: '同范围同单位' }, dimensions: { uomLabel: '套' } })
  assert.match(comparable, /差额 0\.000000 套/)
})

test('有效与历史贡献分别显示对象、Fact生产规则及EOR自身原规则', async () => {
  const base = { orderNo: 'SIM-ORDER', lineNo: 2, designItemId: 6, baselineItemId: 77, originCalculationId: 4, sourceCalculationId: 392, sourceFactId: 424, ruleCode: 'PAINTING-PROCESS-VISIBLE-AREA', ruleVersion: 2, quantity: '0.856800', uomLabel: '平方米' }
  const effective = { ...base, operationRequirementId: 1243, operationRuleCode: 'SIM-PAINTING-LOAD', operationRuleVersion: 3, statusLabel: '有效需求来源贡献' }
  const historical = { ...base, operationRequirementId: 378, operationRuleCode: 'SIM-PAINTING-LOAD', operationRuleVersion: 2, statusLabel: '历史替代需求，仅供追溯' }
  for (const contribution of [effective, historical]) {
    const before = JSON.stringify(contribution)
    const html = await cellHtml('contribution-trace', {}, serverFacts(), { source: contribution })
    assert.match(html, /对象 6；基线对象 77/)
    assert.match(html, /主核算 4；来源核算 392；事实 424/)
    assert.match(html, /规则 PAINTING-PROCESS-VISIBLE-AREA · 版本 2/)
    assert.ok(html.includes(`工序需求 ${contribution.operationRequirementId}；工序规则 SIM-PAINTING-LOAD · 版本 ${contribution.operationRuleVersion}`))
    assert.ok(html.includes(contribution.statusLabel))
    assert.equal(JSON.stringify(contribution), before)
  }
})

test('固定来源详情直接呈现窄面板所需双列、逐工序及历史字段，并保持计划权限守卫', async () => {
  const dimensions = { routingCode: 'QSFB/FM', routingVersionLabel: 'Version31', manufacturingModeLabel: '制造模式未证明', productionGroupLabel: '生产组未证明', sourceScopeLabel: '第2行／基线2' }
  const row = { purposeLabel: '正式来源物理数量', dimensions,
    engineeringCandidate: { quantity: null, sourceQuantity: '3', sourceQuantityLabel: '正式来源物理量', uomLabel: '套', statusLabel: '候选量未知' },
    confirmedPlan: { quantity: '3.000000', uomLabel: '套', statusLabel: '已确认', scopeLabel: '第2行确认计划', sourceLabel: '正式计划数量服务' } }
  const groups = await cellHtml('compact-review', row, serverFacts(), { list: { kind: 'groups' } })
  assert.match(groups, /工程投产候选量：<\/b>未知 套/)
  assert.match(groups, /正式来源物理量：3 套/)
  assert.match(groups, /已确认计划投产量：[\s\S]*3\.000000 套/)
  for (const text of ['QSFB/FM', 'Version31', '制造模式未证明', '生产组未证明', '第2行／基线2', '正式计划数量服务']) assert.ok(groups.includes(text))
  const load = { dimensions, operationName: '油漆工序', stepSequence: 13, workCenterLabel: '油漆工作中心', effectiveQuantity: '1.939650', uomLabel: '平方米', allocatedQuantity: null, allocationStatusLabel: '未分配', capacity: { quantity: '200', uomLabel: '平方米', timeBasisLabel: '天', theoreticalResourceDaysLabel: '0.00969825 资源天', statusLabel: '正式匹配', capacityScopeLabel: '既有正式产能', applicabilityPeriodLabel: '当前有效', admissionStatusLabel: '仅供理论评审' } }
  const loads = await cellHtml('compact-review', load, serverFacts(), { list: { kind: 'operationLoads' } })
  for (const text of ['步骤 13', '有效工序需求量：</b>1.939650 平方米', '已分配计划负荷', '未分配', '200 平方米 / 天', '0.00969825 资源天', '油漆工作中心', '当前有效']) assert.ok(loads.includes(text))
  const restricted = serverFacts({ planningAccess: { allowed: false, statusLabel: '计划读取受限' } })
  assert.doesNotMatch(await cellHtml('compact-review', { ...row, confirmedPlan: { ...row.confirmedPlan, quantity: '999.123456' } }, restricted, { list: { kind: 'groups' } }), /999\.123456/)
  const deniedLoad = await cellHtml('compact-review', { ...load, allocatedQuantity: '999.123456' }, restricted, { list: { kind: 'operationLoads' } })
  assert.match(deniedLoad, /计划读取受限/)
  assert.doesNotMatch(deniedLoad, /999\.123456/)
  const historical = await cellHtml('compact-review', { id: 378, supersededById: 1243, operationName: '历史油漆工序', workloadQuantity: '0.856800', uomLabel: '平方米', statusLabel: '历史替代，仅追溯', dimensions }, serverFacts(), { list: { kind: 'historyRequirements' } })
  for (const text of ['历史需求 378', '0.856800 平方米', '1243', '历史替代，仅追溯']) assert.ok(historical.includes(text))
  assert.match(source, /<summary>\{\{ value\(row\.purposeLabel/)
})

test('无保存分配与对应数量未知分别显示，标准产能和资源天不前端重算', async () => {
  const unallocated = await cellHtml('allocated-load', { allocatedQuantity: null, uomLabel: '平方米', allocationStatusLabel: '未分配' })
  assert.match(unallocated, /未知 平方米/)
  assert.match(unallocated, /未分配/)
  assert.doesNotMatch(unallocated, />0 /)
  const mappedUnknown = await cellHtml('allocated-load', { allocatedQuantity: null, uomLabel: '平方米', allocationStatusLabel: '对应数量未知' })
  assert.match(mappedUnknown, /对应数量未知/)
  const days = await cellHtml('theoretical-days', { capacity: { theoreticalResourceDaysLabel: '5/12 资源天', admissionStatusLabel: '理论量，不生成日期' } })
  assert.match(days, /5\/12 资源天/)
  const capacity = await cellHtml('matched-capacity', { capacity: { quantity: '12', uomLabel: '套', timeBasisLabel: '天', statusLabel: '单位匹配', capacityScopeLabel: '仅限工程需求，不可作为APS可用产能' } })
  assert.match(capacity, /12 套 \/ 天/)
  assert.match(capacity, /仅限工程需求，不可作为APS可用产能/)
  assert.doesNotMatch(script, /parseFloat|parseInt|Number\(|\.reduce\(|Math\./)
})

test('列表沿用企业表格过滤与滚动所有权，只有只读刷新和来源展开', () => {
  assert.match(source, /PceEnterpriseListTable/)
  assert.match(source, /createPceEnterpriseListContract/)
  assert.match(source, /usePceEnterpriseListRuntime/)
  assert.match(source, /filterType: 'select', optionsProvider:/)
  assert.match(source, /历史数量不进入当前候选量、有效工序负荷或待分配输入/)
  assert.match(source, /来源与准入依据/)
  assert.match(source, /source\.originCalculationId[\s\S]*source\.sourceCalculationId[\s\S]*source\.sourceFactId/)
  assert.doesNotMatch(source, /<table|overflow-x\s*:\s*(auto|scroll)|<el-select|<el-input/)
})
