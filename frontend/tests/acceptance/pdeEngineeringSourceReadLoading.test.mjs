import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(path.join(root, 'frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue'), 'utf8')
const api = fs.readFileSync(path.join(root, 'frontend/src/api/pde.js'), 'utf8')
const ref = value => ({ value })

function between(source, startText, endText) {
  const start = source.indexOf(startText)
  const end = source.indexOf(endText, start + startText.length)
  assert.ok(start >= 0 && end > start, `production declaration missing: ${startText}`)
  return source.slice(start, end)
}

// Use the same production-body extraction as pdeEngineeringWorkloadSummary.test.mjs.
// Neither the loading-state guards nor the API request are reimplemented here.
function computedBody(name) {
  const declaration = `const ${name} = computed(() => {`
  const start = page.indexOf(declaration)
  assert.ok(start >= 0, `production computed missing: ${name}`)
  const bodyStart = start + declaration.length
  return page.slice(bodyStart, page.indexOf('\n})', bodyStart))
}

const factsNames = ['activeDraft', 'engineeringWorkloadReadState', 'engineeringWorkloadLoadedScope',
  'engineeringWorkloadScope', 'workshopView', 'loading', 'loadError', 'versionStale',
  'calculationDetailLoading', 'calculationDetailError', 'activeCalculation', 'selectedOrder']
const factsGuard = new Function(...factsNames, computedBody('engineeringWorkloadFacts'))
const summaryGuard = new Function('engineeringWorkloadFacts', 'workshopView', computedBody('engineeringWorkloadSummary'))

function visibleSummary(draft, { state = 'loaded', loadedScope = 'SIM-SCOPE-A', scope = 'SIM-SCOPE-A' } = {}) {
  const facts = factsGuard(ref(draft), ref(state), ref(loadedScope), ref(scope), ref('wood'),
    ref(false), ref(''), ref(false), ref(false), ref(''), ref(null), ref({ salesOrderItemId: 71 }))
  return summaryGuard(ref(facts), ref('wood'))
}

function apiMethod(request) {
  const method = between(api, '  engineeringDesignCalculationContext(', '  saveEngineeringDraft(')
  return new Function('request', `return ({\n${method}\n}).engineeringDesignCalculationContext`)(request)
}

function serverSummary(readStatus = 'loaded') {
  return {
    contractVersion: 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1', factSource: 'server', readStatus,
    workshopViews: { wood: { rows: [{ key: 'SIM-CURRENT-FACT', quantity: '1.939650' }] } },
    formalSavedFacts: [{ sourceFactId: 423, quantity: '0.554850' }],
    counts: { formalFactCount: 1, verifiedOperationRequirementCount: 13 },
  }
}

function draftLoader(request, { pageKey = 'input', draft = null } = {}) {
  const refs = {
    selectedOrder: ref({ salesOrderItemId: 71, sourceRecordId: 11, orderEngineeringInstanceId: 72, isSourceTrial: true }),
    activeBusinessPage: ref(pageKey), engineeringWorkloadScope: ref('SIM-SCOPE-A'),
    engineeringWorkloadReadState: ref('loaded'), engineeringWorkloadReadError: ref(''),
    engineeringWorkloadLoadedScope: ref('SIM-SCOPE-OLD'), drafts: ref(draft ? [draft] : []), activeDraftId: ref(''),
    pdeApi: { engineeringDesignCalculationContext: apiMethod(request) },
    unwrap: response => response, openDraft: () => {},
    explain: (error, fallback) => error?.message || fallback, ElMessage: { error: () => {} },
  }
  const declaration = between(page, 'async function loadDrafts(', '\nasync function loadUnboundDrafts()')
  const load = new Function(...Object.keys(refs), `let draftReadSequence = 0;\n${declaration}\nreturn loadDrafts`)(...Object.values(refs))
  return { load, refs }
}

