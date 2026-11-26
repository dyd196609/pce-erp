import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(path.join(root, 'frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue'), 'utf8')
const router = fs.readFileSync(path.join(root, 'frontend/src/router/index.js'), 'utf8')
const section = page.slice(page.indexOf('data-section="scheduling-summary"'), page.indexOf('data-section="material-summary"'))
const ref = value => ({ value })

// Execute the production computed body rather than reimplement its guards.
function computedBody(name) {
  const start = page.indexOf(`const ${name} = computed(() => {`)
  const bodyStart = page.indexOf('{', start) + 1
  assert.ok(start >= 0, `production ${name} guard must be present`)
  return page.slice(bodyStart, page.indexOf('\n})', bodyStart))
}
const summaryStart = page.indexOf('const engineeringWorkloadFacts = computed(() => {')
const factsBody = computedBody('engineeringWorkloadFacts')
const summaryDependencyNames = ['activeDraft', 'engineeringWorkloadReadState', 'engineeringWorkloadLoadedScope',
  'engineeringWorkloadScope', 'workshopView', 'loading', 'loadError', 'versionStale',
  'calculationDetailLoading', 'calculationDetailError', 'activeCalculation', 'selectedOrder']
const factsGuard = new Function(...summaryDependencyNames, factsBody)
const summaryGuard = new Function('engineeringWorkloadFacts', 'workshopView', computedBody('engineeringWorkloadSummary'))
const readRawFacts = (facts, { state = 'loaded', loadedScope = 'SIM-SCOPE-A', scope = 'SIM-SCOPE-A',
  workshop = 'wood', loading = false, loadError = '', stale = false, draft = true,
  detailLoading = false, detailError = '', calculation = null } = {}) =>
  factsGuard(ref(draft ? { engineeringWorkloadSummary: facts } : null), ref(state), ref(loadedScope), ref(scope),
    ref(workshop), ref(loading), ref(loadError), ref(stale), ref(detailLoading), ref(detailError),
    ref(calculation), ref({ salesOrderItemId: 71 }))
const readSummary = (facts, options = {}) => summaryGuard(ref(readRawFacts(facts, options)), ref(options.workshop || 'wood'))

function serverFacts(rows = []) {
  return { contractVersion: 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1', factSource: 'server', readStatus: 'loaded',
    workshopViews: { wood: { rows }, paint: { rows } }, formalSavedFacts: [] }
}

function computedRows(name, facts) {
  const declaration = page.match(new RegExp(`^const ${name} = computed\\(\\(\\) => (.+)\\)$`, 'm'))
  assert.ok(declaration, `production ${name} declaration must remain a fact projection`)
  return new Function('engineeringWorkloadSummary', 'workshopView', `return ${declaration[1]}`)(ref(facts), ref('wood'))
}

function draftLoader(api, environment = {}) {
  const start = page.indexOf('async function loadDrafts(')
  const end = page.indexOf('\nasync function loadUnboundDrafts()', start)
  assert.ok(start >= 0 && end > start)
  const refs = {
    selectedOrder: ref({ salesOrderItemId: 71, orderEngineeringInstanceId: 72, isSourceTrial: false }),
    engineeringWorkloadScope: ref('SIM-SCOPE-A'), engineeringWorkloadReadState: ref('loaded'),
    engineeringWorkloadReadError: ref(''), engineeringWorkloadLoadedScope: ref('SIM-SCOPE-A'),
    drafts: ref([{ id: 'SIM-OLD-DRAFT' }]), activeDraftId: ref(''),
    pdeApi: api, unwrap: data => data, openDraft: () => {},
    explain: (error, fallback) => error?.message || fallback, ElMessage: { error: () => {} }, ...environment,
  }
  const load = new Function(...Object.keys(refs), `let draftReadSequence = 0;\n${page.slice(start, end)}\nreturn loadDrafts`)(...Object.values(refs))
  return { load, refs }
}

test('工程作业量汇总保留原正式页面身份、查询键和工程/材料区', () => {
  assert.match(page, /key: 'scheduling', label: '工程作业量汇总'/)
  assert.match(page, /v-show="activeBusinessPage === 'scheduling'"/)
  assert.match(router, /path: 'pde\/engineering-calculations'/)
  assert.match(page, /data-page-code="pde-order-engineering-calculation"/)
  assert.match(page, /<h2>施工单／整单核算结果<\/h2>/)
  assert.match(page, /data-section="material-summary"/)
  assert.match(page, /data-section="material-requirement-handoff-preview"/)
  assert.doesNotMatch(page, /SO202609180003/)
})

