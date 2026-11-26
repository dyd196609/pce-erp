import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

// Only synthetic promises and Vue's in-memory renderer: no browser, HTTP or DB.
const repo = process.cwd()
const frontend = path.resolve(process.env.PCE_FRONTEND_SOURCE_ROOT || path.join(repo, 'frontend'))
const require = createRequire(path.join(repo, 'frontend/package.json'))
const Vue = require('vue')
const { parse, compileScript, compileTemplate } = require('@vue/compiler-sfc')
const { compile, baseParse } = require('@vue/compiler-dom')
const { renderToString } = require('@vue/server-renderer')
const runtimeModule = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/pceEnterpriseListContract.js')))
const helperSource = fs.readFileSync(path.join(frontend, 'src/meta/runtime/componentReadLifecycle.js'), 'utf8')
const { createComponentReadLifecycle, componentReadUrl } = await import(`data:text/javascript;base64,${Buffer.from(helperSource).toString('base64')}`)
const viewHelperSource = fs.readFileSync(path.join(frontend, 'src/meta/runtime/operationWorkloadViewContext.js'), 'utf8')
const { createOperationWorkloadViewMemory, reconcileOperationWorkloadView, OPERATION_WORKLOAD_VIEW_KEY } = await import(`data:text/javascript;base64,${Buffer.from(viewHelperSource).toString('base64')}`)
const { explicitTraceConditions } = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/sourceFormatMaintenanceForm.js')))
const { factLoadFailureFromError } = await import(pathToFileURL(path.join(repo, 'frontend/src/meta/runtime/pceFactLoadContract.js')))
const parentSource = fs.readFileSync(path.join(frontend, 'src/meta/components/ProductionFoundationMaintenance.vue'), 'utf8')
const panelSource = fs.readFileSync(path.join(frontend, 'src/meta/components/OperationWorkloadSourcePanel.vue'), 'utf8')
const tableSource = fs.readFileSync(path.join(frontend, 'src/meta/components/PceEnterpriseListTable.vue'), 'utf8')
const panel = parse(panelSource).descriptor
const parent = parse(parentSource).descriptor
const panelScript = panel.scriptSetup.content.replace(/^import .*$/gm, '')
const exposed = `return { selectedOperationId, selectedPlanId, selectedRoutingStepId, selectedRoutePlanId,
  serverFacts, routeFacts, readState, routeReadState, readError, routeReadError, form, catalog, context,
  readDiagnostics, busy, canSave, loadSources, loadRouteOverview, refreshSourceFacts, routeRows,
  validateFacts, validateRequestedScope, quantityText, inputPreparation, routeExpandedStepIds, expandedTraceKeys,
  viewContextNotices, traceKey, traceExpanded, rememberTraceExpansion, rememberRouteExpansion, navigationSnapshot, quantityCards,
  changeOperation, changePlan, openRouteStep }`
const executePanel = new Function('computed', 'nextTick', 'onBeforeUnmount', 'reactive', 'ref', 'watch', 'defineProps',
  'defineEmits', 'pdeApi', 'createPceEnterpriseListContract', 'usePceEnterpriseListRuntime', 'explicitTraceConditions',
  'getTabAuthEpoch', 'readTabIdentity', 'createComponentReadLifecycle', 'componentReadUrl',
  'createOperationWorkloadViewMemory', 'reconcileOperationWorkloadView', `${panelScript}\n${exposed}`)
const contract = 'PCE-OPERATION-WORKLOAD-SOURCE-V1'
function sourceFacts(params = {}) {
  return { contractVersion: contract, factSource: 'server', operations: [{ id: 407, label: '隔离工序', calculation_uom_id: 17 }],
    configuration: { operationId: params.operationId, sources: [], statusLabel: '正式读取' },
    catalog: { companyId: 29, producers: [], manufacturingModes: [], productTypes: [], standardCapacities: [], workCenters: [],
      productionPlans: [{ id: 381, label: '隔离计划', routingSteps: [{ id: 492, operationId: 407 }],
        allRoutingSteps: [{ id: 492, operationId: 407 }], manufacturingOutputId: 31, routingVersionId: 32 }],
      configureAuthorization: { allowed: false, statusLabel: '只读账号' } },
    ...(params.productionPlanId ? { context: { scope: { productionPlanId: params.productionPlanId,
      routingStepId: params.routingStepId, operationId: params.operationId },
      formalRequirements: { statusLabel: '正式需求有效', items: [{ operationRequirementId: 8271, sourceFactId: 9281,
        quantity: '4.230000', uomLabel: '平方米', sourceSnapshot: { immutableProof: 'independent-current-hash' } }] },
      savedAllocations: { statusLabel: '已保存负荷', quantity: '4.230000', uomLabel: '平方米', items: [{ allocationId: 172, operationRequirementId: 8271 }] },
      sourceCandidates: { statusLabel: '来源有效', items: [] }, sourceConfiguration: { statusLabel: '来源方案有效' } } } : {}) }
}
function panelRuntime(api, extra = {}, watchers = true, hooks = {}) {
  const props = Vue.reactive({ operations: [], mode: 'view', refreshKey: 0, invalidateKey: 0, parentReadStatus: 'loaded', ...extra })
  const state = executePanel(Vue.computed, Vue.nextTick, hooks.onBeforeUnmount || (() => {}), Vue.reactive, Vue.ref,
    watchers ? Vue.watch : (() => {}), () => props, () => () => {}, api,
    runtimeModule.createPceEnterpriseListContract, runtimeModule.usePceEnterpriseListRuntime, explicitTraceConditions,
    () => hooks.auth?.epoch || 1, () => ({ userId: hooks.auth?.userId || 8, companyId: hooks.auth?.companyId || 29 }),
    createComponentReadLifecycle, componentReadUrl,
    options => createOperationWorkloadViewMemory({ ...options, ...(hooks.storage ? { storage: () => hooks.storage } : {}) }), reconcileOperationWorkloadView)
  return { props, ...state }
}
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const settle = async () => { await Promise.resolve(); await Promise.resolve(); await Vue.nextTick(); await Promise.resolve() }
function entityFacts(entity, rows = [], tenantId = '29') {
  return { facts: { [entity]: rows }, currentEntityAuthorization: { allowed: true }, factSource: 'server',
    factLoadFacts: { factLoadStatus: rows.length ? 'loaded' : 'empty_valid', tenantId, batchId: 'synthetic-current' } }
}
function parentRuntime(pdeApi, enterpriseMasterDataApi, scope = { current: 'actor8-company29-epoch1' }) {
  const states = Object.fromEntries(['loadStatus', 'workloadSourceInvalidateKey', 'currentEntityAuthorization', 'operationFacts',
    'targetedFacts', 'facts', 'entityReadStates', 'operationReferencesState', 'operationReferencesError', 'message',
    'operationPanelScope', 'factLoadFacts', 'maintenanceFormOpen', 'workloadSourceRefreshKey', 'saveError'].map(name => [name, Vue.ref(null)]))
  Object.assign(states, { selectedEntity: Vue.ref('operations'), loadStatus: Vue.ref('idle'),
    workloadSourceInvalidateKey: Vue.ref(0), workloadSourceRefreshKey: Vue.ref(0), maintenanceFormOpen: Vue.ref(false),
    entityReadStates: Vue.ref({}), facts: Vue.ref({}), factLoadFacts: Vue.ref({}) })
  const records = Vue.ref([])
  const body = parent.scriptSetup.content.slice(parent.scriptSetup.content.indexOf('function loadFacts()'),
    parent.scriptSetup.content.indexOf('async function loadOtherEntityFacts()'))
  const count = parent.scriptSetup.content.slice(parent.scriptSetup.content.indexOf('const currentRecordCount ='),
    parent.scriptSetup.content.indexOf('const latestTemplateVersion ='))
  const dependencies = { ...states, createComponentReadLifecycle, setReadDiagnostics: rows => { records.value = rows },
    readScope: () => scope.current, pdeApi, enterpriseMasterDataApi,
    definitions: { operations: { label: '工序' }, units: { label: '单位' } },
    requireSuccess: response => { if (response?.success === false) throw new Error('正式读取失败'); return response?.data ?? response },
    factLoadFailureFromError, nextTick: Vue.nextTick, loadOtherEntityFacts: () => { throw new Error('Unexpected other entity') },
    providerFailed: Vue.computed(() => states.loadStatus.value === 'failed'), computed: Vue.computed,
    currentRows: Vue.computed(() => states.operationFacts.value || []),
    rowsFor: entity => states.facts.value.facts?.[entity] || [] }
  const execute = new Function(...Object.keys(dependencies), `let activeFactLoadRequest = 0; let pendingOperationLoad = null;
    const reads = createComponentReadLifecycle({ context: () => JSON.stringify([readScope(), activeFactLoadRequest]), changed: setReadDiagnostics });
    ${body}\n${count}\nreturn {loadFacts, ensureOperationReferences, currentRecordCount, entityCountLabel, invalidateOtherEntityRead: () => {activeFactLoadRequest++}}`)
  return { ...states, records, scope, ...execute(...Object.values(dependencies)) }
}