function unboundLoader(request, { pageKey = 'input', query = { sourceRecord: '11' } } = {}) {
  const refs = {
    route: { query }, activeBusinessPage: ref(pageKey), engineeringWorkloadReadState: ref('loaded'),
    engineeringWorkloadLoadedScope: ref('SIM-SCOPE-OLD'), engineeringWorkloadReadError: ref('SIM-OLD-ERROR'),
    unboundDrafts: ref([{ id: 'SIM-OLD-DRAFT' }]), auxiliaryReadNotice: ref(''),
    pdeApi: { engineeringDesignCalculationContext: apiMethod(request) }, unwrap: response => response,
    explain: (error, fallback) => error?.message || fallback,
  }
  const declaration = between(page, 'async function loadUnboundDrafts() {', '\nfunction addDraftRow(')
  const load = new Function(...Object.keys(refs), `${declaration}\nreturn loadUnboundDrafts`)(...Object.values(refs))
  return { load, refs }
}

test('context API preserves the default and explicit-true full read contract', () => {
  const requests = []
  const read = apiMethod(config => { requests.push(config); return config })
  const expected = { method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/',
    params: { action: 'designCalculationContext', sourceRecordId: 11 }, timeout: 90000, meta: { module: 'pde' } }
  assert.deepEqual(read(11), expected)
  assert.deepEqual(read(11, { includeWorkloadSummary: true }), expected)
  assert.deepEqual(read(11, {}), expected)
  assert.equal(requests.length, 3)
})

test('explicit false keeps the existing GET URL, action, source identity and module', () => {
  const read = apiMethod(config => config)
  assert.deepEqual(read(11, { includeWorkloadSummary: false }), {
    method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/',
    params: { action: 'designCalculationContext', sourceRecordId: 11, includeWorkloadSummary: false },
    meta: { module: 'pde' },
  })
  assert.deepEqual(read('', { includeWorkloadSummary: false }).params,
    { action: 'designCalculationContext', includeWorkloadSummary: false })
  assert.equal(Object.hasOwn(read(11, { includeWorkloadSummary: 'false' }).params, 'includeWorkloadSummary'), false)
  assert.equal(Object.hasOwn(read(11, { includeWorkloadSummary: false }), 'timeout'), false)
})

test('only existing full-summary reads receive bounded local timeouts', () => {
  const draftMethod = between(api, '  engineeringDrafts(', '  engineeringDesignCalculationContext(')
  const detailMethod = between(api, '  engineeringCalculation(', '  executeEngineeringCalculation(')
  const reads = new Function('request', `return ({\n${draftMethod}\n${detailMethod}\n})`)(config => config)
  assert.deepEqual(reads.engineeringDrafts(72), { method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/',
    params: { action: 'draftCatalog', orderEngineeringInstanceId: 72 }, timeout: 60000, meta: { module: 'pde' } })
  assert.deepEqual(reads.engineeringCalculation(4), { method: 'GET', url: '/api/pde/a1-engineering/calculations/4/',
    timeout: 60000, meta: { module: 'pde' } })
  const context = apiMethod(config => config)
  for (const option of [undefined, {}, { includeWorkloadSummary: true }]) assert.equal(context(11, option).timeout, 90000)
  const input = context(11, { includeWorkloadSummary: false })
  assert.equal(input.params.includeWorkloadSummary, false)
  assert.equal(Object.hasOwn(input, 'timeout'), false)
  const sharedRequest = fs.readFileSync(path.join(root, 'frontend/src/api/request.js'), 'utf8')
  assert.match(sharedRequest, /timeout:\s*15000/)
  assert.equal((api.match(/timeout:\s*60000/g) || []).length, 2)
  assert.equal((api.match(/timeout:\s*90000/g) || []).length, 1)
})

