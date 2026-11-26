import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'
import { createComponentReadLifecycle, componentReadUrl } from '../../src/meta/runtime/componentReadLifecycle.js'
import { createOperationWorkloadViewMemory, reconcileOperationWorkloadView } from '../../src/meta/runtime/operationWorkloadViewContext.js'
import { explicitTraceConditions } from '../../src/meta/runtime/sourceFormatMaintenanceForm.js'

// Synthetic server contracts only. No HTTP, business service, browser or database.
const url = new URL('../../src/meta/components/OperationWorkloadSourcePanel.vue', import.meta.url)
const source = fs.readFileSync(url, 'utf8')
const descriptor = parse(source, { filename: url.pathname }).descriptor
const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const expose = `return { selectedOperationId, selectedPlanId, selectedRoutingStepId, serverFacts, readState, form,
  saving, changeOperation, saveMessage,
  catalog, context, inputPreparation, quantityCards, operationOptions, configuration, configureAuthorization,
  busy, matchingSteps, selectedRoutePlanId, routeFacts, routeReadState, routeReadError, routeConfiguration,
  routeRows, routeListContract, routeFilterSchema, routeExportColumns, routeSelectedRows, routeQuickSearch,
  routeAppliedSearch, routeAdvancedVisible, routeFilters, routeTableRef, routeActiveFilterCount, routeSortText,
  routeFilteredRows, routeClearFilters, routeClearSort, routeClearSelection, routeHandleSort, routeExportCurrent,
  loadRouteOverview, openRouteStep, refreshSourceFacts, optionLabel, quantityText, recordCountText, sourceInputText,
  quantityContractText, reasonLabel, validateRouteFacts, readDiagnostics, strictFacts, viewContextNotices,
  copyCurrentDiagnostics, diagnosticCopyMessage, selectedRoutePlan, routeExpandedStepIds, rememberRouteExpansion,
  conditionalExecutionLabels, traceExpanded, traceKey, rememberTraceExpansion, noDateDisplayFieldLabel }`
const execute = new Function('computed', 'nextTick', 'onBeforeUnmount', 'reactive', 'ref', 'watch', 'defineProps', 'defineEmits', 'pdeApi',
  'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime', 'explicitTraceConditions',
  'getTabAuthEpoch', 'readTabIdentity', 'createComponentReadLifecycle', 'componentReadUrl',
  'createOperationWorkloadViewMemory', 'reconcileOperationWorkloadView', `${script}\n${expose}`)