test('actual parent and panel compile and retain the formal table, proof, timeout and lazy detail contracts', () => {
  for (const [name, descriptor] of [['parent', parent], ['panel', panel], ['table', parse(tableSource).descriptor]]) {
    assert.doesNotThrow(() => compileScript(descriptor, { id: name }))
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: name + '.vue', id: name }).errors, [])
  }
  assert.match(parentSource, /operationPanelInitialized && !operationSubview/)
  assert.match(parentSource, /v-show="loadStatus === 'loaded' && !providerFailed"/)
  assert.match(panelSource, /@clear-selection="routeSelectedRows = \[\]"/)
  assert.match(panelSource, /validateInputPreparation\(current.inputPreparation/)
  assert.match(panelSource, /validateRouteFacts\(result, plan, companyId\)/)
  assert.match(tableSource, /expandRowKeys: \{ type: Array, default: undefined \}/)
  assert.match(tableSource, /:expand-row-keys="resolvedExpandRowKeys"/)
  assert.match(tableSource, /\$emit\('expand-change', row, expandedRows\)/)
  assert.doesNotMatch(helperSource + panelSource, /XMLHttpRequest\.prototype|timeout\s*:\s*\d+|includeCatalog|compact:/)
})

test('real immediate setup watcher sees the initialized owner before calling the later-declared loadFacts function', async () => {
  const script = parent.scriptSetup.content
  const owner = 'let pendingOperationLoad = null'
  const watcherStart = script.indexOf('watch([() => route.fullPath, () => props.initialEntity]')
  const watcherEnd = script.indexOf('function resetForm()', watcherStart)
  const functionStart = script.indexOf('function loadFacts()')
  const functionEnd = script.indexOf('function readFoundationEntity(', functionStart)
  assert.ok(script.indexOf(owner) < watcherStart, 'The owner must initialize before the actual immediate watcher registration')
  const registration = script.slice(watcherStart, watcherEnd)
  const actualLoad = script.slice(functionStart, functionEnd)
  async function executeSetup(ownerBeforeWatcher) {
    const watches = []
    let calls = 0
    const execute = new Function('watch', 'route', 'props', 'selectedEntity', 'identityError', 'loadStatus',
      'syncPageState', 'readScope', 'reads', 'loadOperationFacts', 'loadOtherEntityFacts', `
      let activeFactLoadRequest = 0;
      ${ownerBeforeWatcher ? owner : ''}
      ${registration}
      ${ownerBeforeWatcher ? '' : owner}
      ${actualLoad}`)
    execute((getter, callback, options) => { assert.equal(options.immediate, true); watches.push(callback()) },
      { fullPath: '/foundation/master-data/operations' }, { initialEntity: 'operations' }, Vue.ref('operations'),
      Vue.ref(''), Vue.ref('idle'), () => {}, () => 'current-actor-company-epoch', { identity: () => 'current-read' },
      async () => { calls++; return true }, () => assert.fail('Wrong entity'))
    return { result: watches[0], calls }
  }
  const before = await executeSetup(false)
  await assert.rejects(before.result, /Cannot access 'pendingOperationLoad' before initialization/)
  assert.equal(before.calls, 0, 'Known failing setup never reaches the actual read')
  const after = await executeSetup(true)
  await after.result
  assert.equal(after.calls, 1)
})

test('operations first read has exactly one operations GET, one units GET, native targeted evidence and lazy maintenance references', async () => {
  const calls = []
  const state = parentRuntime({ productionFoundationA1: async entity => { calls.push(entity); return entityFacts(entity, [{ id: 701 }]) } },
    { group3AOperationTargetedRevalidation: async () => { calls.push('targeted'); return { focusRows: [] } } })
  assert.equal(state.currentRecordCount.value, null)
  assert.equal(state.entityCountLabel('work-centers'), '未读取')
  const first = state.loadFacts(), duplicate = state.loadFacts()
  assert.equal(first, duplicate)
  assert.equal(state.loadStatus.value, 'loading')
  assert.equal(await first, true)
  assert.deepEqual(calls, ['operations', 'units', 'targeted'])
  assert.equal(state.currentRecordCount.value, 1)
  assert.equal(state.entityCountLabel('work-centers'), '未读取')
  assert.equal(state.records.value.length, 3)
  assert.equal(await state.ensureOperationReferences(), true)
  assert.deepEqual(calls, ['operations', 'units', 'targeted', 'workshops', 'work-centers'])
  assert.equal(state.entityCountLabel('work-centers'), 1)
  await state.loadFacts()
  assert.deepEqual(calls.slice(-3), ['operations', 'units', 'targeted'], 'Completed reads are not reused as current facts')
})

test('empty-valid is zero; failed, unread and scope-changed facts remain unknown without silent targeted fallback', async () => {
  let fail = false
  const state = parentRuntime({ productionFoundationA1: async entity => entityFacts(entity) },
    { group3AOperationTargetedRevalidation: async () => { if (fail) throw new Error('targeted failed'); return { focusRows: [] } } })
  await state.loadFacts()
  assert.equal(state.currentRecordCount.value, 0)
  assert.equal(state.entityCountLabel('operations'), 0)
  fail = true
  assert.equal(await state.loadFacts(), false)
  assert.equal(state.currentRecordCount.value, null)
  assert.equal(state.entityCountLabel('operations'), '未知')
  assert.equal(state.operationFacts.value, null)
  assert.deepEqual(state.facts.value, {})
  const gate = deferred()
  const changed = parentRuntime({ productionFoundationA1: () => gate.promise }, { group3AOperationTargetedRevalidation: async () => ({ focusRows: [] }) })
  const pending = changed.loadFacts()
  changed.scope.current = 'different-actor-company-epoch'
  gate.resolve(entityFacts('operations'))
  assert.equal(await pending, false)
  assert.equal(changed.operationFacts.value, null)
})