test('input source read defers only the summary and invalidates old loaded facts', async () => {
  const calls = []
  const deferred = { contractVersion: 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1', factSource: 'server',
    readStatus: 'not_requested', counts: { formalFactCount: null, verifiedOperationRequirementCount: null } }
  const currentDraft = { id: 11, sourceVersion: 'SIM-CURRENT-VERSION', engineeringWorkloadSummary: deferred }
  const oldDraft = { id: 'SIM-OLD-DRAFT', engineeringWorkloadSummary: serverSummary() }
  const { load, refs } = draftLoader(async config => { calls.push(config); return { draft: currentDraft } }, { draft: oldDraft })
  await load()
  assert.equal(calls.length, 1)
  assert.equal(calls[0].params.includeWorkloadSummary, false)
  assert.equal(calls[0].params.sourceRecordId, 11)
  assert.equal(refs.drafts.value[0], currentDraft)
  assert.equal(refs.engineeringWorkloadReadState.value, 'not_requested')
  assert.equal(visibleSummary(currentDraft, { state: refs.engineeringWorkloadReadState.value,
    loadedScope: refs.engineeringWorkloadLoadedScope.value }), null)
  assert.equal(visibleSummary(oldDraft, { state: refs.engineeringWorkloadReadState.value,
    loadedScope: 'SIM-SCOPE-A' }), null)
  assert.equal(visibleSummary(currentDraft), null)
  assert.equal(deferred.counts.formalFactCount, null)
  assert.equal(deferred.counts.verifiedOperationRequirementCount, null)
})

test('the workload page requests the full summary and accepts only its current scope', async () => {
  const calls = []
  const summary = serverSummary()
  const currentDraft = { id: 11, engineeringWorkloadSummary: summary }
  const { load, refs } = draftLoader(async config => { calls.push(config); return { draft: currentDraft } }, { pageKey: 'scheduling' })
  await load()
  assert.equal(Object.hasOwn(calls[0].params, 'includeWorkloadSummary'), false)
  assert.equal(refs.engineeringWorkloadReadState.value, 'loaded')
  assert.equal(visibleSummary(currentDraft, { state: refs.engineeringWorkloadReadState.value,
    loadedScope: refs.engineeringWorkloadLoadedScope.value }), summary)
  assert.equal(visibleSummary(currentDraft, { loadedScope: 'SIM-SCOPE-OLD' }), null)
  assert.equal(visibleSummary(currentDraft, { scope: 'SIM-SCOPE-B' }), null)
})

test('a late source-trial response cannot restore an old scope or old full summary', async () => {
  let resolve
  const response = new Promise(done => { resolve = done })
  const oldDraft = { id: 'SIM-OLD-DRAFT', engineeringWorkloadSummary: serverSummary() }
  const { load, refs } = draftLoader(() => response, { pageKey: 'scheduling', draft: oldDraft })
  const pending = load()
  assert.equal(refs.engineeringWorkloadReadState.value, 'loading')
  assert.equal(refs.engineeringWorkloadLoadedScope.value, '')
  refs.engineeringWorkloadScope.value = 'SIM-SCOPE-B'
  refs.selectedOrder.value = { salesOrderItemId: 81, sourceRecordId: 21, isSourceTrial: true }
  resolve({ draft: { id: 11, engineeringWorkloadSummary: serverSummary() } })
  await pending
  assert.equal(refs.drafts.value[0], oldDraft)
  assert.equal(refs.engineeringWorkloadLoadedScope.value, '')
  assert.notEqual(refs.engineeringWorkloadReadState.value, 'loaded')
  assert.equal(visibleSummary(oldDraft, { state: refs.engineeringWorkloadReadState.value,
    loadedScope: refs.engineeringWorkloadLoadedScope.value, scope: refs.engineeringWorkloadScope.value }), null)
})

