import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { submitManufacturingOutputGeneration } from '../../src/meta/pages/manufacturingOutputGenerationSubmission.js'

const proof = { completed: true, auditId: 53, writeRequestId: 54, initializationTransitionId: 55 }
function fixture() {
  const row = { id: 18, statusCode: 'draft', engineeringDocumentVersionId: 14, predecessorOutputId: 9 }
  const result = { row, auditId: 53, writeRequestId: 54, initializationTransitionId: 55,
    manufacturingReleaseExecuted: false }
  const candidate = { output: { ...row, generationReadback: { ...proof } }, outputCount: 2,
    selectedOutputCount: 1, selection: { salesOrderItemId: 7, engineeringDocumentVersionId: 14, predecessorOutputId: 9 } }
  let busy = false
  const events = []
  return { result, candidate, events, options: {
    confirm: async () => { events.push('confirm') },
    request: async () => { events.push('request'); return { success: true, data: { result } } },
    refresh: async () => { events.push('refresh') },
    readback: () => { events.push('readback'); return candidate },
    isSubmitting: () => busy, setSubmitting: value => { busy = value },
  }, isBusy: () => busy }
}

test('两个版本并存时仅精确选定组合一个且ID及提交证明匹配才成功', async () => {
  const f = fixture()
  const value = await submitManufacturingOutputGeneration(f.options)
  assert.equal(value.result.row.id, 18)
  assert.equal(value.candidate.outputCount, 2)
  assert.deepEqual(f.events, ['confirm', 'request', 'refresh', 'readback'])
  assert.equal(f.isBusy(), false)
})

for (const [field, value] of [['engineeringDocumentVersionId', 15], ['predecessorOutputId', 10]]) {
  test(`回读选定${field}与提交输出不符时拒绝成功`, async () => {
    const f = fixture()
    f.candidate.selection[field] = value
    await assert.rejects(submitManufacturingOutputGeneration(f.options), /READBACK_MISMATCH/)
    assert.equal(f.isBusy(), false)
  })
  test(`刷新输出同ID同ledger但${field}错误也拒绝成功`, async () => {
    const f = fixture()
    f.candidate.output[field] = value
    await assert.rejects(submitManufacturingOutputGeneration(f.options), /READBACK_MISMATCH/)
    assert.equal(f.isBusy(), false)
  })
}

test('全量版本有数据不代替选定组合基数与完整ledger', async () => {
  for (const count of [0, 2, null]) {
    const f = fixture()
    f.candidate.selectedOutputCount = count
    if (count === null) f.candidate.outputCount = 2
    await assert.rejects(submitManufacturingOutputGeneration(f.options), /READBACK_MISMATCH/)
  }
  const f = fixture()
  f.candidate.output.generationReadback.writeRequestId = 999
  await assert.rejects(submitManufacturingOutputGeneration(f.options), /READBACK_MISMATCH/)
})

test('旧单输出响应保留原ID与审计回读合同', async () => {
  const f = fixture()
  delete f.candidate.selection
  delete f.candidate.selectedOutputCount
  f.candidate.outputCount = 1
  assert.equal((await submitManufacturingOutputGeneration(f.options)).result.row.id, 18)
})

const componentSource = fs.readFileSync(new URL('../../src/meta/pages/components/ManufacturingOutputHandoff.vue', import.meta.url), 'utf8')
const pageSource = fs.readFileSync(new URL('../../src/meta/pages/PdeFoundationPage.vue', import.meta.url), 'utf8')
function component(candidate, submitting = false) {
  const script = parse(componentSource).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const emitted = []
  const methods = vm.runInNewContext(`${script}; ({ submit, release, selectOrderItem, selectDocument, selectPredecessor })`, {
    defineProps: () => ({ candidate, submitting }), defineEmits: () => (...args) => emitted.push(args),
    ref: value => ({ value: typeof value === 'string' ? '明确版本办理原因' : value }), watch: () => {},
  })
  return { methods, emitted }
}
const plain = value => JSON.parse(JSON.stringify(value))

test('原生成按钮携带服务端明确资料和前驱，不重算来源或资格', () => {
  const f = fixture()
  const { methods, emitted } = component({ ...f.candidate, salesOrderItemId: 7,
    generationAllowed: true, sourceFingerprint: 'frozen-native-fingerprint', actionCode: 'pde.manufacturing_output.generate' })
  methods.submit()
  assert.deepEqual(plain(emitted), [['generate', { salesOrderItemId: 7,
    sourceFingerprint: 'frozen-native-fingerprint', action: 'pde.manufacturing_output.generate',
    engineeringDocumentVersionId: 14, predecessorOutputId: 9, reason: '明确版本办理原因' }]])
  for (const candidate of [{ ...f.candidate, generationAllowed: false }, { ...f.candidate, generationAllowed: true }]) {
    const blocked = component(candidate, true)
    blocked.methods.submit()
    assert.equal(blocked.emitted.length, 0)
  }
})

test('切订单行只清依赖导航；切资料保留明确前驱；读取中不发送旧版本生成', () => {
  const f = fixture()
  const order = component({ ...f.candidate, generationAllowed: true })
  order.methods.selectOrderItem(8)
  order.methods.submit()
  assert.deepEqual(plain(order.emitted), [['select-version', {
    salesOrderItemId: 8, engineeringDocumentVersionId: null, predecessorOutputId: null }]])
  const document = component(f.candidate)
  document.methods.selectDocument(16)
  assert.deepEqual(plain(document.emitted[0]), ['select-version', {
    salesOrderItemId: 7, engineeringDocumentVersionId: 16, predecessorOutputId: 9 }])
  const predecessor = component(f.candidate)
  predecessor.methods.selectPredecessor(null)
  assert.equal(predecessor.emitted[0][1].predecessorOutputId, null)
})

test('原页面版本选择只更新三个GET上下文ID并保留其他查询，不执行保存', async () => {
  const start = pageSource.indexOf('async function handleSelectManufacturingOutputVersion(selection)')
  const end = pageSource.indexOf('\nasync function handleGenerateManufacturingOutput', start)
  const navigation = []
  const handler = vm.runInNewContext(`${pageSource.slice(start, end)}; handleSelectManufacturingOutputVersion`, {
    manufacturingOutputSubmitting: { value: false },
    route: { path: '/pde/manufacturing-outputs', query: { q: '原筛选', salesOrderItemId: '7', engineeringDocumentVersionId: '14', predecessorOutputId: '9' } },
    router: { replace: async value => { navigation.push(value) } },
  })
  await handler({ salesOrderItemId: 8, engineeringDocumentVersionId: null, predecessorOutputId: null })
  assert.deepEqual(plain(navigation), [{ path: '/pde/manufacturing-outputs', query: { q: '原筛选', salesOrderItemId: '8' } }])
})

test('原页面和候选组件可编译，旧输出历史和原按钮仍在同一组件', () => {
  for (const [filename, source] of [['Handoff.vue', componentSource], ['PdeFoundationPage.vue', pageSource]]) {
    const { descriptor, errors } = parse(source, { filename })
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    const template = compileTemplate({ source: descriptor.template.content, filename, id: filename,
      compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(template.errors, [])
  }
  assert.match(componentSource, /v-for="output in candidate\.existingOutputs"/)
  assert.match(componentSource, /@click="submit"/)
  assert.match(componentSource, /@click="release"/)
  assert.match(pageSource, /@select-version="handleSelectManufacturingOutputVersion"/)
})