test('private helper only shares pending identical context, keeps timings numeric/null and does not publish after dispose', async () => {
  let scope = 'actor-a-company-a-epoch1', now = 10, calls = 0
  const gate = deferred(), records = []
  const lifecycle = createComponentReadLifecycle({ context: () => scope, clock: () => now,
    resources: () => [], changed: value => records.push(value) })
  const task = { purpose: 'test-read', url: '/api/pde/a1-foundation/operations/', params: { id: 9 }, read: () => { calls++; return gate.promise } }
  const first = lifecycle.run(task)
  assert.equal(lifecycle.run(task), first)
  scope = 'actor-b-company-b-epoch2'
  const second = lifecycle.run(task)
  await settle()
  assert.equal(calls, 2)
  now = 32
  gate.resolve({ formal: 'not-cached' })
  await Promise.all([first, second])
  assert.equal(records.at(-1).at(-1).receiveAndParseMs, 22)
  assert.equal(records.at(-1).at(-1).encodedBodySize, null)
  assert.ok(!JSON.stringify(records).includes('not-cached'))
  await lifecycle.run(task)
  assert.equal(calls, 3)
  let onlyOne = []
  const bounded = createComponentReadLifecycle({ limit: 1, changed: value => { onlyOne = value } })
  await bounded.run({ ...task, read: async () => 1 })
  await bounded.run({ ...task, read: async () => 2 })
  assert.equal(onlyOne.length, 1)
  const late = deferred()
  const pending = lifecycle.run({ ...task, params: { id: 10 }, read: () => late.promise })
  const notifications = records.length
  lifecycle.dispose()
  late.resolve({})
  await pending
  assert.equal(records.length, notifications)
})

test('returning to operations does not reuse an owner invalidated by another entity request', async () => {
  const firstGate = deferred(), calls = []
  const state = parentRuntime({ productionFoundationA1: entity => {
    calls.push(entity)
    return calls.length <= 2 ? firstGate.promise.then(() => entityFacts(entity)) : Promise.resolve(entityFacts(entity))
  } }, { group3AOperationTargetedRevalidation: async () => ({ focusRows: [] }) })
  const old = state.loadFacts()
  await settle()
  state.selectedEntity.value = 'units'
  state.invalidateOtherEntityRead()
  state.selectedEntity.value = 'operations'
  const current = state.loadFacts()
  assert.notEqual(current, old)
  assert.equal(await current, true)
  firstGate.resolve()
  assert.equal(await old, false)
  assert.equal(state.loadStatus.value, 'loaded')
  assert.deepEqual(calls, ['operations', 'units', 'operations', 'units'])
})

test('panel coalesces pending same-scope reads and performs a fresh GET after completion', async () => {
  const calls = [], gate = deferred()
  const state = panelRuntime({ getOperationWorkloadSources: params => { calls.push(params); return gate.promise } }, {}, false)
  const first = state.loadSources(), duplicate = state.loadSources()
  assert.equal(first, duplicate)
  await settle()
  assert.equal(calls.length, 1)
  gate.resolve(sourceFacts())
  assert.equal(await first, true)
  assert.equal(await state.loadSources(), true)
  assert.equal(calls.length, 2)
  const diagnostics = state.readDiagnostics.value
  assert.equal(diagnostics.length, 2)
  assert.ok(diagnostics.every(row => row.url.endsWith('?action=operationWorkloadSources')))
  assert.ok(diagnostics.every(row => row.diagnosticOnly && row.vueCommitMs !== undefined))
})

test('changed operation, parent scope and authentication do not allow late results to restore old facts', async () => {
  const gate = deferred(), auth = { epoch: 1 }
  const state = panelRuntime({ getOperationWorkloadSources: () => gate.promise }, {}, false, { auth })
  state.selectedOperationId.value = '407'
  const pending = state.loadSources()
  await settle()
  auth.epoch = 2
  gate.resolve(sourceFacts({ operationId: 407 }))
  assert.equal(await pending, false)
  assert.equal(state.serverFacts.value, null)
})

test('real Vue mount preserves the panel instance and dirty draft across parent invalidation and same-tick successful refresh', async () => {
  const node = (type, text = '') => ({ type, text, style: {}, parent: null, children: [] })
  const renderer = Vue.createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] },
    parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
    insert(n, p, anchor) { n.parent = p; const index = anchor ? p.children.indexOf(anchor) : -1; if (index < 0) p.children.push(n); else p.children.splice(index, 0, n) },
    remove(n) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1) }, patchProp() {},
  })
  let state, instances = 0, unmounted = 0
  const calls = []
  const parentState = Vue.reactive({ loadStatus: 'loaded', providerFailed: false, selectedEntity: 'operations', operationPanelInitialized: true,
    operationSubview: false, currentRows: [], pageState: { mode: 'maintain' }, workloadSourceRefreshKey: 1, workloadSourceInvalidateKey: 0 })
  const start = parent.template.content.indexOf('<OperationWorkloadSourcePanel')
  const end = parent.template.content.indexOf('/>', start) + 2
  const actualBinding = parent.template.content.slice(start, end)
  const renderBinding = new Function('Vue', compile(actualBinding, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const child = { props: ['operations', 'mode', 'refreshKey', 'invalidateKey', 'parentReadStatus'],
    setup(props) {
      instances++
      const exposed = executePanel(Vue.computed, Vue.nextTick, fn => Vue.onBeforeUnmount(() => { unmounted++; fn() }), Vue.reactive, Vue.ref, Vue.watch,
        () => props, () => () => {}, { getOperationWorkloadSources: async params => { calls.push(params); return sourceFacts(params) } },
        runtimeModule.createPceEnterpriseListContract, runtimeModule.usePceEnterpriseListRuntime, explicitTraceConditions,
        () => 1, () => ({ userId: 8, companyId: 29 }), createComponentReadLifecycle, componentReadUrl,
        createOperationWorkloadViewMemory, reconcileOperationWorkloadView)
      state = exposed
      return () => Vue.h('div', { 'data-state': exposed.readState.value }, exposed.serverFacts.value ? 'formal-current' : 'unknown')
    } }
  const app = renderer.createApp({ setup: () => ({ ...Vue.toRefs(parentState), loadFacts: () => {} }), render: renderBinding })
  app.component('OperationWorkloadSourcePanel', child)
  app.mount(node('root'))
  await settle(); await settle()
  assert.equal(state.readState.value, 'loaded')
  assert.equal(calls.length, 1)
  state.form.reason = '尚未保存的草稿'
  state.selectedOperationId.value = '407'
  state.selectedPlanId.value = '381'
  state.selectedRoutingStepId.value = '492'
  parentState.loadStatus = 'loading'
  parentState.workloadSourceInvalidateKey++
  await Vue.nextTick()
  assert.equal(state.serverFacts.value, null)
  assert.equal(state.busy.value, true)
  assert.equal(state.canSave.value, false)
  parentState.loadStatus = 'loaded'
  parentState.workloadSourceRefreshKey++
  await settle(); await state.refreshSourceFacts()
  assert.equal(instances, 1)
  assert.equal(unmounted, 0)
  assert.equal(state.form.reason, '尚未保存的草稿')
  assert.equal(state.selectedPlanId.value, '381')
  assert.equal(state.readState.value, 'loaded')
  assert.equal(calls.length, 3)
  assert.deepEqual(calls[1], {}, 'Refresh validates the current authorized catalog before restoring detail IDs')
  assert.deepEqual(calls[2], { operationId: 407, productionPlanId: 381, routingStepId: 492 })
  app.unmount()
})

test('detail reading preserves native quantity, hashes, zero/null semantics and rejects wrong current scope', async () => {
  const calls = []
  let wrong = false
  const state = panelRuntime({ getOperationWorkloadSources: async params => {
    calls.push(params)
    const value = sourceFacts(params)
    if (wrong) value.context.scope.routingStepId = 493
    return value
  } }, {}, false)
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  assert.equal(await state.loadSources(), true)
  assert.equal(calls.length, 1)
  assert.equal(state.context.value.formalRequirements.items[0].sourceSnapshot.immutableProof, 'independent-current-hash')
  assert.equal(state.context.value.savedAllocations.quantity, '4.230000')
  assert.equal(state.quantityText(0), '0')
  assert.equal(state.quantityText(null), '未知')
  wrong = true
  assert.equal(await state.loadSources(), false)
  assert.equal(state.serverFacts.value, null)
  assert.equal(state.readState.value, 'read_failed')
})

