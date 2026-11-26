import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import test from 'node:test'

// SIMULATED_FOR_TEST promises/renderer only. The optional final case consumes
// complete, captured native responses without HTTP, browser or DB access.
const repo = process.cwd()
const frontend = path.resolve(process.env.PCE_FRONTEND_SOURCE_ROOT || path.join(repo, 'frontend'))
const require = createRequire(path.join(repo, 'frontend/package.json'))
const Vue = require('vue')
const { parse, compileScript, compileTemplate } = require('@vue/compiler-sfc')
const { compile } = require('@vue/compiler-dom')
const { renderToString } = require('@vue/server-renderer')
const sourcePath = path.join(frontend, 'src/meta/components/OperationWorkloadSourcePanel.vue')
const source = readFileSync(sourcePath, 'utf8')
const { descriptor } = parse(source, { filename: sourcePath })
const script = descriptor.scriptSetup.content
const runtimeModule = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/pceEnterpriseListContract.js')))
const lifecycle = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/componentReadLifecycle.js')))
const memory = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/operationWorkloadViewContext.js')))
const trace = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/sourceFormatMaintenanceForm.js')))
const diagnostics = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/pageObservabilityActions.js')))
function actualFunction(name) {
  const match = script.match(new RegExp(`function ${name}\\([^]*?\\n\\}`))
  assert.ok(match, `Actual component function ${name} exists`)
  return match[0]
}
const functionNames = ['quantityText', 'recordCountText', 'serverDisplayLabel', 'sourceInputText', 'quantityContractText',
  'reasonLabel', 'noDateDisplayFieldLabel', 'canonicalSnapshot', 'validateFacts', 'validateNoDateCapacity', 'validateRequestedScope',
  'validateCapacitySemantics', 'validateInputPreparation', 'validateCapacityConsumptionPreparation', 'validateConditionalPreparation',
  'validateQuantityPolicy', 'validateQuantityPolicyPreparation', 'validateRouteFacts']
const functions = functionNames.map(actualFunction).join('\n')
const actual = new Function('CONTRACT', `${functions}\nreturn { ${functionNames.join(', ')} }`)('PCE-OPERATION-WORKLOAD-SOURCE-V1')
const scope = { companyId: 8301, productionPlanId: 8302, manufacturingOutputId: 8303, mainCalculationId: 8304,
  salesOrderItemId: 8305, baselineId: 8306, routingVersionId: 8307, routingStepId: 8308, operationId: 8309, productTypeId: 8310 }
const contract = 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1'
const labelFields = ['capacityLabel', 'productionDaysLabel', 'preparationDaysLabel', 'transferDaysLabel',
  'totalDaysLabel', 'timeSourceLabel', 'scopeBoundaryLabel']
