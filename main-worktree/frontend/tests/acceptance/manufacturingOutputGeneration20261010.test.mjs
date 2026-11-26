import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { submitManufacturingOutputGeneration } from '../../src/meta/pages/manufacturingOutputGenerationSubmission.js'

const proof = { completed: true, auditId: 12, writeRequestId: 13, initializationTransitionId: 14 }
const result = { row: { id: 11, statusCode: 'draft' }, auditId: 12, writeRequestId: 13,
  initializationTransitionId: 14, manufacturingReleaseExecuted: false }
const candidate = { output: { id: 11, statusCode: 'draft', generationReadback: proof }, outputCount: 1,
  orderNo: 'SO-TEST', lineNo: 1 }
const options = extra => ({ confirm: async () => {}, request: async () => ({ success: true, data: { result } }),
  refresh: async () => {}, readback: () => candidate, isSubmitting: () => false,
  setSubmitting: () => {}, ...extra })

test('只在事务证据和正式回读一致后返回生成成功', async () => {
  const got = await submitManufacturingOutputGeneration(options())
  assert.equal(got.candidate.output.statusCode, 'draft')
})
for (const status of [200, 400, 401, 403, 409, 500]) {
  test(`HTTP ${status} success=false保持真实业务错误`, async () => {
    await assert.rejects(submitManufacturingOutputGeneration(options({ request: async () => ({ success: false,
      meta: { status }, error: { code: 'SOURCE_REJECTED', message: '来源组合被拒绝' } }) })), /SOURCE_REJECTED.*来源组合被拒绝/)
  })
}
test('取消确认不发请求', async () => {
  let sent = 0
  await assert.rejects(submitManufacturingOutputGeneration(options({ confirm: async () => { throw 'cancel' },
    request: async () => { sent += 1 } })), e => e === 'cancel')
  assert.equal(sent, 0)
})
test('在途重复点击只发送一次', async () => {
  let busy = false
  let sent = 0
  let finish
  const barrier = new Promise(resolve => { finish = resolve })
  const shared = options({ isSubmitting: () => busy, setSubmitting: value => { busy = value },
    request: async () => { sent += 1; await barrier; return { success: true, data: { result } } } })
  const first = submitManufacturingOutputGeneration(shared)
  assert.equal((await submitManufacturingOutputGeneration(shared)).duplicateSuppressed, true)
  finish()
  await first
  assert.equal(sent, 1)
  assert.equal(busy, false)
})
test('响应缺审计或者状态越界不能进入成功分支', async () => {
  for (const bad of [{ ...result, auditId: null }, { ...result, row: { id: 11, statusCode: 'released_to_manufacturing' } }]) {
    await assert.rejects(submitManufacturingOutputGeneration(options({ request: async () => ({ success: true, data: { result: bad } }) })), /SUCCESS_CONTRACT_INVALID/)
  }
})
test('成功响应但回读对象不一致必须显示异常', async () => {
  await assert.rejects(submitManufacturingOutputGeneration(options({ readback: () => ({ ...candidate,
    output: { ...candidate.output, id: 99 } }) })), /READBACK_MISMATCH/)
})
test('网络失败释放在途锁且不宣称成功', async () => {
  let busy = false
  await assert.rejects(submitManufacturingOutputGeneration(options({ setSubmitting: value => { busy = value },
    request: async () => { throw new Error('网络中断') } })), /网络中断/)
  assert.equal(busy, false)
})

const page = fs.readFileSync(new URL('../../src/meta/pages/PdeFoundationPage.vue', import.meta.url), 'utf8')
const start = page.indexOf('async function handleGenerateManufacturingOutput(payload)')
const end = page.indexOf('\nfunction failureMessage', start)
const handlerSource = page.slice(start, end)
test('真实页面处理函数等待刷新后成功，失败没有成功提示', async () => {
  for (const fails of [false, true]) {
    const successes = [], errors = []
    const state = { value: false }
    const handler = vm.runInNewContext(`${handlerSource}; handleGenerateManufacturingOutput`, {
      submitManufacturingOutputGeneration,
      ElMessageBox: { confirm: async () => {} },
      ElMessage: { success: text => successes.push(text), error: text => errors.push(text) },
      strictFacts: { value: { manufacturingOutputCandidate: candidate } },
      manufacturingOutputSubmitting: state,
      refresh: async () => {}, newIdempotencyKey: () => 'test-key',
      pdeApi: { generateManufacturingOutput: async () => fails
        ? { success: false, meta: { status: 403 }, error: { code: 'EXECUTOR_DENIED', message: '人员拒绝' } }
        : { success: true, data: { result } } },
    })
    await handler({ reason: '源确认', salesOrderItemId: 3 })
    assert.equal(successes.length, fails ? 0 : 1)
    assert.equal(errors.length, fails ? 1 : 0)
    if (fails) assert.match(errors[0], /EXECUTOR_DENIED/)
    assert.equal(state.value, false)
  }
})
test('候选组件和主页面均可编译，主页面接入真实生成函数', () => {
  const source = fs.readFileSync(new URL('../../src/meta/pages/components/ManufacturingOutputHandoff.vue', import.meta.url), 'utf8')
  for (const [filename, content] of [['Handoff.vue', source], ['PdeFoundationPage.vue', page]]) {
    const parsed = parse(content, { filename })
    assert.equal(parsed.errors.length, 0)
    const compiled = compileTemplate({ source: parsed.descriptor.template.content, filename, id: 'pmo-test' })
    assert.equal(compiled.errors.length, 0)
  }
  assert.match(page, /@generate="handleGenerateManufacturingOutput"/)
  assert.match(source, /candidate\.generationAllowed/)
})