const render = new Function('Vue', compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
const historicalSection = descriptor.template.content.slice(descriptor.template.content.indexOf('<section v-if="inputPreparation"'),
  descriptor.template.content.indexOf('<div class="quantity-states">'))
const historyRender = new Function('Vue', compile(historicalSection, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
const contract = 'PCE-OPERATION-WORKLOAD-SOURCE-V1'
const bucket = (statusCode, statusLabel, items = [], extra = {}) => ({ statusCode, statusLabel, items, blockers: [], ...extra })
const semantics = { contractVersion: 'PCE-CAPACITY-TRISTATE-V1', valid: true, meaningCode: 'QUANTIFIED',
  statusLabel: '仅保留既有引用元数据', sourceStatusLabel: '正式引用已读取', recordPresenceStatusLabel: '正式引用有记录',
  quantitativeOccupancyAllowed: false, independentDurationAllowed: false }

function fixture() {
  const rows = Array.from({ length: 28 }, (_, index) => {
    const id = 9021 + index
    const quantity = `${index + 2}.456700`
    const formal = bucket('EXISTS', '存在当前有效正式需求', [{ operationRequirementId: 7300 + index,
      sourceFactId: 6400 + index, sourceCalculationId: 6201, quantity, uomLabel: '平方米' }])
    const saved = bucket('SAVED', '已保存且通过原生校验的计划负荷', [{ allocationId: 8100 + index,
      operationRequirementId: 7300 + index, sourceFactId: 6400 + index, sourceCalculationId: 6201,
      quantity, uomLabel: '平方米', auditId: 9100 + index }], { quantity, uomId: 6180, uomLabel: '平方米' })
    const row = { routingStepId: id, operationId: 9821 + index, sequence: index + 1,
      predecessorSequences: index ? [index] : [], operationName: `隔离工序${index + 1}`,
      applicability: { result: 'REQUIRED', statusLabel: '当前对象经过' }, capacitySemantics: { ...semantics },
      sourceConfiguration: { statusLabel: '来源已配置', sources: [{ ruleId: 7200 + index, ruleName: `独立面积口径${index + 1}`,
        ruleVersion: 'V9', sourceCanonicalField: 'ISOLATED_VISIBLE_AREA', producerVersion: 'V3',
        quantityExpression: 'source_quantity', quantityBasisLabel: '来源范围总量', deduplicationLabel: '本范围计一次' }] },
      resourceReferences: {}, sourceCandidates: bucket('MATCHED', '正式来源工程事实匹配',
        [{ sourceCalculationId: 6201, sourceFactId: 6400 + index, quantity, uomLabel: '平方米' }]),
      formalRequirements: formal, savedAllocations: saved,
      objectCoverage: { statusCode: 'PROVEN', statusLabel: '当前读取覆盖证明有效', designItemIds: [501],
        baselineItemIds: [601], inputFactIds: [6400 + index], proofSource: 'CURRENT_READ_VALIDATED_SOURCE_CHAIN' },
      workloadReview: { statusCode: 'SAVED', statusLabel: '当前投产量已核对', applicabilityLabel: '当前对象经过',
        processingLabel: '采用本工序独立来源', sourceBusinessLabel: `独立面积口径${index + 1}`,
        formalRequirementStatusLabel: formal.statusLabel, formalRequirementCount: 1,
        allocationStatusLabel: saved.statusLabel, allocationCount: 1, savedQuantity: quantity,
        uomLabel: '平方米', coverageStatusLabel: '当前读取覆盖证明有效', blockers: [] } }
    return row
  })
  return { contractVersion: contract, factSource: 'server', businessWriteCount: 0,
    routeConfiguration: { workloadReviewIncluded: true, workloadReviewContract: 'PCE-ROUTE-WORKLOAD-READ-V1',
      scope: { companyId: 6099, productionPlanId: 5008, manufacturingOutputId: 7008, mainCalculationId: 7108,
        salesOrderItemId: 7208, baselineId: 7308, routingId: 7408, routingVersionId: 7508, productTypeId: 7608 },
      rows, summary: { stepCount: 28, statusLabel: '旧元数据标签不能覆盖当前投产事实', workloadStatusLabel: '当前同一读取范围已取得', formalRequirementRecordCount: 28,
        allocationRecordCount: 28 }, businessWriteCount: 0, auditWriteCount: 0,
      generated: false, allocationSaved: false, newEorRuleEvaluated: false, wholeRouteReady: false } }
}
function planOf(value) {
  const route = value.routeConfiguration
  return { id: 5008, label: '隔离计划', manufacturingOutputId: 7008, routingVersionId: 7508,
    allRoutingSteps: route.rows.map(row => ({ id: row.routingStepId, operationId: row.operationId })) }
}
function runtime(api = {}, value = fixture()) {
  const props = Vue.reactive({ operations: [], mode: 'view', refreshKey: 0, invalidateKey: 0, parentReadStatus: 'loaded' })
  const state = execute(Vue.computed, Vue.nextTick, () => {}, Vue.reactive, Vue.ref, () => {}, () => props, () => () => {}, api,
    createPceEnterpriseListContract, usePceEnterpriseListRuntime, explicitTraceConditions,
    () => 1, () => ({ userId: 8099, companyId: 6099 }), createComponentReadLifecycle, componentReadUrl,
    createOperationWorkloadViewMemory, reconcileOperationWorkloadView)
  state.serverFacts.value = { contractVersion: contract, factSource: 'server', catalog: {
    companyId: 6099, productionPlans: [planOf(value)], configureAuthorization: { allowed: false, statusLabel: '只读账号' } } }
  state.readState.value = 'loaded'
  return { props, ...state }
}
async function html(state, selectedRender = render) {
  const data = Object.fromEntries(Object.entries(state).map(([key, value]) => [key, Vue.isRef(value) ? value.value : value]))
  const app = Vue.createSSRApp({ data: () => ({ ...state.props, ...data }), render: selectedRender })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  app.component('ElTableColumn', { render: () => null })
  app.component('PceEnterpriseListTable', { props: ['tableRows'], setup(props, { slots }) {
    function cells(nodes, row) {
      return nodes.flatMap(node => Array.isArray(node.children) ? cells(node.children, row)
        : node.children?.default ? node.children.default({ row }) : [])
    }
    return () => Vue.h('section', props.tableRows.map(row => Vue.h('article', [row.stepLabel,
      row.processingText, row.sourceBusinessLabel, row.formalRequirementLabel, row.savedQuantityText,
      row.savedAllocationLabel, row.coverageStatusLabel, row.blockerText,
      ...cells(slots.columns?.() || [], row), ...(slots.actions?.({ row }) || [])])))
  } })
  return renderToString(app)
}
function assignBranch(row, code, label, extra = {}) {
  const unknown = ['NOT_READ', 'NOT_EVALUATED', 'READ_FAILED', 'PENDING', 'NOT_APPLICABLE'].includes(code)
  row.formalRequirements = bucket(code, `需求：${label}`)
  row.savedAllocations = bucket(code, `分配：${label}`, [], { quantity: null, uomId: null, uomLabel: null })
  row.objectCoverage = { statusCode: code, statusLabel: `覆盖：${label}`, designItemIds: null, baselineItemIds: null,
    inputFactIds: null, proofSource: null }
  Object.assign(row.workloadReview, { statusCode: code, statusLabel: label, applicabilityLabel: label,
    processingLabel: label, formalRequirementStatusLabel: row.formalRequirements.statusLabel,
    formalRequirementCount: unknown ? null : 0, allocationStatusLabel: row.savedAllocations.statusLabel,
    allocationCount: unknown ? null : 0, savedQuantity: null, uomLabel: null,
    coverageStatusLabel: row.objectCoverage.statusLabel, blockers: [], ...extra })
}

test('final workload panel compiles and retains governed list and lazy drilldown', () => {
  assert.equal(compileTemplate({ source: descriptor.template.content, filename: url.pathname, id: 'final-workload' }).errors.length, 0)
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'final-workload' }))
  assert.match(source, /:default-page-size="50"/)
  assert.match(source, /:primary-width="140"/)
  assert.match(source, /:show-action-column="mode === 'maintain'"/)
  assert.match(source, /v-if="mode !== 'maintain'"[^>]*@click="openRouteStep\(row\)">查看完整来源追溯/)
  assert.match(source, /<el-table-column type="expand"/)
  assert.match(source, /PceEnterpriseListTable/)
  assert.match(source, /@click="openRouteStep\(row\)"/)
  assert.match(source, /function quantityText\(value\)[\s\S]*?value === null \|\| value === undefined/)
})