test('current 28-row route owner deduplicates only pending reads and preserves the existing server projections on refresh', async () => {
  // Reuse the already governed synthetic 28-row contract, without rerunning its suite.
  const existing = fs.readFileSync(path.join(repo, 'frontend/tests/acceptance/operationWorkloadRouteFinal.test.mjs'), 'utf8')
  const fixtureDeclarations = existing.slice(existing.indexOf('const bucket ='), existing.indexOf('function runtime('))
  const { fixture, planOf } = new Function('contract', `${fixtureDeclarations}; return { fixture, planOf }`)(contract)
  const value = fixture(), gate = deferred(), calls = []
  const state = panelRuntime({ getOperationWorkloadSources: params => { calls.push(params); return gate.promise } }, {}, false)
  state.serverFacts.value = sourceFacts()
  state.serverFacts.value.catalog.companyId = 6099
  state.serverFacts.value.catalog.productionPlans = [planOf(value)]
  state.readState.value = 'loaded'
  state.selectedRoutePlanId.value = '5008'
  const first = state.loadRouteOverview(), duplicate = state.loadRouteOverview()
  assert.equal(first, duplicate)
  await settle()
  assert.equal(calls.length, 1)
  gate.resolve(value)
  assert.equal(await first, true)
  assert.equal(state.routeRows.value.length, 28)
  assert.equal(state.routeRows.value[0].savedQuantityText, '2.456700 平方米')
  assert.equal(state.routeRows.value[27].sourceBusinessLabel, '独立面积口径28')
  assert.equal(await state.loadRouteOverview(), true)
  assert.equal(calls.length, 2)
  assert.equal(state.routeReadState.value, 'loaded')
  assert.equal(state.readDiagnostics.value[1].url,
    '/api/pde/a1-foundation/operations/?routeOverview=1&includeWorkloads=1&productionPlanId=5008&action=operationWorkloadSources')
})

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}
test('same-tab view memory whitelists navigation only and rejects another user, company or login epoch', () => {
  const storage = memoryStorage(), identity = { userId: 8, companyId: 29, authEpoch: 3 }
  const memory = createOperationWorkloadViewMemory({ scope: () => identity, storage: () => storage })
  memory.write({ selectedOperationId: '407', selectedPlanId: 381, selectedRoutingStepId: '492', selectedRoutePlanId: '381',
    routeExpandedStepIds: ['492', 492, 'invalid'], expandedTraceKeys: ['source-1'], scrollTop: 987,
    serverFacts: { qualification: true, quantity: 999 }, form: { reason: 'unsaved' }, canSave: true })
  const saved = JSON.parse(storage.getItem(OPERATION_WORKLOAD_VIEW_KEY))
  assert.deepEqual(Object.keys(saved.navigation).sort(), ['expandedTraceKeys', 'routeExpandedStepIds', 'scrollTop',
    'selectedOperationId', 'selectedPlanId', 'selectedRoutePlanId', 'selectedRoutingStepId'].sort())
  assert.deepEqual(memory.read().routeExpandedStepIds, ['492'])
  assert.doesNotMatch(JSON.stringify(saved), /qualification|quantity|unsaved|canSave|serverFacts|form/)
  for (const key of ['userId', 'companyId', 'authEpoch']) {
    identity[key]++
    assert.equal(memory.read(), null)
    identity[key]--
  }
})

test('catalog reconciliation clears only unavailable or inactive selections and rejects a foreign company', () => {
  const navigation = { selectedOperationId: '407', selectedPlanId: '381', selectedRoutingStepId: '492', selectedRoutePlanId: '999',
    routeExpandedStepIds: ['492'], expandedTraceKeys: ['detail-proof'], scrollTop: 250 }
  const facts = sourceFacts()
  let result = reconcileOperationWorkloadView(navigation, facts, 29)
  assert.equal(result.value.selectedOperationId, '407')
  assert.equal(result.value.selectedPlanId, '381')
  assert.equal(result.value.selectedRoutingStepId, '492')
  assert.equal(result.value.selectedRoutePlanId, '')
  assert.match(result.reasons[0], /路线总览计划/)
  facts.catalog.productionPlans[0].routingSteps[0].isActive = false
  result = reconcileOperationWorkloadView({ ...navigation, selectedRoutePlanId: '381' }, facts, 29)
  assert.equal(result.value.selectedPlanId, '381')
  assert.equal(result.value.selectedOperationId, '407')
  assert.equal(result.value.selectedRoutingStepId, '')
  assert.match(result.reasons[0], /详情步骤/)
  facts.operations[0].is_active = false
  result = reconcileOperationWorkloadView(navigation, facts, 29)
  assert.equal(result.value.selectedOperationId, '')
  assert.equal(result.value.selectedPlanId, '381')
  assert.throws(() => reconcileOperationWorkloadView(navigation, facts, 30), /所属公司/)
})

test('browser reconstruction restores selected IDs and expansions only after current catalog, detail and route reads', async () => {
  const existing = fs.readFileSync(path.join(repo, 'frontend/tests/acceptance/operationWorkloadRouteFinal.test.mjs'), 'utf8')
  const declarations = existing.slice(existing.indexOf('const bucket ='), existing.indexOf('function runtime('))
  const { fixture, planOf } = new Function('contract', `${declarations}; return { fixture, planOf }`)(contract)
  const route = fixture(), storage = memoryStorage(), auth = { epoch: 2, userId: 8, companyId: 6099 }, calls = []
  const sample = params => {
    const value = sourceFacts(params), plan = planOf(route)
    plan.routingSteps = plan.allRoutingSteps
    value.catalog.companyId = 6099; value.catalog.productionPlans = [plan]
    value.operations = route.routeConfiguration.rows.map(row => ({ id: row.operationId, label: row.operationName }))
    return value
  }
  const api = { getOperationWorkloadSources: async params => { calls.push(params); return params.routeOverview ? route : sample(params) } }
  const original = panelRuntime(api, {}, true, { storage, auth })
  await original.refreshSourceFacts()
  original.selectedOperationId.value = '9821'; original.selectedPlanId.value = '5008'
  original.selectedRoutingStepId.value = '9021'; original.selectedRoutePlanId.value = '5008'
  await original.loadSources(); await original.loadRouteOverview()
  const trace = original.traceKey('formalRequirements', 8271)
  original.rememberTraceExpansion(trace, { target: { open: true } })
  original.rememberRouteExpansion({ routingStepId: 9021 }, [{ routingStepId: 9021 }])
  const before = calls.length
  const rebuilt = panelRuntime(api, {}, true, { storage, auth })
  assert.equal(rebuilt.serverFacts.value, null, 'Stored navigation cannot supply current facts')
  assert.equal(rebuilt.canSave.value, false)
  assert.equal(await rebuilt.refreshSourceFacts(), true)
  assert.deepEqual(calls.slice(before), [{}, { operationId: 9821, productionPlanId: 5008, routingStepId: 9021 },
    { routeOverview: 1, includeWorkloads: 1, productionPlanId: 5008 }])
  assert.equal(rebuilt.selectedRoutePlanId.value, '5008')
  assert.equal(rebuilt.selectedOperationId.value, '9821')
  assert.equal(rebuilt.selectedPlanId.value, '5008')
  assert.equal(rebuilt.selectedRoutingStepId.value, '9021')
  assert.deepEqual([...rebuilt.routeExpandedStepIds.value], ['9021'])
  assert.equal(rebuilt.traceExpanded(trace), true)
  assert.equal(rebuilt.context.value.savedAllocations.quantity, '4.230000')
  assert.equal(rebuilt.routeRows.value.length, 28)
})

test('refresh with an invalid route plan becomes idle without clearing valid detail or remaining permanently busy', async () => {
  const state = panelRuntime({ getOperationWorkloadSources: async params => sourceFacts(params) }, {}, false)
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  state.selectedRoutePlanId.value = '999'
  assert.equal(await state.refreshSourceFacts(), true)
  assert.equal(state.selectedRoutePlanId.value, '')
  assert.equal(state.routeReadState.value, 'idle')
  assert.equal(state.selectedPlanId.value, '381')
  assert.equal(state.selectedRoutingStepId.value, '492')
  assert.equal(state.busy.value, false)
  assert.match(state.viewContextNotices.value[0], /路线总览计划/)
})

