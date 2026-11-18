import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { computed, ref } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = fs.readFileSync(new URL('../../src/meta/pages/PdeOrderEngineeringCalculationPage.vue', import.meta.url), 'utf8')
const descriptor = parse(source).descriptor
const compiled = compileScript(descriptor, { id: 'main-calculation-continuation-test' })
const functionNames = ['formalRuleIds', 'mainContinuationPayload', 'mainContinuationScopeKey', 'resetMainContinuationPreview', 'runMainContinuationAction', 'previewMainContinuation', 'executeMainContinuation', 'unwrap', 'explain']
const computedNames = ['mainContinuationFacts', 'mainContinuationActions', 'mainContinuationCanExecute']
const selectedNodes = compiled.scriptSetupAst.filter(node => node.type === 'FunctionDeclaration' && functionNames.includes(node.id.name) || node.type === 'VariableDeclaration' && node.declarations.some(item => computedNames.includes(item.id.name)))
const behaviorSource = selectedNodes.map(node => descriptor.scriptSetup.content.slice(node.start, node.end)).join('\n')
const plain = value => JSON.parse(JSON.stringify(value))
const actions = [{ actionCode: 'preview', displayName: '预览主核算接续', allowed: true }, { actionCode: 'execute', displayName: '正式接续主核算', allowed: true }]
const previewResult = () => ({ ready: true, statusLabel: '只读预览通过', expectedContextHash: 'context-hash', continuationBasisHash: 'basis-hash', availableActions: actions })
const committedRecord = () => ({ id: 201, newCalculationId: 501, predecessorCalculationId: 301, orderEngineeringBaselineId: 403, statusLabel: '正式主核算接续已提交', stateMachineConsistent: true, requestStatus: 'COMMITTED' })
const newCalculation = () => ({ id: 501, companyId: 1, salesOrderItemId: 103, orderEngineeringInstanceId: 202, status: 'completed', trace: { baselineReference: { id: 403 } } })
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }

function harness(options = {}) {
  const calls = []
  const messages = []
  const state = {
    selectedOrder: ref({ salesOrderItemId: 103, orderNo: 'ORDER-A', sourceRecordId: 41, isSourceTrial: false }),
    formalContinuationLine: ref({ orderEngineeringInstanceId: 202, calculationContinuation: { statusLabel: '等待明确选择与预览', predecessorCalculations: [{ id: 301 }], availableActions: actions, records: [] } }),
    formalBaselines: ref([{ id: 403, status: 'confirmed', baselineNo: 'BASELINE-403' }]),
    selectedBaselineId: ref(403), selectedPredecessorCalculationId: ref(301),
    selectedWorkbookSourceRecordId: ref(''),
    permissionProfile: ref({ user: { id: 7 }, organization: { id: 1 } }),
    formalContinuation: ref({ formalRulePackages: [{ id: 71 }, { id: 72 }] }),
    formalBusy: ref(false), mainContinuationPreview: ref(null), mainContinuationError: ref(''), mainContinuationReadback: ref(null), writeCount: ref(0),
  }
  let methods
  const dependencies = {
    ...state, computed,
    pdeApi: {
      async previewEngineeringCalculationVersionContinuation(payload) { calls.push(['preview', plain(payload)]); return options.preview ? options.preview(payload) : previewResult() },
      async executeEngineeringCalculationVersionContinuation(payload) { calls.push(['execute', plain(payload)]); return options.execute ? options.execute(payload) : { continuation: { id: 201 }, calculation: { id: 501, companyId: 1 }, idempotent: false } },
      async engineeringCalculation(id) { calls.push(['read-exact-calculation', id]); return options.detail ? options.detail(id) : { calculation: newCalculation() } },
    },
    ElMessageBox: { async confirm() { calls.push(['confirm']); return options.confirm?.(state) } },
    ElMessage: { success: message => messages.push(message) },
    async loadFormalContinuation() {
      calls.push(['read-formal-continuation'])
      if (options.formalRead) return options.formalRead(state, methods)
      state.formalContinuationLine.value.calculationContinuation.records = [committedRecord()]
      state.formalContinuationLine.value.calculationContinuation.predecessorCalculations = []
      methods.resetMainContinuationPreview()
    },
    async loadCalculations() { calls.push(['read-calculation-list']) },
  }
  methods = vm.runInNewContext(`let mainContinuationRequestSequence = 0; let mainContinuationPreviewScope = '';\n${behaviorSource}\n({ ${functionNames.join(', ')}, mainContinuationFacts, mainContinuationActions, mainContinuationCanExecute })`, dependencies)
  return { ...state, methods, calls, messages }
}