test('explicit current workload read yields the exact 28 identities and export values', async () => {
  const value = fixture()
  const calls = []
  const state = runtime({ getOperationWorkloadSources: async params => { calls.push(params); return { data: value } } }, value)
  state.selectedRoutePlanId.value = '5008'
  assert.equal(await state.loadRouteOverview(), true)
  assert.deepEqual(calls, [{ routeOverview: 1, includeWorkloads: 1, productionPlanId: 5008 }])
  assert.equal(state.routeRows.value.length, 28)
  assert.deepEqual(state.routeRows.value.map(row => row.routingStepId), value.routeConfiguration.rows.map(row => row.routingStepId))
  for (const [index, row] of state.routeRows.value.entries()) {
    assert.equal(row.savedQuantityText, `${index + 2}.456700 平方米`)
    assert.equal(row.sourceBusinessLabel, `独立面积口径${index + 1}`)
    assert.equal(row.formalRequirementLabel, '存在当前有效正式需求；1条')
  }
  assert.deepEqual(state.routeExportColumns.map(column => column.field), ['sequence', 'operationName', 'processingText',
    'sourceBusinessLabel', 'formalRequirementLabel', 'savedQuantityText', 'savedAllocationLabel', 'coverageStatusLabel', 'blockerText'])
  const rendered = await html(state)
  assert.match(rendered, /当前同一读取范围已取得/)
  assert.doesNotMatch(rendered, /旧元数据标签不能覆盖当前投产事实/)
  assert.match(rendered, /隔离工序28/)
  assert.match(rendered, /29\.456700 平方米/)
  assert.doesNotMatch(rendered, /原生需求合计|总面积：/)
})