test('refresh failures keep navigation but erase stale facts; foreign company and old login responses never restore facts', async () => {
  const state = panelRuntime({ getOperationWorkloadSources: async () => { throw new Error('catalog unavailable') } }, {}, false)
  state.serverFacts.value = sourceFacts({ operationId: 407, productionPlanId: 381, routingStepId: 492 })
  state.readState.value = 'loaded'
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  assert.equal(await state.refreshSourceFacts(), false)
  assert.equal(state.selectedPlanId.value, '381')
  assert.equal(state.serverFacts.value, null)
  assert.equal(state.readState.value, 'read_failed')
  assert.equal(state.canSave.value, false)
  const foreign = panelRuntime({ getOperationWorkloadSources: async () => { const value = sourceFacts(); value.catalog.companyId = 30; return value } }, {}, false)
  assert.equal(await foreign.refreshSourceFacts(), false)
  assert.match(foreign.readError.value, /所属公司/)
  assert.equal(foreign.serverFacts.value, null)
  const gate = deferred(), auth = { epoch: 1 }
  const changed = panelRuntime({ getOperationWorkloadSources: () => gate.promise }, {}, false, { auth })
  const pending = changed.refreshSourceFacts()
  await settle(); auth.epoch = 2; gate.resolve(sourceFacts())
  assert.equal(await pending, false)
  assert.equal(changed.serverFacts.value, null)
})

test('the actual native trace binding restores open state after loading unmounts its details element', async () => {
  const node = (type, text = '') => ({ type, text, props: {}, parent: null, children: [] })
  const renderer = Vue.createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] },
    parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
    insert(n, p, anchor) { n.parent = p; const index = anchor ? p.children.indexOf(anchor) : -1; if (index < 0) p.children.push(n); else p.children.splice(index, 0, n) },
    remove(n) { if (n.parent) { const index = n.parent.children.indexOf(n); if (index >= 0) n.parent.children.splice(index, 1) } },
    patchProp(n, key, oldValue, value) { n.props[key] = value },
  })
  const catalogGate = deferred(), calls = []
  const state = panelRuntime({ getOperationWorkloadSources: async params => {
    calls.push(params); if (!params.operationId) await catalogGate.promise; return sourceFacts(params)
  } }, {}, false)
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  state.serverFacts.value = sourceFacts({ operationId: 407, productionPlanId: 381, routingStepId: 492 }); state.readState.value = 'loaded'
  const start = panel.template.content.indexOf('<details :open="traceExpanded(traceKey(card.key')
  const actualDetails = panel.template.content.slice(start, panel.template.content.indexOf('</details>', start) + 10)
  const fragment = `<section v-if="readState === 'loaded' && context"><template v-for="card in quantityCards"><template v-for="(item,index) in card.facts?.items || []">${actualDetails}</template></template></section>`
  const render = new Function('Vue', compile(fragment, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const root = node('root'), app = renderer.createApp({ setup: () => state, render })
  app.mount(root)
  const details = () => { const found = []; const visit = n => { if (n.type === 'details') found.push(n); n.children.forEach(visit) }; visit(root); return found }
  assert.equal(details().length, 2)
  details()[0].props.onToggle({ target: { open: true } })
  await Vue.nextTick()
  assert.equal(details()[0].props.open, true)
  const pending = state.refreshSourceFacts()
  await Vue.nextTick()
  assert.equal(details().length, 0, 'The loading v-if really removed the native details node')
  assert.equal(state.serverFacts.value, null)
  catalogGate.resolve()
  assert.equal(await pending, true)
  await Vue.nextTick()
  assert.equal(details().length, 2)
  assert.equal(details()[0].props.open, true, 'The new native node receives the restored open binding')
  assert.deepEqual(calls, [{}, { operationId: 407, productionPlanId: 381, routingStepId: 492 }])
  app.unmount()
})

async function withViewWindow(run) {
  const previous = globalThis.window, listeners = new Set(), restored = []
  const view = { scrollY: 0, addEventListener: (type, callback) => { if (type === 'scroll') listeners.add(callback) },
    removeEventListener: (type, callback) => listeners.delete(callback),
    scrollTo: ({ top }) => { view.scrollY = top; restored.push(top) } }
  globalThis.window = view
  try { await run({ view, restored, scroll: top => { view.scrollY = top; listeners.forEach(callback => callback({ target: view })) } }) }
  finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous }
}

test('local route refresh preserves position while loading; selecting a different plan never restores the prior plan position', async () => {
  await withViewWindow(async ({ view, restored, scroll }) => {
    const existing = fs.readFileSync(path.join(repo, 'frontend/tests/acceptance/operationWorkloadRouteFinal.test.mjs'), 'utf8')
    const declarations = existing.slice(existing.indexOf('const bucket ='), existing.indexOf('function runtime('))
    const { fixture, planOf } = new Function('contract', `${declarations}; return { fixture, planOf }`)(contract)
    const firstRoute = fixture(), nextRoute = fixture(), gate = deferred(), calls = []
    nextRoute.routeConfiguration.scope.productionPlanId = 5009
    const state = panelRuntime({ getOperationWorkloadSources: async params => {
      calls.push(params); if (calls.length === 1) await gate.promise
      return params.productionPlanId === 5008 ? firstRoute : nextRoute
    } }, {}, false, { auth: { companyId: 6099 } })
    const nextPlan = planOf(nextRoute); nextPlan.id = 5009
    state.serverFacts.value = sourceFacts(); state.serverFacts.value.catalog.companyId = 6099
    state.serverFacts.value.catalog.productionPlans = [planOf(firstRoute), nextPlan]
    state.readState.value = 'loaded'; state.routeFacts.value = firstRoute; state.routeReadState.value = 'loaded'
    state.selectedRoutePlanId.value = '5008'; state.routeExpandedStepIds.value = ['9021']
    view.scrollY = 620
    const pending = state.loadRouteOverview(), duplicate = state.loadRouteOverview()
    assert.equal(pending, duplicate, 'Both existing route refresh controls retain the pending owner')
    scroll(0)
    assert.equal(state.routeFacts.value, null)
    gate.resolve(); assert.equal(await pending, true)
    assert.equal(view.scrollY, 620)
    assert.deepEqual(restored, [620])
    assert.deepEqual([...state.routeExpandedStepIds.value], ['9021'])
    assert.equal(state.navigationSnapshot().scrollTop, 620)
    state.selectedRoutePlanId.value = '5009'; view.scrollY = 480
    const switched = state.loadRouteOverview()
    scroll(0); assert.equal(await switched, true)
    assert.equal(view.scrollY, 0)
    assert.deepEqual(restored, [620], 'A plan change does not scroll back to the former plan view')
    assert.equal(calls.length, 2)
  })
})

test('detail reread and parent refresh restore their position; switching detail selection does not restore the former view', async () => {
  await withViewWindow(async ({ view, restored, scroll }) => {
    const gate = deferred(), calls = []
    const api = { getOperationWorkloadSources: async params => {
      calls.push(params); if (calls.length === 1) await gate.promise
      const value = sourceFacts(params)
      value.catalog.productionPlans.push({ id: 382, label: '另一个合法计划', routingSteps: [{ id: 493, operationId: 407 }] })
      return value
    } }
    const state = panelRuntime(api, {}, false)
    state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
    state.serverFacts.value = sourceFacts({ operationId: 407, productionPlanId: 381, routingStepId: 492 }); state.readState.value = 'loaded'
    view.scrollY = 710
    const pending = state.loadSources(); scroll(0); gate.resolve()
    assert.equal(await pending, true)
    assert.equal(view.scrollY, 710)
    state.selectedPlanId.value = '382'; state.selectedRoutingStepId.value = '493'; view.scrollY = 430
    const changed = state.loadSources(); scroll(0); assert.equal(await changed, true)
    assert.equal(view.scrollY, 0)
    assert.deepEqual(restored, [710])
    // The real parent hides its child before refreshKey starts the next source GET.
    const parentDriven = panelRuntime({ getOperationWorkloadSources: async params => sourceFacts(params) })
    await parentDriven.refreshSourceFacts()
    scroll(855)
    parentDriven.props.parentReadStatus = 'loading'; parentDriven.props.invalidateKey++
    scroll(0)
    assert.equal(parentDriven.navigationSnapshot().scrollTop, 855)
    parentDriven.props.parentReadStatus = 'loaded'; parentDriven.props.refreshKey++
    await settle(); assert.equal(await parentDriven.refreshSourceFacts(), true)
    assert.equal(view.scrollY, 855)
  })
})