function labels(prefix = '隔离正式') {
  return { capacityLabel: `${prefix}产能已核对`, productionDaysLabel: `${prefix}加工用时 0.3123456789 天`,
    preparationDaysLabel: `${prefix}准备 0.1 天，计入一次`, transferDaysLabel: `${prefix}转运 0.1 天，计入一次`,
    totalDaysLabel: `${prefix}理论用时 0.5123456789 天`, timeSourceLabel: `${prefix}时间来自所选正式标准`,
    scopeBoundaryLabel: `${prefix}仅无日期核对，不形成排程或资源占用` }
}
function noDate(exactScope = scope) {
  return { contractVersion: contract, factSource: 'server', scope: { ...exactScope },
    assessedAt: '2026-10-20T10:00:00+08:00', resultHash: 'a'.repeat(64), stage: 'QUANTIFIED',
    statusCode: 'MATCHED', statusLabel: '隔离原生无日期匹配通过', legalEmptyLoadVerified: false,
    independentAllocationRequired: true, noDateMatchPassed: true, scopeNoDateReady: true,
    matchedStepCount: 1, matchedAllocationCount: 1, displayLabels: labels(),
    capacityMatches: [{ standardCapacityId: 8311, workCenterId: 8312,
      capacityFact: { id: 8311, quantity: '500.000000', uomId: 8313, uomLabel: '米', available: false },
      productionDays: '0.3123456789', preparationDays: '0.1', transferDays: '0.1', durationDays: '0.5123456789',
      preparationIncludedCount: 1, transferIncludedCount: 1,
      timeSelection: { preparation: { source: 'CAPACITY_SOURCE_RULES_HEADER' },
        transfer: { source: 'CAPACITY_SOURCE_RULES_HEADER' } }, displayLabels: labels('隔离所选') }],
    timeReferences: { step: null, standardCapacities: [] }, blockers: [], dateLayerBlockers: [],
    dateConditions: { planStartDateProvided: false, calendarOccupationEvaluated: false,
      capacityAndResourceExecutionWindowEvaluated: false, statusLabel: '未评估日期、执行期间及资源占用' },
    planningReady: false, businessWriteCount: 0, auditWriteCount: 0, dateOccupationCount: 0,
    productionScheduleCreatedCount: 0 }
}
function special(stage, statusCode, label) {
  const value = noDate()
  Object.assign(value, { stage, statusCode, statusLabel: label,
    legalEmptyLoadVerified: stage !== 'NON_QUANTIFIED_SAVED_LOAD',
    independentAllocationRequired: stage === 'NON_QUANTIFIED_SAVED_LOAD', noDateMatchPassed: false,
    scopeNoDateReady: false, matchedStepCount: 0, matchedAllocationCount: 0, capacityMatches: [],
    displayLabels: { capacityLabel: label, productionDaysLabel: '不形成独立定量加工用时',
      preparationDaysLabel: '准备时间仅保留正式引用，不计入准确工期',
      transferDaysLabel: '转运时间仅保留正式引用，不计入准确工期',
      totalDaysLabel: '不形成独立准确工期，不等于0天', timeSourceLabel: '保留原正式时间参考',
      scopeBoundaryLabel: '保留本步骤，不形成日期、占用或完成事实' } })
  return value
}
function routeFixture() {
  const routeScope = { ...scope, routingId: 8314 }
  delete routeScope.routingStepId
  delete routeScope.operationId
  const rows = Array.from({ length: 28 }, (_, index) => {
    const exact = { ...scope, routingStepId: 8400 + index, operationId: 8500 + index }
    const formal = { statusCode: 'EXISTS', statusLabel: '存在正式需求', items: [{ operationRequirementId: 8600 + index }], blockers: [] }
    const saved = { statusCode: 'SAVED', statusLabel: '已保存负荷', items: [{ allocationId: 8700 + index }],
      quantity: '2.456700', uomLabel: '米', blockers: [] }
    return { routingStepId: exact.routingStepId, operationId: exact.operationId, sequence: index + 1,
      operationName: `隔离工序${index + 1}`, scope: exact, predecessorSequences: index ? [index] : [],
      sourceConfiguration: { sources: [] }, resourceReferences: {},
      sourceCandidates: { statusCode: 'AVAILABLE', statusLabel: '来源可读取', items: [], blockers: [] },
      formalRequirements: formal, savedAllocations: saved,
      objectCoverage: { statusCode: 'PROVEN', statusLabel: '原固定对象证明', designItemIds: [1], baselineItemIds: [2], inputFactIds: [3] },
      workloadReview: { statusCode: 'SAVED', statusLabel: '已核对原保存量', applicabilityLabel: '本步骤必经',
        processingLabel: '按本步骤正式来源执行', sourceBusinessLabel: '独立正式数量口径',
        formalRequirementStatusLabel: formal.statusLabel, formalRequirementCount: 1,
        allocationStatusLabel: saved.statusLabel, allocationCount: 1, savedQuantity: saved.quantity,
        uomLabel: saved.uomLabel, coverageStatusLabel: '原固定对象证明', blockers: [] }, noDateCapacity: noDate(exact) }
  })
  return { contractVersion: 'PCE-OPERATION-WORKLOAD-SOURCE-V1', factSource: 'server', businessWriteCount: 0,
    routeConfiguration: { scope: routeScope, rows, summary: { stepCount: 28, workloadStatusLabel: '本次正式读取' },
      businessWriteCount: 0, auditWriteCount: 0, generated: false, allocationSaved: false, newEorRuleEvaluated: false,
      workloadReviewIncluded: true, workloadReviewContract: 'PCE-ROUTE-WORKLOAD-READ-V1',
      noDateCapacityIncluded: true, noDateCapacityContract: contract,
      noDateCapacitySummary: { statusLabel: '隔离本次读取28步；定量28步，其余特殊及阻断均0步',
        readStepCount: 28, assessedAt: '2026-10-20T10:00:00+08:00', resultHash: 'b'.repeat(64) } } }
}
function planFor(route) {
  const value = route.routeConfiguration
  return { id: value.scope.productionPlanId, manufacturingOutputId: value.scope.manufacturingOutputId,
    routingVersionId: value.scope.routingVersionId, allRoutingSteps: value.rows.map(row => ({ id: row.routingStepId, operationId: row.operationId })) }
}
function detailFixture() {
  return { contractVersion: 'PCE-OPERATION-WORKLOAD-SOURCE-V1', factSource: 'server', operations: [],
    configuration: { operationId: scope.operationId },
    catalog: { companyId: scope.companyId, producers: [], manufacturingModes: [], productTypes: [], standardCapacities: [],
      workCenters: [], productionPlans: [] }, context: { scope: { ...scope }, noDateCapacityIncluded: true,
      noDateCapacityContract: contract, noDateCapacity: noDate() } }
}
const params = { operationId: scope.operationId, productionPlanId: scope.productionPlanId, routingStepId: scope.routingStepId }
const clone = value => structuredClone(value)
const settle = async () => { await Promise.resolve(); await Promise.resolve(); await Vue.nextTick(); await Promise.resolve() }
function section(marker) {
  const start = descriptor.template.content.indexOf(marker)
  assert.ok(start >= 0)
  const end = descriptor.template.content.indexOf('</section>', start)
  assert.ok(end > start)
  return descriptor.template.content.slice(start, end + '</section>'.length)
}
async function html(template, data) {
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ data: () => ({ reasonLabel: actual.reasonLabel, noDateDisplayFieldLabel: actual.noDateDisplayFieldLabel, ...data }), render })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  return renderToString(app)
}
function runtime(api, extra = {}) {
  const clean = script.replace(/^import .*$/gm, '')
  const unmount = []
  const props = Vue.reactive({ operations: [], mode: 'view', refreshKey: 0, invalidateKey: 0, parentReadStatus: 'loaded' })
  const deps = { computed: Vue.computed, nextTick: Vue.nextTick, onBeforeUnmount: fn => unmount.push(fn),
    reactive: Vue.reactive, ref: Vue.ref, watch: () => {}, inject: () => extra.observability || null,
    defineProps: () => props, defineEmits: () => () => {}, pdeApi: api,
    ...runtimeModule, ...lifecycle, ...memory, ...trace, ...diagnostics,
    getTabAuthEpoch: () => 1, readTabIdentity: () => ({ userId: 8315, companyId: scope.companyId }) }
  const result = new Function(...Object.keys(deps), `${clean}\nreturn { selectedRoutePlanId, selectedOperationId, selectedPlanId,
    selectedRoutingStepId, serverFacts, routeFacts, routeReadState, readState, routeReadError, routeRows, strictFacts,
    buildDiagnostics, loadRouteOverview, loadSources, routeExportCurrent, readDiagnostics }`)(...Object.values(deps))
  const route = routeFixture()
  result.serverFacts.value = detailFixture()
  result.serverFacts.value.catalog.productionPlans = [planFor(route)]
  result.selectedRoutePlanId.value = String(scope.productionPlanId)
  return { ...result, props, unmount }
}