test('zero, unknown, unread, not-applicable and auxiliary meanings remain distinct server facts', async () => {
  const value = fixture()
  const rows = value.routeConfiguration.rows
  rows[0].savedAllocations.quantity = '0.000000'
  rows[0].workloadReview.savedQuantity = '0.000000'
  assignBranch(rows[1], 'MISSING', '真实缺失／未知')
  assignBranch(rows[2], 'NOT_READ', '尚未读取')
  assignBranch(rows[3], 'NOT_APPLICABLE', '有正式依据的不适用')
  assignBranch(rows[4], 'MISSING', '原生配套处理，不形成独立定量负荷', { statusCode: 'AUXILIARY' })
  const state = runtime({}, value)
  state.routeFacts.value = state.validateRouteFacts(value, planOf(value), 6099)
  assert.equal(state.routeRows.value[0].savedQuantityText, '0.000000 平方米')
  assert.equal(state.routeRows.value[1].formalRequirementLabel, '需求：真实缺失／未知；0条')
  assert.equal(state.routeRows.value[2].formalRequirementLabel, '需求：尚未读取；记录数未知')
  assert.equal(state.routeRows.value[3].formalRequirementLabel, '需求：有正式依据的不适用；记录数未知')
  assert.equal(state.routeRows.value[4].savedQuantityText, '未知')
  assert.match(state.routeRows.value[4].processingText, /原生配套处理/)
})

test('invalid counts, quantity mapping, units, route identities or scope fail closed', () => {
  const variations = [
    value => { value.routeConfiguration.rows[0].workloadReview.formalRequirementCount = 4 },
    value => { value.routeConfiguration.rows[0].workloadReview.savedQuantity = '999.000000' },
    value => { value.routeConfiguration.rows[0].workloadReview.uomLabel = '件' },
    value => { value.routeConfiguration.rows[1].routingStepId = value.routeConfiguration.rows[0].routingStepId },
    value => { value.routeConfiguration.rows[1].sequence = value.routeConfiguration.rows[0].sequence },
    value => { value.routeConfiguration.rows[0].operationId = 9999 },
    value => { value.routeConfiguration.scope.companyId = 6098 },
    value => { value.routeConfiguration.workloadReviewIncluded = false },
    value => { value.routeConfiguration.rows[0].objectCoverage.designItemIds = [true] },
  ]
  for (const mutate of variations) {
    const value = fixture()
    const plan = planOf(value)
    mutate(value)
    assert.throws(() => runtime({}, value).validateRouteFacts(value, plan, 6099))
  }
})