test('identity change reason survives the first successful reconciliation and clears on the following ordinary refresh', async () => {
  const auth = { epoch: 1 }, state = panelRuntime({ getOperationWorkloadSources: async params => sourceFacts(params) }, {}, false, { auth })
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  auth.epoch = 2
  assert.equal(await state.refreshSourceFacts(), true)
  assert.equal(state.selectedOperationId.value, '')
  assert.equal(state.selectedPlanId.value, '')
  assert.match(state.viewContextNotices.value[0], /当前账号、公司或登录上下文已变化/)
  assert.equal(await state.refreshSourceFacts(), true)
  assert.deepEqual([...state.viewContextNotices.value], [])
})

test('the real wrapper row identity mapping keeps Element Plus expansion open after raw-key event readback', async () => {
  const tableScript = parse(tableSource).descriptor.scriptSetup.content
  const identity = tableScript.slice(tableScript.indexOf('function resolveRowIdentity('), tableScript.indexOf('function clearSort('))
  const mapping = tableScript.slice(tableScript.indexOf('const resolvedExpandRowKeys = computed('), tableScript.indexOf('const actionRuntime = computed('))
  assert.ok(identity && mapping, 'Exercise the actual wrapper functions, without a second identity implementation')
  const setupMapping = new Function('computed', 'props', 'pagedRows', `${identity}\n${mapping}\nreturn { resolveRowIdentity, resolvedExpandRowKeys, pagedRows }`)
  const useExpand = require(path.join(repo, 'frontend/node_modules/element-plus/lib/components/table/src/store/expand.js')).default
  const node = (type, text = '') => ({ type, text, props: {}, parent: null, children: [] })
  const renderer = Vue.createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] },
    parentNode: n => n.parent, nextSibling: n => n.parent?.children[n.parent.children.indexOf(n) + 1] || null,
    insert(n, p, anchor) { n.parent = p; const index = anchor ? p.children.indexOf(anchor) : -1; if (index < 0) p.children.push(n); else p.children.splice(index, 0, n) },
    remove(n) { if (n.parent) { const index = n.parent.children.indexOf(n); if (index >= 0) n.parent.children.splice(index, 1) } },
    patchProp(n, key, oldValue, value) { n.props[key] = value },
  })
  const rows = [{ routingStepId: 806 }, { routingStepId: '807' }]
  const model = Vue.reactive({ rows, rowKey: 'routingStepId', keys: undefined, controlled: false })
  let expansion, wrapper
  const ElementPlusStoreProbe = {
    props: ['data', 'rowKey', 'expandRowKeys'], emits: ['expand-change'],
    setup(props) {
      const instance = Vue.getCurrentInstance()
      instance.store = { states: { rowExpandable: Vue.ref(null) }, assertRowKey: () => assert.equal(typeof props.rowKey, 'function') }
      expansion = useExpand({ data: Vue.toRef(props, 'data'), rowKey: Vue.toRef(props, 'rowKey') })
      // The installed Element Plus style helper has the same controlled-key watch.
      Vue.watchEffect(() => { if (props.expandRowKeys) expansion.setExpandRowKeys(props.expandRowKeys) })
      Vue.watch(() => props.data, expansion.updateExpandRows, { flush: 'sync' })
      return () => Vue.h('div', expansion.states.expandRows.value.map(row => Vue.h('span', props.rowKey(row))))
    },
  }
  const bindings = [':data="pagedRows"', ':row-key="resolveRowIdentity"', ':expand-row-keys="resolvedExpandRowKeys"', '@expand-change=']
    .map(anchor => tableSource.split('\n').find(line => line.trim().startsWith(anchor))?.trim())
  assert.ok(bindings.every(Boolean), 'Render the wrapper\'s actual table data, identity, expansion and event bindings')
  const render = new Function('Vue', compile(`<el-table ${bindings.join(' ')} />`, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const Wrapper = { props: ['tableRows', 'rowKey', 'expandRowKeys'], emits: ['expand-change'],
    setup(props) { wrapper = setupMapping(Vue.computed, props, Vue.computed(() => props.tableRows)); return wrapper }, render }
  const app = renderer.createApp({ render: () => Vue.h(Wrapper, {
    tableRows: model.rows, rowKey: model.rowKey, expandRowKeys: model.keys,
    onExpandChange: (row, expandedRows) => { if (model.controlled) model.keys = expandedRows.map(item => item[model.rowKey]) },
  }) })
  app.component('ElTable', ElementPlusStoreProbe)
  app.mount(node('root'))
  assert.equal(wrapper.resolvedExpandRowKeys.value, undefined)
  expansion.toggleRowExpansion(model.rows[0], true)
  await Vue.nextTick()
  assert.equal(expansion.isRowExpanded(model.rows[0]), true, 'Uncontrolled default retains native expansion')
  expansion.setExpandRowKeys(['806'])
  assert.equal(expansion.states.expandRows.value.length, 0, 'The installed Element Plus store reproduces the old raw-key failure')
  model.controlled = true; model.keys = [806, '807', 806, 'missing']
  await Vue.nextTick()
  assert.deepEqual([...wrapper.resolvedExpandRowKeys.value], ['routingStepId:806', 'routingStepId:807'])
  assert.equal(expansion.states.expandRows.value.length, 2)
  expansion.toggleRowExpansion(model.rows[0], false)
  await Vue.nextTick()
  assert.deepEqual([...model.keys], ['807'], 'Public event readback stays in raw row-key values')
  assert.equal(expansion.isRowExpanded(model.rows[1]), true)
  expansion.toggleRowExpansion(model.rows[0], true)
  await Vue.nextTick()
  assert.equal(expansion.isRowExpanded(model.rows[0]), true, 'Controlled raw-key readback no longer immediately collapses the row')
  const retained = [...model.keys]
  model.rows = [rows[1]]
  await Vue.nextTick()
  assert.deepEqual([...wrapper.resolvedExpandRowKeys.value], ['routingStepId:807'])
  assert.equal(expansion.states.expandRows.value.length, 1)
  assert.deepEqual([...model.keys], retained, 'Filtering affects rendered expansion identities without erasing navigation hints')
  model.rows = rows
  await Vue.nextTick()
  assert.equal(expansion.states.expandRows.value.length, 2, 'Restoring the current page/filter restores both valid expansions')
  model.rowKey = 'lineId'; model.rows = [{ lineId: 'A1' }, { lineId: 0 }]; model.keys = ['A1', 0]
  await Vue.nextTick()
  assert.deepEqual([...wrapper.resolvedExpandRowKeys.value], ['lineId:A1', 'lineId:0'])
  assert.equal(expansion.states.expandRows.value.length, 2, 'The mapping follows the configured rowKey for other callers')
  model.keys = undefined; model.controlled = false
  await Vue.nextTick()
  expansion.toggleRowExpansion(model.rows[0], false)
  await Vue.nextTick()
  assert.equal(wrapper.resolvedExpandRowKeys.value, undefined)
  assert.equal(expansion.states.expandRows.value.length, 1)
  app.unmount()
})