test('initial source loading requests the correct mode without marking deferred facts loaded', async () => {
  for (const pageKey of ['input', 'scheduling']) {
    const calls = []
    const currentDraft = { id: 11, engineeringWorkloadSummary: serverSummary('not_requested') }
    const { load, refs } = unboundLoader(async config => { calls.push(config); return { draft: currentDraft } }, { pageKey })
    await load()
    assert.equal(calls[0].params.sourceRecordId, '11')
    assert.equal(calls[0].params.includeWorkloadSummary, false)
    assert.equal(Object.hasOwn(calls[0], 'timeout'), false)
    assert.equal(refs.unboundDrafts.value[0], currentDraft)
    assert.equal(refs.engineeringWorkloadLoadedScope.value, '')
    assert.notEqual(refs.engineeringWorkloadReadState.value, 'loaded')
    assert.equal(visibleSummary(currentDraft, { state: refs.engineeringWorkloadReadState.value,
      loadedScope: refs.engineeringWorkloadLoadedScope.value }), null)
  }
})

test('initial page refresh preserves the server not-requested state after opening its draft', async () => {
  const summary = { contractVersion: 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1', factSource: 'server',
    readStatus: 'not_requested', counts: { formalFactCount: null } }
  const draft = { id: 11, sourceVersion: 'SIM-CURRENT-VERSION', engineeringWorkloadSummary: summary }
  const order = { salesOrderItemId: -11, sourceRecordId: 11, isSourceTrial: true, draft }
  const noop = () => {}
  const noRead = async () => {}
  const refs = {
    route: { query: { sourceRecord: '11' }, path: '/pde/engineering-calculations', fullPath: '/pde/engineering-calculations?sourceRecord=11' },
    loading: ref(false), loadError: ref(''), initialReadFailure: ref(null), auxiliaryReadNotice: ref(''), accessMode: ref(''),
    activeBusinessPage: ref('input'), configurationSubview: ref(false), resolveBusinessPage: () => 'input',
    resolveFoundationPageState: noop, permissionProfile: ref(null), loadPermissionProfile: async () => ({}),
    permissionAllowed: () => true, CALCULATION_VIEW_PERMISSION: 'SIM-VIEW', RULE_VIEW_PERMISSION: 'SIM-RULE-VIEW',
    readiness: ref({}), calculations: ref([]), formalContinuation: ref({}), conditionPreflight: ref({ blockers: [] }),
    selection: { salesOrderItemId: -11, ruleIds: [], candidateRuleIds: [] }, rules: ref([]), candidateMethods: ref([]),
    pdeApi: { engineeringCalculationReadiness: async () => ({}) }, unwrap: response => response,
    loadUnboundDrafts: noRead, sourceTrialOrders: ref([order]), orders: ref([order]), selectedOrder: ref(order),
    linkedWholeOrderSummary: noop, resolveFormalSummaryReturnTarget: noop, formalSummaryReturnContext: ref(null),
    activeCalculation: ref(null), formalValidation: ref({}), seedDraftRows: noop, drafts: ref([]), activeDraftId: ref(''),
    openDraft: noop, engineeringWorkloadScope: ref('SIM-SCOPE-A'), engineeringWorkloadLoadedScope: ref('SIM-SCOPE-OLD'),
    engineeringWorkloadReadState: ref('loaded'), engineeringWorkloadReadError: ref('SIM-OLD-ERROR'),
    requestedEngineeringVersion: ref(''), loadCalculations: noRead, loadFormalContinuation: noRead,
    loadMaterialRequirementPreview: noRead, visibleCalculations: ref([]), chooseCalculation: noRead, loadDrafts: noRead,
    explain: (error, fallback) => error?.message || fallback, isAuthenticationFailure: () => false,
    router: { replace: noRead }, updateDocumentTitle: noop,
  }
  const declaration = between(page, 'async function refresh() {', '\nwatch(() => route.fullPath, refresh)')
  const refresh = new Function(...Object.keys(refs), `let sequence = 0;\n${declaration}\nreturn refresh`)(...Object.values(refs))
  await refresh()
  assert.equal(refs.loadError.value, '')
  assert.equal(refs.drafts.value[0], draft)
  assert.equal(refs.loading.value, false)
  assert.equal(refs.engineeringWorkloadReadState.value, 'not_requested')
  assert.equal(refs.engineeringWorkloadReadError.value, '')
  assert.equal(visibleSummary(draft, { state: refs.engineeringWorkloadReadState.value,
    loadedScope: refs.engineeringWorkloadLoadedScope.value }), null)
  assert.equal(summary.counts.formalFactCount, null)
})