test('actual SFC compiles with the original governed table and exactly two additional no-date columns', () => {
  const compiled = compileScript(descriptor, { id: 'no-date-capacity-display' })
  assert.deepEqual(compileTemplate({ id: 'no-date-capacity-display', source: descriptor.template.content,
    filename: sourcePath, compilerOptions: { bindingMetadata: compiled.bindings } }).errors, [])
  assert.match(source, /prop="noDateCapacityLabel"/)
  assert.match(source, /prop="noDateTimeLabel"/)
  assert.doesNotMatch(source, /timeout\s*:|setInterval\(|retry\s*:/)
  const request = readFileSync(path.join(frontend, 'src/api/request.js'), 'utf8')
  assert.match(request, /timeout:\s*15000/)
})

test('quantitative contract retains exact native strings, selected capacity and shared-time provenance without recalculation', () => {
  const value = noDate()
  const before = JSON.stringify(value)
  assert.equal(actual.validateNoDateCapacity(value, scope), value)
  assert.equal(JSON.stringify(value), before)
  assert.equal(value.capacityMatches[0].capacityFact.available, false)
  assert.equal(value.capacityMatches[0].durationDays, '0.5123456789')
  assert.equal(value.capacityMatches[0].timeSelection.preparation.source, 'CAPACITY_SOURCE_RULES_HEADER')
})

test('all four native special states keep distinct server text and never fabricate a quantitative match or zero days', async () => {
  for (const [stage, code, label] of [
    ['NON_QUANTIFIED_SAVED_LOAD', 'AUXILIARY', '有保存负荷，产能无法准确核算'],
    ['NOT_APPLICABLE_VERIFIED', 'NOT_APPLICABLE_VERIFIED', '正式不适用，保留本步骤'],
    ['WAITING_TRIGGER', 'WAITING_TRIGGER', '品质异常触发时执行，当前待触发'],
    ['NOT_SEPARATELY_MEASURED_VERIFIED', 'NOT_SEPARATELY_MEASURED_VERIFIED', '常规配套，不单独计量'],
  ]) {
    const value = special(stage, code, label)
    actual.validateNoDateCapacity(value, scope)
    const rendered = await html(section('<section v-if="context.noDateCapacity"'), { context: { noDateCapacity: value }, readState: 'loaded' })
    assert.match(rendered, new RegExp(label))
    assert.match(rendered, /不形成独立准确工期，不等于0天/)
    assert.doesNotMatch(rendered, /MATCHED|AUXILIARY|WAITING_TRIGGER|NOT_APPLICABLE_VERIFIED|NOT_SEPARATELY_MEASURED_VERIFIED/)
    assert.equal(value.noDateMatchPassed, false)
    assert.deepEqual(value.capacityMatches, [])
  }
})

test('every exact-scope identity, provenance, server label and zero-write boundary is required', () => {
  for (const key of Object.keys(scope)) {
    const value = noDate()
    value.scope[key] += 1
    assert.throws(() => actual.validateNoDateCapacity(value, scope), /无日期产能核对/)
  }
  for (const alter of [v => { delete v.resultHash }, v => { v.assessedAt = '' }, v => { v.businessWriteCount = 1 },
    v => { v.auditWriteCount = 1 }, v => { v.dateOccupationCount = 1 }, v => { v.planningReady = true },
    v => { v.dateConditions.calendarOccupationEvaluated = true }, v => { v.productionScheduleCreatedCount = 1 },
    ...labelFields.map(key => v => { delete v.displayLabels[key] })]) {
    const value = noDate(); alter(value)
    assert.throws(() => actual.validateNoDateCapacity(value, scope), /无日期产能核对/)
  }
})

test('malformed native duration values and contradictory legal-empty flags fail closed', () => {
  for (const alter of [v => { v.capacityMatches[0].durationDays = 0 }, v => { delete v.capacityMatches[0].productionDays },
    v => { v.capacityMatches[0].preparationDays = '-1' }, v => { v.capacityMatches[0].transferIncludedCount = null },
    v => { v.capacityMatches[0].displayLabels.timeSourceLabel = '' }, v => { v.legalEmptyLoadVerified = true },
    v => { v.noDateMatchPassed = true; v.capacityMatches = [] }]) {
    const value = noDate(); alter(value)
    assert.throws(() => actual.validateNoDateCapacity(value, scope), /无日期产能核对/)
  }
  const unknown = special('WAITING_TRIGGER', 'EMPTY_LOAD_POLICY_CONFLICT', '政策与当前事实冲突，是否独立分配尚未证明')
  Object.assign(unknown, { legalEmptyLoadVerified: false, independentAllocationRequired: null,
    blockers: [{ code: 'EMPTY_LOAD_POLICY_CONFLICT', label: '原生政策与当前执行事实冲突' }] })
  actual.validateNoDateCapacity(unknown, scope)
  const unproven = clone(unknown); unproven.blockers = []
  assert.throws(() => actual.validateNoDateCapacity(unproven, scope), /无日期产能核对/)
})

test('actual full 28-step and detail validators require the new result when its native read marker is present', () => {
  const route = routeFixture()
  actual.validateRouteFacts(route, planFor(route), scope.companyId)
  actual.validateFacts(detailFixture())
  actual.validateRequestedScope(detailFixture(), params)
  const broken = clone(route); delete broken.routeConfiguration.rows[12].noDateCapacity
  assert.throws(() => actual.validateRouteFacts(broken, planFor(route), scope.companyId), /无日期产能核对/)
  const detail = detailFixture(); delete detail.context.noDateCapacity
  assert.throws(() => actual.validateRequestedScope(detail, params), /无日期产能核对/)
})

test('effective fixed-source anchors remain separate from root step and reject a different effective scope', () => {
  const route = routeFixture()
  const row = route.routeConfiguration.rows[2]
  row.effectiveVersion = { rootRoutingStepId: row.routingStepId, effectiveRoutingStepId: 9901,
    effectiveManufacturingOutputId: 9902, effectiveRoutingVersionId: 9903, sourceBaselineId: 9904, mainCalculationId: 9905 }
  Object.assign(row.scope, { routingStepId: 9901, manufacturingOutputId: 9902, routingVersionId: 9903,
    baselineId: 9904, mainCalculationId: 9905 })
  row.noDateCapacity.scope = { ...row.scope }
  actual.validateRouteFacts(route, planFor(route), scope.companyId)
  for (const field of ['routingStepId', 'manufacturingOutputId', 'routingVersionId', 'baselineId', 'mainCalculationId']) {
    const broken = clone(route)
    broken.routeConfiguration.rows[2].scope[field] += 1
    broken.routeConfiguration.rows[2].noDateCapacity.scope[field] += 1
    assert.throws(() => actual.validateRouteFacts(broken, planFor(route), scope.companyId), /范围不一致/)
  }
})

test('actual route mapping uses server labels and never changes the original saved quantity', () => {
  const route = routeFixture()
  const mapping = script.slice(script.indexOf('const routeRows = computed('), script.indexOf('const routeListContract ='))
  const rows = new Function('computed', 'routeConfiguration', `${functions}\n${mapping}\nreturn routeRows`)(
    Vue.computed, Vue.ref(route.routeConfiguration)).value
  assert.equal(rows.length, 28)
  assert.equal(rows[0].noDateCapacityLabel, route.routeConfiguration.rows[0].noDateCapacity.displayLabels.capacityLabel)
  assert.equal(rows[0].noDateTimeLabel, route.routeConfiguration.rows[0].noDateCapacity.displayLabels.totalDaysLabel)
  assert.equal(rows[0].savedQuantityText, '2.456700 米')
  delete route.routeConfiguration.rows[0].noDateCapacity
  const unknown = new Function('computed', 'routeConfiguration', `${functions}\n${mapping}\nreturn routeRows`)(
    Vue.computed, Vue.ref(route.routeConfiguration)).value[0]
  assert.equal(unknown.noDateCapacityLabel, '尚未读取无日期产能，当前结论未知')
  assert.equal(unknown.noDateTimeLabel, '理论用时未知')
})

test('route and detail render the same exact server labels and escape business text', async () => {
  const value = noDate()
  value.displayLabels.timeSourceLabel = '服务端原文 <img src=x onerror=alert(1)>'
  const detail = await html(section('<section v-if="context.noDateCapacity"'), { context: { noDateCapacity: value }, readState: 'loaded' })
  const route = await html(section('<section v-if="row.noDateCapacity"'), { row: { noDateCapacity: value }, routeReadState: 'loaded' })
  for (const rendered of [detail, route]) {
    assert.match(rendered, /0\.5123456789/)
    assert.match(rendered, /&lt;img/)
    assert.doesNotMatch(rendered, /<img|CAPACITY_SOURCE_RULES_HEADER|MATCHED/)
  }
})

test('route and detail preserve exact native step/capacity time references without selecting, totaling or replacing unknown with zero', async () => {
  const value = special('NOT_SEPARATELY_MEASURED_VERIFIED', 'NOT_SEPARATELY_MEASURED_VERIFIED', '不单独计量，保留原正式时间参考')
  value.timeReferences = { step: null, standardCapacities: [
    { standardCapacityId: 233, preparationDays: '0.1000', transferDays: '0.1000', timeUnit: 'DAY' }] }
  const before = JSON.stringify(value)
  const templates = [[section('<section v-if="context.noDateCapacity"'), () => ({ context: { noDateCapacity: value }, readState: 'loaded' })],
    [section('<section v-if="row.noDateCapacity"'), () => ({ row: { noDateCapacity: value }, routeReadState: 'loaded' })]]
  for (const [template, data] of templates) {
    const rendered = await html(template, data())
    assert.match(rendered, /标准产能 233 原始参考：准备 0\.1000；转运 0\.1000；单位 天/)
    assert.match(rendered, /路线步骤原始参考：准备 未知；转运 未知；单位 未知/)
    assert.match(rendered, /以下参考值不计入准确总工期/)
    assert.doesNotMatch(rendered, /0\.2000|合计.*0\.2|单位 DAY/)
  }
  assert.equal(JSON.stringify(value), before)
  value.timeReferences = { step: { preparationDays: '0.2222', transferDays: null, timeUnit: 'DAY' }, standardCapacities: [] }
  for (const [template, data] of templates) {
    const rendered = await html(template, data())
    assert.match(rendered, /路线步骤原始参考：准备 0\.2222；转运 未知；单位 天/)
    assert.match(rendered, /标准产能原始参考未提供，准备和转运时间未知/)
  }
  value.timeReferences = { step: null, standardCapacities: [] }
  for (const [template, data] of templates) {
    const rendered = await html(template, data())
    assert.match(rendered, /路线步骤原始参考：准备 未知；转运 未知；单位 未知/)
    assert.doesNotMatch(rendered, /准备 0(?:；|\s)|转运 0(?:；|\s)/)
  }
})

test('one original batch GET supplies the current table and an explicit refresh issues exactly one fresh GET', async () => {
  const calls = []
  const value = routeFixture()
  const state = runtime({ getOperationWorkloadSources: async args => { calls.push(args); return value } })
  assert.equal(await state.loadRouteOverview(), true)
  assert.equal(await state.loadRouteOverview(), true)
  assert.deepEqual(calls, Array(2).fill({ routeOverview: 1, includeWorkloads: 1, productionPlanId: scope.productionPlanId }))
  assert.equal(state.strictFacts.value.route.rows[0].noDateCapacity, state.routeFacts.value.routeConfiguration.rows[0].noDateCapacity)
  assert.equal(state.buildDiagnostics().strictFacts, state.strictFacts.value)
  assert.equal(state.buildDiagnostics().strictServerFacts, state.strictFacts.value)
})

test('late responses cannot restore another selected plan, and failed refresh clears formerly matched facts', async () => {
  let complete
  const state = runtime({ getOperationWorkloadSources: () => new Promise(resolve => { complete = resolve }) })
  const reading = state.loadRouteOverview()
  await settle()
  assert.equal(typeof complete, 'function', 'The real lifecycle has started its original GET before selection changes')
  state.selectedRoutePlanId.value = '9999'
  complete(routeFixture())
  assert.equal(await reading, false)
  assert.equal(state.routeFacts.value, null)
  const current = runtime({ getOperationWorkloadSources: async () => routeFixture() })
  assert.equal(await current.loadRouteOverview(), true)
  current.props.parentReadStatus = 'loaded'
  const failed = routeFixture(); failed.routeConfiguration.rows[0].noDateCapacity.scope.productionPlanId += 1
  const broken = runtime({ getOperationWorkloadSources: async () => failed })
  broken.routeFacts.value = routeFixture()
  assert.equal(await broken.loadRouteOverview(), false)
  assert.equal(broken.routeFacts.value, null)
  assert.equal(broken.strictFacts.value.passed, false)
  assert.equal(broken.strictFacts.value.route.noDateReadState, 'read_failed')
  assert.equal(broken.strictFacts.value.route.rows, null)
})

test('component unregisters its own diagnostic provider and legacy reads do not claim no-date facts loaded', () => {
  const registrations = [], removals = []
  const actions = { register: owner => registrations.push(owner), unregister: owner => removals.push(owner) }
  const old = runtime({}, { observability: actions })
  const next = runtime({}, { observability: actions })
  old.unmount.forEach(fn => fn())
  assert.equal(registrations.length, 2)
  assert.equal(removals[0], registrations[0])
  assert.notEqual(removals[0], registrations[1])
  const legacy = routeFixture()
  delete legacy.routeConfiguration.noDateCapacityIncluded
  delete legacy.routeConfiguration.noDateCapacityContract
  legacy.routeConfiguration.rows.forEach(row => { delete row.noDateCapacity })
  actual.validateRouteFacts(legacy, planFor(legacy), scope.companyId)
  next.routeFacts.value = legacy
  next.routeReadState.value = 'loaded'
  assert.equal(next.strictFacts.value.route.noDateReadState, 'not_read')
  assert.ok(next.strictFacts.value.route.rows.every(row => row.noDateCapacity === null))
})

test('fresh complete native overview and detail pass actual validators and retain every no-date fact unchanged',
  { skip: !process.env.PCE_NO_DATE_CAPACITY_NATIVE_FACTS_PATH }, () => {
    const capture = JSON.parse(readFileSync(process.env.PCE_NO_DATE_CAPACITY_NATIVE_FACTS_PATH, 'utf8'))
    const route = capture.routeResponse?.data ?? capture.routeResponse
    const detail = capture.detailResponse?.data ?? capture.detailResponse
    assert.ok(route?.routeConfiguration && detail?.context, 'Capture both complete current native responses')
    const before = JSON.stringify({ route, detail })
    const plan = planFor(route)
    assert.equal(route.routeConfiguration.noDateCapacityIncluded, true)
    assert.equal(detail.context.noDateCapacityIncluded, true)
    actual.validateRouteFacts(route, plan, route.routeConfiguration.scope.companyId)
    actual.validateFacts(detail)
    actual.validateRequestedScope(detail, { operationId: detail.configuration.operationId,
      productionPlanId: detail.context.scope.productionPlanId, routingStepId: detail.context.scope.routingStepId })
    assert.equal(JSON.stringify({ route, detail }), before)
    assert.equal(route.routeConfiguration.rows.length, 28)
  })

test('captured native positive consumption preparation requires its exact persisted proof, saved load and current no-date facts',
  { skip: !process.env.PCE_NO_DATE_CAPACITY_NATIVE_CONTEXT_PATH }, () => {
    const context = JSON.parse(readFileSync(process.env.PCE_NO_DATE_CAPACITY_NATIVE_CONTEXT_PATH, 'utf8'))
    assert.equal(context.inputPreparation.statusCode, 'POSITIVE_CAPACITY_REFERENCE_RECORDED')
    const parameters = { operationId: context.scope.operationId, productionPlanId: context.scope.productionPlanId,
      routingStepId: context.scope.routingStepId }
    const wrapped = value => ({ configuration: { operationId: context.scope.operationId },
      catalog: { companyId: context.scope.companyId }, context: value })
    const before = JSON.stringify(context)
    actual.validateRequestedScope(wrapped(context), parameters)
    assert.equal(JSON.stringify(context), before, 'The validator must not rewrite native values or proofs')
    for (const field of ['producerRuleId', 'manufacturingModeId', 'workCenterId']) {
      const allowed = clone(context)
      allowed.inputPreparation[field] = context.inputPreparation.capacityConsumptionReference.selectedCapacityFact.workCenterId
      actual.validateRequestedScope(wrapped(allowed), parameters)
    }
    const corruptions = [
      value => { value.inputPreparation.sourceQuantity = null },
      value => { value.inputPreparation.inputQuantity = '0' },
      value => { value.inputPreparation.capacityQuantity = '0' },
      value => { value.inputPreparation.capacityBusinessValue = '0' },
      value => { value.inputPreparation.readyForScheduling = true },
      value => { value.inputPreparation.standardCapacityId = value.inputPreparation.capacityConsumptionReference.capacityReference.standardCapacityId },
      value => { value.inputPreparation.capacityConsumptionReference.consumer = 'DATE_SCHEDULING' },
      value => { value.inputPreparation.capacityConsumptionReference.formalConsumptionValidated = false },
      value => { value.inputPreparation.capacityConsumptionReference.recordId += 1 },
      value => { value.inputPreparation.capacityConsumptionReference.auditIds[0] += 1 },
      value => { value.inputPreparation.capacityConsumptionReference.grantsAllocation = true },
      value => { value.inputPreparation.capacityConsumptionReference.referenceHash = 'f'.repeat(64) },
      value => { value.inputPreparation.capacityConsumptionReference.exactScope.baselineId += 1 },
      value => { value.inputPreparation.capacityConsumptionReference.savedLoadReference.uomId += 1 },
      value => { value.inputPreparation.capacityConsumptionReference.sharedTimeSource.countPolicy = 'ONCE_PER_ALLOCATION' },
      value => { value.inputPreparation.businessBasis.entries.forEach(entry => { delete entry.capacityConsumptionReference }) },
      value => { delete value.inputPreparation.capacityConsumptionReference },
      value => { value.savedAllocations.quantity = '0' },
      value => { value.savedAllocations.uomId += 1 },
      value => { value.savedAllocations.items[0].allocationId += 1 },
      value => { value.savedAllocations.items[0].operationRequirementId += 1 },
      value => { value.noDateCapacity.capacityConsumptionReference.referenceHash = 'e'.repeat(64) },
      value => { value.noDateCapacity.scope.routingStepId += 1 },
      value => { value.noDateCapacity.capacityMatches[0].standardCapacityId += 1 },
      value => { value.noDateCapacity.capacityMatches[0].preparationDays = '0' },
      value => { value.noDateCapacity.capacityMatches[0].timeSelection.preparation.selectedDays = '0' },
      value => { value.noDateCapacity.capacityMatches[0].timeSelection.transfer.timeUnit = 'HOUR' },
      value => { value.inputPreparation.conditionalExecution = { triggerStatus: 'WAITING_TRIGGER' } },
      value => { value.inputPreparation.quantityPolicy = { measurementMode: 'NOT_SEPARATELY_MEASURED' } },
      value => { value.inputPreparation.businessBasis.conditionalExecution = { triggerStatus: 'WAITING_TRIGGER' } },
      value => { value.inputPreparation.businessBasis.quantityPolicy = { measurementMode: 'NOT_SEPARATELY_MEASURED' } },
      value => { value.inputPreparation.context.contractVersion = 'PCE-OPERATION-QUANTITY-POLICY-V1' },
    ]
    for (const mutate of corruptions) {
      const damaged = clone(context)
      mutate(damaged)
      assert.throws(() => actual.validateRequestedScope(wrapped(damaged), parameters),
        error => error instanceof Error && /当前|准备记录|引用/.test(error.message))
    }
    const legacy = clone(context)
    delete legacy.inputPreparation.capacityConsumptionReference
    legacy.inputPreparation.businessBasis.entries.forEach(entry => { delete entry.capacityConsumptionReference })
    legacy.inputPreparation.statusCode = 'RECORDED'
    assert.throws(() => actual.validateRequestedScope(wrapped(legacy), parameters), /准备记录与本次准确范围/)
    Object.assign(legacy.inputPreparation, { sourceQuantity: null, inputQuantity: null, capacityQuantity: null })
    assert.throws(() => actual.validateRequestedScope(wrapped(legacy), parameters), /未证明当前产能裁决/)
    assert.equal(JSON.stringify(context), before, 'All fault mutations stay in separate in-memory copies')
  })