test('historical preparation text remains folded and independent from current formal state', async () => {
  const state = runtime()
  state.selectedOperationId.value = '9821'
  state.selectedPlanId.value = '5008'
  state.selectedRoutingStepId.value = '9021'
  state.serverFacts.value.configuration = { operationId: 9821, statusLabel: '已发布当前来源', sources: [] }
  state.serverFacts.value.context = { scope: { productionPlanId: 5008, routingStepId: 9021 },
    sourceConfiguration: { statusLabel: '当前来源方案有效' }, formalRequirements: bucket('EXISTS', '当前正式需求已保存'),
    savedAllocations: bucket('SAVED', '当前分配已保存', [], { quantity: '8.765400', uomLabel: '平方米' }),
    inputPreparation: { statusLabel: '记录原状态', inputStandardStatusLabel: '历史投入标准待确认',
      capacityMeasurementStatusLabel: '记录保留不可定量裁决', formalRuleStatusLabel: '记录当时未发布规则',
      remainingItems: [{ statusLabel: '历史需求缺失、负荷未知' }], businessBasisPresentation: [
        { statusLabel: '历史原答复', exactStatement: '原文完整保留，不改写后来状态。', reference: '隔离历史凭证' }] },
    blockers: [] }
  const result = await html(state, historyRender)
  assert.match(result, /当前正式读取状态/)
  assert.match(result, /当前来源方案有效/)
  assert.match(result, /8\.765400 平方米/)
  assert.match(result, /<details data-section="historical-input-preparation"><summary>记录保存时状态／历史依据<\/summary>/)
  assert.doesNotMatch(result, /<details[^>]*data-section="historical-input-preparation"[^>]*open/)
  assert.match(result, /历史需求缺失、负荷未知/)
  assert.match(result, /原文完整保留，不改写后来状态。/)
})

test('stale plan response cannot replace the currently selected plan facts', async () => {
  let release
  const response = new Promise(resolve => { release = resolve })
  const value = fixture()
  const state = runtime({ getOperationWorkloadSources: () => response }, value)
  state.selectedRoutePlanId.value = '5008'
  const pending = state.loadRouteOverview()
  state.selectedRoutePlanId.value = ''
  await state.loadRouteOverview()
  release({ data: value })
  assert.equal(await pending, false)
  assert.equal(state.routeFacts.value, null)
  assert.equal(state.routeReadState.value, 'idle')
})