function refreshHarness({ pageKey = 'scheduling', sourceTrial = true, fullResponse = null } = {}) {
  const calls = [], opens = [], continuations = []
  const deferredDraft = { id: 11, sourceVersion: 'SIM-CURRENT-VERSION', engineeringWorkloadSummary: serverSummary('not_requested') }
  const fullDraft = { ...deferredDraft, engineeringWorkloadSummary: serverSummary() }
  const sourceOrder = { salesOrderItemId: -11, sourceRecordId: 11, isSourceTrial: true, draft: deferredDraft }
  const formalOrder = { salesOrderItemId: 4, orderEngineeringInstanceId: 3, orderNo: 'SIM-ORDER', isSourceTrial: false }
  const noop = () => {}, noRead = async () => {}
  const contextAndDrafts = between(api, '  engineeringDrafts(', '  saveEngineeringDraft(')
  const detail = between(api, '  engineeringCalculation(', '  executeEngineeringCalculation(')
  const productionReads = new Function('request', `return ({\n${contextAndDrafts}\n${detail}\n})`)(async config => {
    calls.push(config)
    if (config.params?.action === 'designCalculationContext') {
      if (config.params.includeWorkloadSummary === false) return { draft: deferredDraft }
      return fullResponse ? await fullResponse : { draft: fullDraft }
    }
    return { calculation: { id: 4, salesOrderItemId: 4, engineeringWorkloadSummary: serverSummary() } }
  })
  const refs = {
    route: { query: sourceTrial ? { sourceRecord: '11', page: pageKey } : { order: '4', page: pageKey }, path: '/pde/engineering-calculations', fullPath: '/pde/engineering-calculations' },
    loading: ref(false), loadError: ref(''), initialReadFailure: ref(null), auxiliaryReadNotice: ref(''), accessMode: ref(''),
    activeBusinessPage: ref(pageKey), configurationSubview: ref(false), resolveBusinessPage: () => pageKey,
    resolveFoundationPageState: noop, permissionProfile: ref(null), loadPermissionProfile: async () => ({}),
    permissionAllowed: () => true, CALCULATION_VIEW_PERMISSION: 'SIM-VIEW', RULE_VIEW_PERMISSION: 'SIM-RULE-VIEW',
    readiness: ref({}), calculations: ref([]), formalContinuation: ref({}), conditionPreflight: ref({ blockers: [] }),
    selection: { salesOrderItemId: sourceTrial ? -11 : 4, ruleIds: [], candidateRuleIds: [] }, rules: ref([]), candidateMethods: ref([]),
    pdeApi: { ...productionReads, engineeringCalculationReadiness: async () => ({}) }, unwrap: response => response,
    sourceTrialOrders: ref([sourceOrder]), orders: ref([sourceOrder, formalOrder]), selectedOrder: ref(sourceTrial ? sourceOrder : formalOrder),
    linkedWholeOrderSummary: noop, resolveFormalSummaryReturnTarget: noop, formalSummaryReturnContext: ref(null),
    activeCalculation: ref(null), formalValidation: ref({}), seedDraftRows: noop, drafts: ref([]), activeDraftId: ref(''), unboundDrafts: ref([]),
    openDraft: options => opens.push(options), engineeringWorkloadScope: ref(sourceTrial ? 'SIM-SOURCE-11' : 'SIM-LINE-4'), engineeringWorkloadLoadedScope: ref(''),
    engineeringWorkloadReadState: ref('not_requested'), engineeringWorkloadReadError: ref(''), requestedEngineeringVersion: ref(''),
    loadCalculations: async () => { if (!refs.selectedOrder.value?.isSourceTrial) refs.visibleCalculations.value = [{ id: 4, status: 'completed' }] },
    loadFormalContinuation: async () => continuations.push(refs.selectedOrder.value?.salesOrderItemId), loadMaterialRequirementPreview: noRead,
    visibleCalculations: ref([]), chooseCalculation: async row => { refs.activeCalculation.value = (await refs.pdeApi.engineeringCalculation(row.id)).calculation },
    explain: (error, fallback) => error?.message || fallback, isAuthenticationFailure: () => false,
    ElMessage: { error: noop }, router: { replace: noRead }, updateDocumentTitle: noop,
  }
  const declaration = between(page, 'async function loadDrafts(', '\nfunction addDraftRow(')
  const refreshDeclaration = between(page, 'async function refresh() {', '\nwatch(() => route.fullPath, refresh)')
  const refresh = new Function(...Object.keys(refs), `let sequence = 0; let draftReadSequence = 0;\n${declaration}\n${refreshDeclaration}\nreturn refresh`)(...Object.values(refs))
  return { refresh, refs, calls, opens, continuations, deferredDraft, fullDraft, formalOrder }
}