test('服务端合同、当前范围与加载状态全部正确才接受事实', () => {
  const facts = serverFacts()
  assert.equal(readSummary(facts), facts)
  for (const state of ['loading', 'not_requested', 'read_failed']) assert.equal(readSummary(facts, { state }), null)
  assert.equal(readSummary(facts, { loadedScope: 'SIM-SCOPE-OLD' }), null)
  assert.equal(readSummary({ ...facts, factSource: 'client-cache' }), null)
  assert.equal(readSummary({ ...facts, contractVersion: 'INVALID' }), null)
  assert.equal(readSummary({ ...facts, readStatus: 'unknown' }), null)
  assert.equal(readSummary({ ...facts, formalSavedFacts: null }), null)
  assert.equal(readSummary({ ...facts, workshopViews: {} }), null)
  assert.equal(readSummary(facts, { loading: true }), null)
  assert.equal(readSummary(facts, { loadError: 'SIMULATED_FOR_TEST failure' }), null)
  assert.equal(readSummary(facts, { stale: true }), null)
})

test('无草稿的正式记录只接受当前订单服务端只读投影而非旧EOR fallback', () => {
  const facts = serverFacts()
  const calculation = { salesOrderItemId: 71, engineeringWorkloadSummary: facts }
  assert.equal(readSummary(facts, { draft: false, calculation }), facts)
  assert.equal(readSummary(facts, { draft: false, calculation, detailLoading: true }), null)
  assert.equal(readSummary(facts, { draft: false, calculation, detailError: 'SIMULATED_FOR_TEST failure' }), null)
  assert.equal(readSummary(facts, { draft: false, calculation: { ...calculation, salesOrderItemId: 999 } }), null)
  assert.equal(readSummary(facts, { draft: false, calculation: { salesOrderItemId: 71, operationRequirements: [{ id: 1 }] } }), null)
})