test('real exposed table clear event terminates and initial read plus refresh each calls the API once', async () => {
  assert.equal((source.match(/@clear-selection="routeSelectedRows = \[\]"/g) || []).length, 1)
  const oldSource = source.replace('@clear-selection="routeSelectedRows = []"', '@clear-selection="routeClearSelection"')
  const oldDescriptor = parse(oldSource, { filename: url.pathname }).descriptor
  const oldRender = new Function('Vue', compile(oldDescriptor.template.content,
    { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const sharedUrl = new URL('../../src/meta/components/PceEnterpriseListTable.vue', import.meta.url)
  const sharedSource = fs.readFileSync(sharedUrl, 'utf8')
  const sharedDescriptor = parse(sharedSource, { filename: sharedUrl.pathname }).descriptor
  assert.doesNotThrow(() => compileScript(sharedDescriptor, { id: 'real-exposed-clear-selection' }))
  assert.equal(compileTemplate({ source: sharedDescriptor.template.content, filename: sharedUrl.pathname,
    id: 'real-exposed-clear-selection' }).errors.length, 0)
  assert.match(sharedDescriptor.scriptSetup.content, /defineExpose\(\{[\s\S]*?\bclearSelection\b/)
  const clearStart = sharedDescriptor.scriptSetup.content.indexOf('function clearSelection()')
  const clearEnd = sharedDescriptor.scriptSetup.content.indexOf('function requestExportCurrent()', clearStart)
  assert.ok(clearStart >= 0 && clearEnd > clearStart)
  // Execute the existing shared component's exact public method body; do not
  // reimplement its behavior. The small adapter supplies its ordinary Element
  // table ref and routes emitted names to actual compiled parent listeners.
  const actualClearDeclaration = sharedDescriptor.scriptSetup.content.slice(clearStart, clearEnd)
  const exposeSharedClear = new Function('tableRef', 'internalSelectedRows', 'emit',
    `${actualClearDeclaration}\nreturn clearSelection`)

  async function wireRealExposedClear(state, selectedRender) {
    let listeners
    const app = Vue.createSSRApp({ setup: () => ({ ...state.props, ...state }), render: selectedRender })
    app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
    app.component('ElTableColumn', { render: () => null })
    app.component('PceEnterpriseListTable', { inheritAttrs: false, props: ['tableRows'], setup(props, { attrs }) {
      listeners = { clear: attrs.onClearSelection, selection: attrs.onSelectionChange }
      return () => Vue.h('section')
    } })
    await renderToString(app)
    assert.equal(typeof listeners?.clear, 'function')
    assert.equal(typeof listeners?.selection, 'function')
    const calls = { exposedClear: 0, elementClear: 0, emitted: [] }
    const internalSelectedRows = Vue.ref([state.routeRows.value[0]])
    const elementTableRef = Vue.ref({ clearSelection() {
      calls.elementClear += 1
      // Bound the already known faulty chain offline instead of overflowing
      // Node's stack or invoking any browser/network operation.
      if (calls.elementClear > 6) throw new Error('OFFLINE_BOUND_DETECTED_CLEAR_SELECTION_CYCLE')
    } })
    const clearSelection = exposeSharedClear(elementTableRef, internalSelectedRows, (event, value) => {
      calls.emitted.push(event)
      if (event === 'selection-change') listeners.selection(value)
      else if (event === 'clear-selection') listeners.clear()
      else assert.fail('Unexpected event from the unmodified public clear method')
    })
    state.routeTableRef.value = { clearSelection() {
      calls.exposedClear += 1
      return clearSelection()
    } }
    return { calls, internalSelectedRows }
  }

  const oldApiCalls = []
  const oldValue = fixture()
  const bad = runtime({ getOperationWorkloadSources: async params => {
    oldApiCalls.push(params)
    return { data: structuredClone(oldValue) }
  } }, oldValue)
  bad.selectedRoutePlanId.value = '5008'
  assert.equal(await bad.loadRouteOverview(), true)
  assert.equal(oldApiCalls.length, 1)
  const boundedOld = await wireRealExposedClear(bad, oldRender)
  await assert.rejects(bad.loadRouteOverview(), /OFFLINE_BOUND_DETECTED_CLEAR_SELECTION_CYCLE/)
  assert.equal(oldApiCalls.length, 1, 'Known faulty refresh never reaches the second API invocation')
  assert.ok(boundedOld.calls.exposedClear > 1)
  assert.equal(bad.routeFacts.value, null)

  const apiCalls = []
  const current = fixture()
  const state = runtime({ getOperationWorkloadSources: async params => {
    apiCalls.push(params)
    return { data: structuredClone(current) }
  } }, current)
  state.selectedRoutePlanId.value = '5008'
  assert.equal(await state.loadRouteOverview(), true)
  assert.equal(apiCalls.length, 1)
  const bridge = await wireRealExposedClear(state, render)
  state.routeSelectedRows.value = [state.routeRows.value[0]]
  assert.equal(await state.loadRouteOverview(), true)
  assert.equal(apiCalls.length, 2)
  assert.ok(apiCalls.every(params => params.productionPlanId === 5008 && params.routeOverview === 1 && params.includeWorkloads === 1))
  assert.equal(bridge.calls.exposedClear, 1)
  assert.equal(bridge.calls.elementClear, 1)
  assert.deepEqual(bridge.calls.emitted, ['selection-change', 'clear-selection'])
  assert.deepEqual(state.routeSelectedRows.value, [])
  assert.deepEqual(bridge.internalSelectedRows.value, [])
  assert.equal(state.routeReadState.value, 'loaded')
  assert.equal(state.routeRows.value.length, 28)
  state.routeTableRef.value.clearSelection()
  assert.equal(bridge.calls.exposedClear, 2)
  assert.equal(bridge.calls.elementClear, 2)
  assert.equal(apiCalls.length, 2, 'The normal table clear action does not reload or recurse')
})