function actualTemplateElement(attribute, value) {
  let found = null
  const visit = node => {
    if (node.type === 1 && node.props.some(prop => prop.type === 6 && prop.name === attribute && prop.value?.content === value)) found = node
    if (!found) for (const child of node.children || []) { visit(child); if (found) break }
  }
  visit(baseParse(panel.template.content))
  assert.ok(found, `The actual panel has ${attribute}=${value}`)
  return found
}
async function renderActualTemplate(source, state, components = {}) {
  const render = new Function('Vue', compile(source, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ setup: () => state, render })
  app.component('PceBusinessStatus', { props: ['statusLabel'], render() { return Vue.h('strong', this.statusLabel) } })
  for (const [name, component] of Object.entries(components)) app.component(name, component)
  return renderToString(app)
}
function displayContext() {
  return {
    sourceConfiguration: { statusLabel: '当前正式来源规则已配置', sources: [{ ruleId: 7341, ruleCode: 'SRC-ISOLATED-B', ruleVersion: 'V17',
      ruleName: '完整隔离测试来源规则名称保留在原规则详情', sourceCanonicalField: 'ISOLATED_QUANTITY', producerVersion: 'V3',
      quantityExpression: 'source_quantity', quantityBasisLabel: '按正式来源数量', deduplicationLabel: '精确范围去重' }] },
    standardCapacityFacts: [{ id: 8842, quantity: '12.000000', uomLabel: '套', timeUnitLabel: '天', timeBasisQuantity: '2.000000',
      productTypeName: '隔离测试产品乙', productTypeCode: 'ISOLATED-B', statusLabel: '正式标准产能当前有效' }],
    formalRequirements: { statusCode: 'NOT_APPLICABLE', statusLabel: '当前计划对象正式不适用', items: [], quantitySummary: [],
      persistence: { readStatus: 'READ', recordCount: 0, recordIds: [], statusLabel: '正式需求持久化读取完成；尚未保存需求', quantityStatusLabel: '当前计划步骤不形成可用需求数量' } },
    savedAllocations: { statusCode: 'NOT_APPLICABLE', statusLabel: '当前计划对象正式不适用', items: [], quantity: null, uomLabel: null,
      persistence: { readStatus: 'READ', recordCount: 0, recordIds: [], statusLabel: '分配持久化读取完成；尚未保存分配', quantityStatusLabel: '当前计划步骤无可用已保存负荷' } },
  }
}

test('the actual original structure and all fourteen dropdown bindings remain in their original order with the source form directly visible', async () => {
  const template = panel.template.content
  const locations = ['data-section="route-source-overview"', 'class="operation-selector"', 'data-cell="source-configuration"',
    'data-section="plan-source-read"', 'class="quantity-states"', 'data-section="source-maintenance"'].map(value => template.indexOf(value))
  assert.ok(locations.every((value, index) => value >= 0 && (index === 0 || value > locations[index - 1])))
  assert.doesNotMatch(template + panel.styles.map(style => style.content).join(''), /current-formal-data|route-current-formal-data|current-step-formal-details/)
  const selections = []
  const visit = (node, ancestors = []) => {
    if (node.type === 1 && node.tag === 'select') {
      const binding = node.props.find(prop => prop.type === 7 && (prop.name === 'model' || prop.name === 'bind' && prop.arg?.content === 'value'))
      selections.push({ binding: binding?.exp?.content, ancestors, node })
    }
    for (const child of node.children || []) visit(child, node.type === 1 ? [...ancestors, node] : ancestors)
  }
  visit(baseParse(template))
  assert.deepEqual(selections.map(row => row.binding), ['selectedRoutePlanId', 'selectedOperationId', 'selectedPlanId', 'selectedRoutingStepId',
    'form.capacityMode', 'form[field.key]', "form.sourceSelectorMode || 'CATALOG'", "selectedTraceOption?.key || ''", 'condition.valueType',
    'condition.value', 'form.quantityBasis', 'form.basisUomId', 'form.scopeCode', 'form.routingContextKey'])
  const exactStep = selections.find(row => row.binding === 'selectedRoutingStepId')
  assert.ok(exactStep.ancestors.some(node => node.tag === 'label' && node.props.some(prop => prop.type === 7 && prop.name === 'if' && prop.exp?.content === 'matchingSteps.length > 1')))
  const draft = actualTemplateElement('data-section', 'source-maintenance')
  assert.equal(draft.tag, 'section')
  for (const row of selections.slice(4)) assert.equal(row.ancestors.some(node => node.tag === 'details'), false, row.binding)
  const heading = draft.children.find(node => node.type === 1 && node.tag === 'h5')
  const firstLabel = selections[4].ancestors.findLast(node => node.tag === 'label')
  const frame = draft.loc.source.slice(0, draft.loc.source.indexOf('>') + 1) + heading.loc.source + firstLabel.loc.source + '</section>'
  const markup = await renderActualTemplate(frame, { selectedOperationId: '4239', hasCapacityModes: true,
    form: { capacityMode: '' }, capacityModes: [{ value: 'ISOLATED', statusLabel: '正式产能承接选项' }], refreshResourceSelection: () => {} })
  assert.ok(markup.includes('<select'))
  assert.ok(markup.includes('正式产能承接选项'))
  assert.doesNotMatch(markup, /<details|可选）/)
  assert.match(draft.loc.source, /<form @submit\.prevent="saveSource">/)
  assert.match(draft.loc.source, /@click="previewSourceConfiguration"/)
  assert.match(draft.loc.source, /v-if="mode === 'maintain'" type="submit" :disabled="!canSave"/)
})

test('the original formal demand card directly renders the server five-set quantity with the original per-item source traceability', async () => {
  const value = displayContext()
  value.formalRequirements = { statusCode: 'EXISTS', statusLabel: '当前有效正式需求已保存', blockers: [],
    quantitySummary: [{ quantity: '5.000000', uomId: 19, uomLabel: '套' }],
    items: Array.from({ length: 5 }, (_, index) => ({ operationRequirementId: 941 + index, sourceFactId: 8941 + index,
      sourceCalculationId: 7345, quantity: '1.000000', uomLabel: '套' })) }
  value.savedAllocations = { statusCode: 'MISSING', statusLabel: '尚未保存分配', quantity: null, uomLabel: '套', items: [], blockers: [] }
  const cards = [{ key: 'formalRequirements', label: '正式工序需求', facts: value.formalRequirements },
    { key: 'savedAllocations', label: '计划已保存负荷', facts: value.savedAllocations }]
  const markup = await renderActualTemplate(actualTemplateElement('class', 'quantity-states').loc.source,
    { quantityCards: cards, selectedPlan: { id: 731, label: '隔离计划甲' }, selectedOperation: { id: 4239, label: '另一合法工序' },
      optionLabel: row => row.label, quantityText: value => value == null || value === '' ? '未知' : String(value),
      traceExpanded: () => false, traceKey: () => 'source-proof', reasonLabel: String })
  assert.ok(markup.includes('详情计划：隔离计划甲；工序：另一合法工序'))
  assert.ok(markup.includes('data-cell="formal-requirement-quantity-summary">5.000000 套'))
  assert.equal((markup.match(/1\.000000 套/g) || []).length, 5)
  for (const record of value.formalRequirements.items) {
    assert.ok(markup.includes(String(record.operationRequirementId)))
    assert.ok(markup.includes(String(record.sourceFactId)))
  }
  assert.ok(markup.includes('来源核算'))
  assert.ok(markup.includes('来源与保存追溯'))
  const saved = markup.slice(markup.indexOf('data-cell="savedAllocations"'))
  assert.ok(saved.includes('尚未保存分配'))
  assert.doesNotMatch(saved, /5\.000000|>数量未知<|>0(?:\.0+)? 套/)
})

