import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { baseParse, compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

// These fixtures are synthetic display inputs. No HTTP, database, browser or allocation service is invoked.
const componentPath = new URL('../../src/meta/pages/components/EngineeringWorkloadPurposeReview.vue', import.meta.url)
const source = fs.readFileSync(componentPath, 'utf8')
const parentSource = fs.readFileSync(new URL('../../src/meta/pages/PdeOrderEngineeringCalculationPage.vue', import.meta.url), 'utf8')
const descriptor = parse(source, { filename: componentPath.pathname }).descriptor
const compiledScript = compileScript(descriptor, { id: 'saved-load-visibility' })
const productionScript = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const excluded = new Set(['computed', 'reactive', 'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime', 'PceEnterpriseListTable', 'PceBusinessStatus', 'facts', 'refreshing', 'designItems'])
const bindings = Object.keys(compiledScript.bindings).filter(name => !excluded.has(name) && compiledScript.bindings[name] !== 'props')
const execute = new Function('computed', 'reactive', 'defineProps', 'defineEmits', 'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime',
  `${productionScript}\nreturn { ${bindings.join(', ')} }`)
const ast = baseParse(descriptor.template.content)
const statusDescriptor = parse(fs.readFileSync(new URL('../../src/meta/components/PceBusinessStatus.vue', import.meta.url), 'utf8')).descriptor
const statusScript = statusDescriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const statusSetup = new Function('computed', 'defineProps', `${statusScript}\nreturn { visibleLabel, resolvedTitle }`)
const statusRender = new Function('Vue', compile(statusDescriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
const ProductionBusinessStatus = {
  props: ['statusLabel', 'statusCode', 'source'],
  setup: props => statusSetup(Vue.computed, () => props),
  render: statusRender,
}

function findCell(name, root = ast, ancestors = []) {
  if (root.type === 1 && root.props.some(prop => prop.type === 6 && prop.name === 'data-cell' && prop.value?.content === name)) return { node: root, ancestors }
  for (const child of root.children || []) {
    const found = findCell(name, child, [...ancestors, root])
    if (found) return found
  }
  return null
}

const serverFacts = (extra = {}) => ({ contractVersion: 'PCE-ENGINEERING-WORKLOAD-PURPOSE-REVIEW-V1', factSource: 'server', readStatus: 'loaded',
  statusLabel: '只读评审', planningAccess: { allowed: true, statusLabel: '既有计划查看已授权' }, groups: [], operationLoads: [], historyRequirements: [], ...extra })
const load = (extra = {}) => ({ key: 'SIM-STEP-13', purposeLabel: '油漆来源候选面积', stepSequence: 13, operationName: '白胚/打磨',
  effectiveQuantity: '1.939650', allocatedQuantity: '1.939650', uomLabel: '平方米', allocationStatusLabel: '已保存且通过原服务校验的计划负荷',
  contributions: [], ...extra })
function runtime(facts, extraProps = {}) {
  const props = Vue.reactive({ facts, refreshing: false, sourceObjects: [], sourceSalesOrderItemId: null, ...extraProps })
  return { props, ...execute(Vue.computed, Vue.reactive, () => props, () => {}, createPceEnterpriseListContract, usePceEnterpriseListRuntime) }
}
async function renderCell(name, row, facts = serverFacts(), extra = {}, extraProps = {}) {
  const found = findCell(name)
  assert.ok(found, `actual production ${name} cell exists`)
  const render = new Function('Vue', compile(found.node.loc.source, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const state = runtime(facts, extraProps)
  const values = Object.fromEntries(Object.entries(state).map(([key, value]) => [key, Vue.isRef(value) ? value.value : value]))
  const before = JSON.stringify({ row, facts, extraProps })
  const app = Vue.createSSRApp({ data: () => ({ ...values, row, list: { kind: 'operationLoads' }, ...extra }), render })
  app.component('PceBusinessStatus', ProductionBusinessStatus)
  const html = await renderToString(app)
  assert.equal(JSON.stringify({ row, facts, extraProps }), before, 'rendering preserves authoritative inputs')
  return { html, text: html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() }
}

test('the actual component compiles and puts load acceptance content outside collapsed trace', () => {
  const result = compileTemplate({ source: descriptor.template.content, filename: componentPath.pathname, id: 'saved-load-visibility',
    compilerOptions: { bindingMetadata: compiledScript.bindings } })
  assert.deepEqual(result.errors, [])
  const overview = findCell('operation-load-overview')
  assert.ok(overview)
  assert.ok(!overview.ancestors.some(node => node.tag === 'details'), 'critical load content must not require expanding trace')
  assert.ok(overview.ancestors.some(node => node.tag === 'template' && node.props.some(prop => prop.type === 7 && prop.name === 'slot' && prop.arg?.content === 'actions')),
    'critical content is in the original fixed action column')
})

test('direct operation content distinguishes effective demand from saved allocated load and keeps server status', async () => {
  const { text } = await renderCell('operation-load-overview', load({ effectiveQuantity: '2.000000', allocatedQuantity: '1.939650' }))
  assert.match(text, /白胚\/打磨/)
  assert.match(text, /有效工序需求量\s*[：:]?\s*2\.000000\s*平方米/)
  assert.match(text, /已分配计划负荷\s*[：:]?\s*1\.939650\s*平方米/)
  assert.match(text, /已保存且通过原服务校验的计划负荷/)
  assert.doesNotMatch(text, /3\s*套|25\.21545/)
})

test('unallocated cutting and unknown mapping remain distinct from a formal zero', async () => {
  const unallocated = await renderCell('operation-load-overview', load({ operationName: '开料', allocatedQuantity: null, allocationStatusLabel: '未分配' }))
  assert.match(unallocated.text, /开料/)
  assert.match(unallocated.text, /未分配/)
  assert.match(unallocated.text, /已分配计划负荷\s*[：:]?\s*未知\s*平方米/)
  assert.doesNotMatch(unallocated.text, /已保存且通过/)
  const unknown = await renderCell('operation-load-overview', load({ allocatedQuantity: null, allocationStatusLabel: '对应数量未知' }))
  assert.match(unknown.text, /对应数量未知/)
  assert.doesNotMatch(unknown.text, /已分配计划负荷\s*[：:]?\s*0/)
  const zero = await renderCell('operation-load-overview', load({ allocatedQuantity: '0.000000', allocationStatusLabel: '正式零量' }))
  assert.match(zero.text, /已分配计划负荷\s*[：:]?\s*0\.000000\s*平方米/)
})

test('direct load content keeps original plan-view permission and does not expose restricted allocated quantity', async () => {
  const restricted = serverFacts({ planningAccess: { allowed: false, statusLabel: '缺少既有计划查看权限' } })
  const { text } = await renderCell('operation-load-overview', load({ allocatedQuantity: '987.654321' }), restricted)
  assert.match(text, /缺少既有计划查看权限/)
  assert.doesNotMatch(text, /987\.654321/)
  assert.match(text, /有效工序需求量\s*[：:]?\s*1\.939650\s*平方米/)
})

test('the original operation region explains native plan units and unknown plan area without recasting saved load', async () => {
  const groups = [
    { key: 'SIM-PHYSICAL', purposeCode: 'PHYSICAL_SOURCE', confirmedPlan: { quantity: '3.000000', uomLabel: '套', scopeLabel: 'SIM-第2行确认计划' } },
    { key: 'SIM-PAINT', purposeCode: 'PAINTING', confirmedPlan: { quantity: null, uomLabel: '平方米' }, missingReasons: [{ code: 'PLAN_PURPOSE_QUANTITY_UNKNOWN' }] },
  ]
  const { text } = await renderCell('plan-load-explanation', {}, serverFacts({ groups }))
  assert.match(text, /计划源数量\s*[：:]\s*3\.000000 套/)
  assert.match(text, /不直接换算/)
  assert.match(text, /不累加为产品投产量/)
  assert.match(text, /油漆计划对应面积未知/)
  assert.match(text, /不表示已保存的工序分配失败/)
  const noAreaReason = await renderCell('plan-load-explanation', {}, serverFacts({ groups: [groups[0]] }))
  assert.doesNotMatch(noAreaReason.text, /油漆计划对应面积未知/)
  const denied = await renderCell('plan-load-explanation', {}, serverFacts({ groups,
    planningAccess: { allowed: false, statusLabel: '缺少既有计划查看权限' } }))
  assert.match(denied.text, /缺少既有计划查看权限/)
  assert.doesNotMatch(denied.text, /3\.000000|油漆计划对应面积未知/)
})

test('replacing the current formal projection replaces all direct rows and excludes history', () => {
  const first = serverFacts({ operationLoads: [load()], historyRequirements: [{ id: 'SIM-HISTORY', quantity: '999.000000' }] })
  const r = runtime(first)
  assert.deepEqual(r.loadRows.value.map(row => row.key), ['SIM-STEP-13'])
  const second = serverFacts({ operationLoads: [load({ key: 'SIM-OTHER-SOURCE', operationName: '组装', uomLabel: '套' })] })
  r.props.facts = second
  assert.deepEqual(r.loadRows.value.map(row => row.key), ['SIM-OTHER-SOURCE'])
  assert.ok(!r.loadRows.value.some(row => row.id === 'SIM-HISTORY'))
  r.props.facts = serverFacts({ readStatus: 'read_failed' })
  assert.equal(r.review.value, null)
  assert.deepEqual(r.loadRows.value, [])
})

test('expanded contribution uses only a unique current-scope formal object name and preserves each native quantity', async () => {
  const sourceObjects = [
    { salesOrderItemId: 4, designItemId: 8, itemName: 'SIM-房门甲' },
    { salesOrderItemId: 4, designItemId: 6, itemName: 'SIM-房门乙' },
    { salesOrderItemId: 4, designItemId: 7, itemName: 'SIM-房门丙' },
  ]
  for (const [designItemId, quantity, name] of [[8, '0.554850', 'SIM-房门甲'], [6, '0.856800', 'SIM-房门乙'], [7, '0.528000', 'SIM-房门丙']]) {
    const contribution = { salesOrderItemId: 4, designItemId, quantity, uomLabel: '平方米', itemName: 'SIM-不可读取贡献自带名称' }
    const { text } = await renderCell('contribution-trace', {}, serverFacts(), { source: contribution }, { sourceObjects, sourceSalesOrderItemId: 4 })
    assert.ok(text.includes(name))
    assert.ok(text.includes(quantity))
    assert.match(text, /平方米/)
    assert.doesNotMatch(text, /SIM-不可读取贡献自带名称/)
  }
  const contribution = { salesOrderItemId: 4, designItemId: 8, quantity: '0.554850', uomLabel: '平方米' }
  for (const [currentScope, candidates, sourceOverride] of [
    [4, [], {}],
    [4, [{ salesOrderItemId: 5, designItemId: 8, itemName: 'SIM-异行名称' }], {}],
    [4, [sourceObjects[0], { ...sourceObjects[0], itemName: 'SIM-歧义名称' }], {}],
    [5, sourceObjects, {}],
    [4, sourceObjects, { salesOrderItemId: 5 }],
    [null, sourceObjects, {}],
  ]) {
    const { text } = await renderCell('contribution-trace', {}, serverFacts(), { source: { ...contribution, ...sourceOverride } },
      { sourceObjects: candidates, sourceSalesOrderItemId: currentScope })
    assert.match(text, /对象名称未提供/)
    assert.doesNotMatch(text, /SIM-房门甲|SIM-异行名称|SIM-歧义名称/)
  }
})

test('the actual parent projection binds names only to one nonempty matching source record/version and the current order line', async () => {
  const declaration = 'const engineeringWorkloadSourceObjects = computed(() => {'
  const start = parentSource.indexOf(declaration)
  assert.ok(start >= 0, 'production source-object projection must exist')
  const bodyStart = start + declaration.length
  const end = parentSource.indexOf('\n})', bodyStart)
  assert.ok(end > bodyStart)
  const readObjects = new Function('selectedOrder', 'unboundDrafts', parentSource.slice(bodyStart, end))
  const direct = { salesOrderItemId: 4, designItemId: 8 }
  const order = { salesOrderItemId: 4, sourceRecordId: 11, sourceVersion: 'SIM-R31', currentDesignInputs: [direct] }
  const named = { salesOrderItemId: 4, designItemId: 8, itemName: 'SIM-同版本正式对象' }
  const foreign = { salesOrderItemId: 5, designItemId: 8, itemName: 'SIM-越行对象' }
  const context = { id: 11, sourceVersion: 'SIM-R31', currentDesignInputs: [named, foreign] }
  const contribution = { salesOrderItemId: 4, designItemId: 8, quantity: '0.554850', uomLabel: '平方米' }
  const selectedOrder = Vue.ref(order), unboundDrafts = Vue.ref([context])
  const before = JSON.stringify({ order, context })
  const matched = readObjects(selectedOrder, unboundDrafts)
  assert.deepEqual(matched.map(row => row.itemName), ['SIM-同版本正式对象'])
  const allowed = await renderCell('contribution-trace', {}, serverFacts(), { source: contribution },
    { sourceObjects: matched, sourceSalesOrderItemId: 4 })
  assert.match(allowed.text, /SIM-同版本正式对象/)
  assert.doesNotMatch(allowed.text, /SIM-越行对象/)
  for (const [selected, contexts] of [
    [order, [{ ...context, id: 12 }]],
    [order, [{ ...context, sourceVersion: 'SIM-R43' }]],
    [order, []],
    [order, [context, { ...context }]],
    [order, [{ ...context, currentDesignInputs: null }]],
    [{ ...order, sourceRecordId: null }, [context]],
    [{ ...order, sourceRecordId: '' }, [context]],
    [{ ...order, sourceVersion: '' }, [context]],
    [{ ...order, sourceVersion: null }, [context]],
  ]) {
    selectedOrder.value = selected
    unboundDrafts.value = contexts
    const current = readObjects(selectedOrder, unboundDrafts)
    assert.deepEqual(current, [direct], 'unproved or ambiguous context retains only formal current-line direct inputs')
    const denied = await renderCell('contribution-trace', {}, serverFacts(), { source: contribution },
      { sourceObjects: current, sourceSalesOrderItemId: 4 })
    assert.match(denied.text, /对象名称未提供/)
    assert.doesNotMatch(denied.text, /SIM-同版本正式对象|SIM-越行对象/)
  }
  for (const selected of [null, { ...order, salesOrderItemId: null }]) {
    assert.deepEqual(readObjects({ value: selected }, { value: [context] }), [])
  }
  assert.deepEqual(readObjects({ value: order }, { value: [{ ...context, currentDesignInputs: [foreign] }] }), [])
  const noContextForeignDirect = { ...order, currentDesignInputs: [foreign] }
  assert.deepEqual(readObjects({ value: noContextForeignDirect }, { value: [] }), [])
  assert.equal(JSON.stringify({ order, context }), before, 'formal inputs stay unchanged')
})