test('所有单位、零、缺失和来源贡献直接传递，前端不筛单位或重算', () => {
  const units = ['m', 'm2', '套', '扇', '块', '支', '条', 'mm', null]
  const rows = units.map((unit, index) => ({ key: `SIM-${index}`, uomCode: unit,
    quantity: index === 0 ? '0' : index === 8 ? null : String(index),
    contributions: { door: null, threeInOne: String(index), items: [{ id: `source-${index}`, quantity: String(index) }] } }))
  const facts = serverFacts(rows)
  const before = JSON.stringify(facts)
  assert.equal(computedRows('engineeringWorkloadRows', readSummary(facts)), rows)
  assert.equal(JSON.stringify(facts), before)
  const computations = page.slice(summaryStart, page.indexOf('// PceEnterpriseListTable', summaryStart))
  assert.doesNotMatch(computations, /\.filter\(|\.reduce\(|Number\(|Math\.|\['m',\s*'m2'/)
  assert.doesNotMatch(computations, /activeCalculation.*operationRequirements|sourceCalculationRows/)
})

test('预览与正式FK转换事实并列，已转换不被来源预览遮挡', () => {
  const preview = [{ key: 'preview', quantity: '20', statusCode: 'PREVIEW_UNBOUND', operationRequirementIds: [] }]
  const formal = [{ key: 'formal', sourceCalculationId: 31, sourceFactId: 32, sourceDetailId: 33,
    quantity: '20', statusCode: 'CONVERTED', statusLabel: '已转换为正式工序作业量', operationRequirementIds: [34],
    conversion: { requirements: [{ workloadQuantity: '40', quantityBasis: 'PER_BASIS_QUANTITY' }] } }]
  const facts = { ...serverFacts(preview), formalSavedFacts: formal }
  assert.equal(computedRows('engineeringWorkloadRows', readSummary(facts)), preview)
  assert.equal(computedRows('engineeringWorkloadFormalRows', readSummary(facts)), formal)
  assert.equal(formal[0].quantity, '20')
  assert.equal(formal[0].conversion.requirements[0].workloadQuantity, '40')
  assert.match(section, /row\.sourceCalculationId[\s\S]*row\.sourceFactId[\s\S]*row\.sourceDetailId/)
  assert.match(section, /row\.operationRequirementIds/)
  assert.match(section, /requirement\.workloadQuantity/)
  assert.match(section, /requirement\.uomLabel \|\| requirement\.uomCode/)
})

test('转换标签与缺规则原因逐行来自服务端，不写固定尚未转换结论', () => {
  for (const field of ['sourceProject', 'dataTypeLabel', 'quantity', 'uomLabel', 'sourceNatureLabel', 'statusLabel'])
    assert.match(section, new RegExp(`prop="${field}"`))
  assert.match(section, /:status-label="row\.statusLabel"/)
  assert.match(section, /reason\.statusLabel/)
  assert.doesNotMatch(section, /\{\{\s*(?:row|reason)\.statusCode/)
  assert.doesNotMatch(section, /尚未转换为正式工序作业量|尚未转换为正式工序工作量/)
  assert.match(section, /row\.contributions\?\.door/)
  assert.match(section, /row\.contributions\?\.threeInOne/)
  assert.match(section, /row\.contributions\?\.items/)
})

test('读取失败使旧缓存失效且保留未知状态，不回退为零或旧正式EOR', async () => {
  const { load, refs } = draftLoader({ engineeringDrafts: async () => { throw new Error('SIMULATED_FOR_TEST read failure') } })
  await load()
  assert.equal(refs.engineeringWorkloadReadState.value, 'read_failed')
  assert.equal(refs.engineeringWorkloadLoadedScope.value, '')
  assert.match(refs.engineeringWorkloadReadError.value, /read failure/)
  assert.equal(readSummary(serverFacts(), { state: refs.engineeringWorkloadReadState.value,
    loadedScope: refs.engineeringWorkloadLoadedScope.value }), null)
  const serverFailure = { ...serverFacts(), readStatus: 'read_failed', factLoadStatus: 'read_failed',
    counts: { previewResultCount: null, formalFactCount: null }, httpStatus: 200,
    readStatusLabel: 'SIMULATED_FOR_TEST server summary unavailable' }
  assert.equal(readRawFacts(serverFailure), serverFailure)
  assert.equal(readSummary(serverFailure), null)
  assert.match(page, /engineeringWorkloadSummary: engineeringWorkloadFacts\.value/)
  assert.match(page, /engineeringWorkloadFacts\.value\?\.readStatus === 'read_failed'/)
  assert.match(section, /data-state="engineering-workload-unknown"/)
  assert.match(section, /数量与转换状态未知，未补为零/)
})

test('晚到的旧范围响应不能替换当前订单工程事实', async () => {
  let resolve
  const response = new Promise(done => { resolve = done })
  const { load, refs } = draftLoader({ engineeringDrafts: () => response })
  const loading = load()
  assert.equal(refs.engineeringWorkloadReadState.value, 'loading')
  refs.engineeringWorkloadScope.value = 'SIM-SCOPE-B'
  resolve({ drafts: [{ id: 'SIM-STALE-RESPONSE' }] })
  await loading
  assert.deepEqual(refs.drafts.value, [{ id: 'SIM-OLD-DRAFT' }])
  assert.notEqual(refs.engineeringWorkloadReadState.value, 'loaded')
  assert.equal(refs.engineeringWorkloadLoadedScope.value, '')
})

test('共享企业列表拥有筛选、滚动、选择和导出，枚举声明正式select合同', () => {
  assert.match(section, /<PceEnterpriseListTable/)
  assert.match(section, /:contract="list\.contract"/)
  assert.match(section, /:table-rows="list\.runtime\.filteredRows"/)
  assert.match(section, /@export-current="list\.runtime\.exportCurrent"/)
  assert.doesNotMatch(section, /<table\b|<el-select\b|<el-input\b/)
  for (const field of ['dataTypeLabel', 'uomLabel', 'sourceNatureLabel', 'statusLabel'])
    assert.match(page, new RegExp(`field: '${field}'[^\n]+filterType: 'select'[^\n]+optionsProvider: 'current_result'`))
  assert.match(page, /createPceEnterpriseListContract\(\{ pageCode: 'pde-order-engineering-calculation'/)
})

test('只提供受权限保护的正式规则导航，汇总无自动转换或APS执行动作', () => {
  assert.match(section, /permissionAllowed\(RULE_VIEW_PERMISSION\)/)
  assert.match(section, /router\.push\(ruleDefinitionsLocation\)/)
  assert.match(page, /name: 'FoundationEngineeringRuleDefinitions'/)
  assert.doesNotMatch(section, /@click="[^\"]*(?:generate|calculate|allocate|schedule|runAps|createCapacity)/i)
  assert.match(section, /不执行转换、生成日期、分配资源或形成产能结论/)
})