test('the two original-page API methods post only to the formal preview and execute endpoints', async () => {
  const apiSource = fs.readFileSync(new URL('../../src/api/pde.js', import.meta.url), 'utf8')
  const requests = []
  const api = vm.runInNewContext(`${apiSource.replace(/^import .*$/m, '').replace('export const pdeApi', 'const pdeApi')}; pdeApi`, { request: value => { requests.push(plain(value)); return value } })
  await api.previewEngineeringCalculationVersionContinuation({ salesOrderItemId: 103 })
  await api.executeEngineeringCalculationVersionContinuation({ expectedContextHash: 'native-hash' })
  assert.deepEqual(requests.map(row => [row.method, row.url]), [['POST', '/api/pde/a1-engineering/calculations/version-continuation/preview/'], ['POST', '/api/pde/a1-engineering/calculations/version-continuation/execute/']])
  assert.deepEqual(requests[0].data, { salesOrderItemId: 103 })
  assert.deepEqual(requests[1].data, { expectedContextHash: 'native-hash' })
})

test('original baseline, four-page navigation and formal actions stay in place; SFC compiles', () => {
  const originalActions = ['createFormalInstance', 'confirmFormalInstanceSource', 'validateFormalContinuation', 'executeFormalContinuation']
  for (const name of originalActions) assert.ok(source.indexOf(`@click="${name}"`) < source.indexOf('data-section="main-calculation-version-continuation"'))
  assert.ok(source.indexOf('v-model.number="selectedBaselineId"') < source.indexOf('data-section="main-calculation-version-continuation"'))
  assert.match(source, /@click="switchBusinessPage\(page.key\)"/)
  assert.match(source, /watch\(\[selectedBaselineId, selectedPredecessorCalculationId, \(\) => selection.salesOrderItemId, \(\) => formalContinuation.value\], resetMainContinuationPreview, \{ flush: 'sync' \}\)/)
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'PdeOrderEngineeringCalculationPage.vue', id: 'main-calculation-continuation-test', compilerOptions: { bindingMetadata: compiled.bindings } }).errors, [])
})

test('server action permission and explicit current candidates gate preview and execute', async () => {
  const denied = harness()
  denied.formalContinuationLine.value.calculationContinuation.availableActions = actions.map(action => ({ ...action, allowed: false }))
  await denied.methods.previewMainContinuation()
  await denied.methods.executeMainContinuation()
  assert.equal(denied.calls.length, 0)
  const missing = harness()
  missing.selectedPredecessorCalculationId.value = 999
  await missing.methods.previewMainContinuation()
  assert.equal(missing.calls.length, 0)
})

test('preview uses selected native identities and rule IDs without manufacturing basis or approval', async () => {
  const f = harness()
  await f.methods.previewMainContinuation()
  assert.deepEqual(f.calls, [['preview', { salesOrderItemId: 103, orderEngineeringInstanceId: 202, orderEngineeringBaselineId: 403, predecessorCalculationId: 301, ruleIds: [71, 72] }]])
  assert.equal(f.methods.mainContinuationCanExecute.value, true)
  assert.equal(f.writeCount.value, 0)
  assert.equal(f.messages.length, 0)
})

test('selection changes invalidate an in-flight preview and old responses stay isolated', async () => {
  const pending = deferred()
  const f = harness({ preview: () => pending.promise })
  const reading = f.methods.previewMainContinuation()
  f.selectedBaselineId.value = 404
  f.methods.resetMainContinuationPreview()
  pending.resolve(previewResult())
  await reading
  assert.equal(f.mainContinuationPreview.value, null)
  assert.equal(f.methods.mainContinuationCanExecute.value, false)
  assert.equal(f.formalBusy.value, false)
})

test('identity refresh suppresses a late response even with the same selected business IDs', async () => {
  const pending = deferred()
  const f = harness({ preview: () => pending.promise })
  const reading = f.methods.previewMainContinuation()
  f.permissionProfile.value = { user: { id: 8 }, organization: { id: 1 } }
  pending.resolve(previewResult())
  await reading
  assert.equal(f.mainContinuationPreview.value, null)
  assert.equal(f.mainContinuationError.value, '')
})