test('source selection directory always defers; actual source summary is loaded on first scheduling entry and refresh', async () => {
  const h = refreshHarness()
  await h.refresh()
  await h.refresh()
  assert.equal(h.refs.loadError.value, '')
  assert.deepEqual(h.calls.map(config => config.params.includeWorkloadSummary === false ? 'directory-deferred' : 'selected-source-full'),
    ['directory-deferred', 'selected-source-full', 'directory-deferred', 'selected-source-full'])
  assert.equal(h.calls[1].timeout, 90000)
  assert.equal(Object.hasOwn(h.calls[0], 'timeout'), false)
  assert.equal(h.refs.drafts.value[0], h.fullDraft)
  assert.equal(h.refs.engineeringWorkloadReadState.value, 'loaded')
  assert.equal(h.refs.engineeringWorkloadLoadedScope.value, 'SIM-SOURCE-11')
  assert.ok(h.opens.every(options => options.syncUrl === false), 'refresh must not sync the URL through openDraft')
})

test('normal line refresh reads only the deferred source directory and selected formal detail', async () => {
  const h = refreshHarness({ sourceTrial: false })
  await h.refresh()
  assert.equal(h.refs.loadError.value, '')
  assert.equal(h.calls.length, 2)
  assert.equal(h.calls[0].params.includeWorkloadSummary, false)
  assert.equal(h.calls[1].url, '/api/pde/a1-engineering/calculations/4/')
  assert.equal(h.calls[1].timeout, 60000)
  assert.equal(h.refs.activeCalculation.value.id, 4)
})

test('source input refresh remains deferred and never requests the full summary', async () => {
  const h = refreshHarness({ pageKey: 'input' })
  await h.refresh()
  assert.equal(h.calls.length, 1)
  assert.equal(h.calls[0].params.includeWorkloadSummary, false)
  assert.equal(h.refs.engineeringWorkloadReadState.value, 'not_requested')
  assert.equal(h.refs.drafts.value[0], h.deferredDraft)
})

test('late full-source response cannot overwrite a newer line refresh or resume its old continuation', async () => {
  let resolveFull
  const fullResponse = new Promise(resolve => { resolveFull = resolve })
  const h = refreshHarness({ fullResponse })
  const oldRefresh = h.refresh()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(h.calls.length, 2)
  h.refs.selectedOrder.value = h.formalOrder
  h.refs.selection.salesOrderItemId = 4
  h.refs.route.query = { order: '4', page: 'scheduling' }
  h.refs.engineeringWorkloadScope.value = 'SIM-LINE-4'
  await h.refresh()
  resolveFull({ draft: h.fullDraft })
  await oldRefresh
  assert.equal(h.refs.activeCalculation.value.id, 4)
  assert.equal(h.refs.drafts.value.length, 0)
  assert.deepEqual(h.continuations, [4])
  assert.notEqual(h.refs.engineeringWorkloadLoadedScope.value, 'SIM-SOURCE-11')
})