test('the original route demand column shows server multi-unit demand independently from unsaved or zero allocations and independent plan scope', async () => {
  const state = panelRuntime({}, {}, false)
  const review = { applicabilityLabel: '当前对象正式适用', processingLabel: '正式读取', sourceBusinessLabel: '正式来源',
    formalRequirementStatusLabel: '当前正式需求已保存', formalRequirementCount: 3,
    formalRequirementQuantitySummary: [{ quantity: '5.000000', uomId: 19, uomLabel: '套' }, { quantity: '3.750000', uomId: 20, uomLabel: '米' }],
    allocationStatusLabel: '尚未保存分配', allocationCount: 0, savedQuantity: null, uomLabel: '套',
    coverageStatusLabel: '当前正式覆盖状态', blockers: [] }
  state.routeFacts.value = { routeConfiguration: { rows: [{ sequence: 1, operationName: '另一合法工序',
    sourceConfiguration: { sources: [] }, workloadReview: review }] } }
  let row = state.routeRows.value[0]
  assert.ok(row.formalRequirementLabel.includes('5.000000 套；3.750000 米'))
  assert.equal(row.savedQuantityText, '尚未保存分配')
  assert.doesNotMatch(row.savedAllocationLabel, /5\.000000|3\.750000/)
  const columns = ['formalRequirementLabel', 'savedQuantityText', 'savedAllocationLabel']
    .map(field => actualTemplateElement('prop', field).loc.source).join('')
  const markup = await renderActualTemplate(`<div>${columns}</div>`, {}, { ElTableColumn: {
    props: ['prop', 'label'], render() { return Vue.h('p', { 'data-field': this.prop }, `${this.label}：${row[this.prop]}`) },
  } })
  assert.ok(markup.includes('5.000000 套；3.750000 米'))
  assert.ok(markup.includes('尚未保存分配'))
  state.routeFacts.value.routeConfiguration.rows[0].workloadReview.savedQuantity = '0.000000'
  state.routeFacts.value.routeConfiguration.rows[0].workloadReview.uomLabel = '米'
  row = state.routeRows.value[0]
  assert.equal(row.savedQuantityText, '0.000000 米')
  assert.ok(row.formalRequirementLabel.includes('5.000000 套；3.750000 米'))
  state.routeFacts.value.routeConfiguration.rows[0].workloadReview.savedQuantity = null
  state.routeFacts.value.routeConfiguration.rows[0].workloadReview.allocationPersistenceLabel = '当前保存范围已读取0条；尚未保存分配'
  assert.equal(state.routeRows.value[0].savedQuantityText, '当前保存范围已读取0条；尚未保存分配')
  const scope = await renderActualTemplate(actualTemplateElement('data-section', 'route-overview-scope').loc.source,
    { selectedRoutePlanId: '732', selectedRoutePlan: { label: '独立路线计划乙' }, optionLabel: row => row.label })
  assert.ok(scope.includes('路线总览计划：独立路线计划乙'))
  assert.ok(scope.includes('详情生产计划由下方原下拉独立选择'))
})

test('the original source and standard-capacity detail regions retain server facts and persistence remains separate from applicability', async () => {
  const value = displayContext()
  value.standardCapacityFacts.push({ ...value.standardCapacityFacts[0], id: 8843, quantity: '0.000000', statusLabel: '正式零值产能' },
    { ...value.standardCapacityFacts[0], id: 8844, quantity: null, statusLabel: '标准产能未测定；数量为空' })
  const format = value => value == null || value === '' ? '未知' : String(value)
  const capacity = await renderActualTemplate(actualTemplateElement('data-section', 'current-standard-capacity-facts').loc.source,
    { context: value, quantityText: format })
  for (const text of ['12.000000 套／天', '0.000000 套／天', '未知 套／天', '基准 2.000000 天', '隔离测试产品乙',
    '正式标准产能当前有效', '正式零值产能', '标准产能未测定；数量为空']) assert.ok(capacity.includes(text), text)
  const rules = await renderActualTemplate(actualTemplateElement('data-cell', 'source-configuration').loc.source,
    { selectedOperationId: '4239', configuration: value.sourceConfiguration, traceExpanded: () => false, traceKey: () => 'source-rule',
      sourceInputText: source => `${source.sourceCanonicalField} / ${source.producerVersion}`,
      quantityContractText: source => `${source.quantityExpression}；${source.quantityBasisLabel}；${source.deduplicationLabel}`,
      quantityText: format, reasonLabel: String })
  assert.ok(rules.includes(value.sourceConfiguration.sources[0].ruleName))
  assert.ok(rules.includes('来源规则与数量口径'))
  const cards = await renderActualTemplate(actualTemplateElement('class', 'quantity-states').loc.source,
    { quantityCards: [{ key: 'formalRequirements', label: '正式工序需求', facts: value.formalRequirements },
      { key: 'savedAllocations', label: '计划已保存负荷', facts: value.savedAllocations }],
      selectedPlan: { label: '隔离计划乙' }, selectedOperation: { label: '另一合法工序' }, optionLabel: row => row.label,
      quantityText: format, traceExpanded: () => false, traceKey: () => 'proof', reasonLabel: String })
  assert.ok(cards.includes(value.formalRequirements.statusLabel))
  assert.ok(cards.includes(value.formalRequirements.persistence.statusLabel))
  assert.ok(cards.includes(value.savedAllocations.persistence.statusLabel))
  assert.doesNotMatch(cards, /不适用，不形成该项保存负荷|不适用，不形成该项数量/)
})

test('the original operation, detail-plan and route-step handlers retain their exact read scopes and independent plan selections', async () => {
  const calls = []
  const fixture = params => {
    const value = sourceFacts(params)
    value.operations.push({ id: 408, label: '另一合法工序' })
    value.catalog.productionPlans[0].routingSteps = [{ id: 492, operationId: 407 }, { id: 494, operationId: 408 }, { id: 495, operationId: 408 }]
    value.catalog.productionPlans.push({ id: 382, label: '另一详情计划', routingSteps: [{ id: 596, operationId: 408 }] })
    return value
  }
  const state = panelRuntime({ getOperationWorkloadSources: async params => { calls.push(params); return fixture(params) } }, {}, false)
  state.serverFacts.value = fixture({}); state.readState.value = 'loaded'
  state.selectedOperationId.value = '407'; state.selectedPlanId.value = '381'; state.selectedRoutingStepId.value = '492'
  state.selectedRoutePlanId.value = '999'
  state.selectedOperationId.value = '408'
  await state.changeOperation()
  assert.equal(state.selectedPlanId.value, '381')
  assert.equal(state.selectedRoutingStepId.value, '', 'Multiple matching steps retain the original explicit selector')
  assert.equal(state.selectedRoutePlanId.value, '999')
  assert.deepEqual(calls[0], { operationId: 408 })
  state.selectedRoutingStepId.value = '494'
  await state.loadSources()
  assert.deepEqual(calls[1], { operationId: 408, productionPlanId: 381, routingStepId: 494 })
  state.selectedPlanId.value = '382'
  await state.changePlan()
  assert.equal(state.selectedRoutingStepId.value, '596', 'A single matching step retains the original automatic selection')
  assert.equal(state.selectedRoutePlanId.value, '999')
  assert.deepEqual(calls[2], { operationId: 408, productionPlanId: 382, routingStepId: 596 })
  state.selectedRoutePlanId.value = '381'; state.routeReadState.value = 'loaded'
  const routeRow = { routingStepId: 492, operationId: 407 }
  state.routeFacts.value = { routeConfiguration: { scope: { productionPlanId: 381 }, rows: [routeRow] } }
  await state.openRouteStep(routeRow)
  assert.equal(state.selectedOperationId.value, '407')
  assert.equal(state.selectedPlanId.value, '381')
  assert.equal(state.selectedRoutingStepId.value, '492')
  assert.deepEqual(calls[3], { operationId: 407, productionPlanId: 381, routingStepId: 492 })
  assert.equal(calls.length, 4)
})