test('blocked or failed preview never becomes save eligibility and preserves selections', async () => {
  const blocked = harness({ preview: () => ({ ...previewResult(), ready: false, blockers: [{ statusLabel: '正式范围仍有阻断' }] }) })
  await blocked.methods.previewMainContinuation()
  await blocked.methods.executeMainContinuation()
  assert.equal(blocked.calls.length, 1)
  const failed = harness({ preview: () => { throw new Error('read_failed') } })
  await failed.methods.previewMainContinuation()
  assert.equal(failed.mainContinuationPreview.value, null)
  assert.match(failed.mainContinuationError.value, /read_failed/)
  assert.equal(failed.selectedBaselineId.value, 403)
  assert.equal(failed.selectedPredecessorCalculationId.value, 301)
  assert.equal(failed.writeCount.value, 0)
})

test('execute binds both preview hashes and confirms exact committed relationship plus fresh calculation', async () => {
  const f = harness()
  await f.methods.previewMainContinuation()
  await f.methods.executeMainContinuation()
  const execute = f.calls.find(row => row[0] === 'execute')[1]
  assert.equal(execute.expectedContextHash, 'context-hash')
  assert.equal(execute.continuationBasisHash, 'basis-hash')
  assert.equal(execute.idempotencyKey, 'engineering-calculation-continuation:context-hash')
  assert.equal(execute.predecessorCalculationId, 301)
  assert.equal(execute.orderEngineeringBaselineId, 403)
  assert.equal(Object.hasOwn(execute, 'continuationBasis'), false)
  assert.deepEqual(f.calls.slice(2).map(row => row[0]), ['execute', 'read-formal-continuation', 'read-exact-calculation', 'read-calculation-list'])
  assert.equal(f.mainContinuationReadback.value.newCalculationId, 501)
  assert.equal(f.writeCount.value, 1)
  assert.deepEqual(f.messages, ['正式主核算接续已提交'])
  assert.equal(f.formalBusy.value, false)
})

for (const [name, detail] of [['wrong baseline', { ...newCalculation(), trace: { baselineReference: { id: 999 } } }], ['wrong company', { ...newCalculation(), companyId: 2 }], ['wrong new ID', { ...newCalculation(), id: 999 }]]) {
  test(`a fresh calculation with ${name} cannot be reported as committed readback`, async () => {
    const f = harness({ detail: () => ({ calculation: detail }) })
    await f.methods.previewMainContinuation()
    await f.methods.executeMainContinuation()
    assert.equal(f.mainContinuationReadback.value, null)
    assert.equal(f.writeCount.value, 0)
    assert.equal(f.messages.length, 0)
    assert.match(f.mainContinuationError.value, /未自动重试/)
    assert.equal(f.calls.filter(row => row[0] === 'execute').length, 1)
  })
}

test('missing committed state proof or failed fresh readback is not replaced by old page data', async () => {
  for (const formalRead of [(state) => { state.formalContinuationLine.value.calculationContinuation.records = [{ ...committedRecord(), requestStatus: 'PENDING' }] }, () => { throw new Error('fresh read failed') }]) {
    const f = harness({ formalRead })
    await f.methods.previewMainContinuation()
    await f.methods.executeMainContinuation()
    assert.equal(f.mainContinuationReadback.value, null)
    assert.equal(f.messages.length, 0)
    assert.equal(f.calls.filter(row => row[0] === 'execute').length, 1)
  }
})

test('context changed during confirmation cannot execute an old preview', async () => {
  const f = harness({ confirm: state => { state.selectedPredecessorCalculationId.value = 999 } })
  await f.methods.previewMainContinuation()
  await f.methods.executeMainContinuation()
  assert.deepEqual(f.calls.map(row => row[0]), ['preview', 'confirm'])
  assert.equal(f.formalBusy.value, false)
})

test('busy confirmation and execution prevent duplicate submissions; failure is not retried', async () => {
  const confirm = deferred()
  const f = harness({ confirm: () => confirm.promise, execute: () => { throw new Error('outcome unknown') } })
  await f.methods.previewMainContinuation()
  const executing = f.methods.executeMainContinuation()
  await f.methods.executeMainContinuation()
  assert.equal(f.calls.filter(row => row[0] === 'confirm').length, 1)
  confirm.resolve()
  await executing
  assert.equal(f.calls.filter(row => row[0] === 'execute').length, 1)
  assert.equal(f.mainContinuationReadback.value, null)
  assert.match(f.mainContinuationError.value, /outcome unknown/)
  assert.equal(f.selectedBaselineId.value, 403)
  assert.equal(f.selectedPredecessorCalculationId.value, 301)
  assert.equal(f.formalBusy.value, false)
})
