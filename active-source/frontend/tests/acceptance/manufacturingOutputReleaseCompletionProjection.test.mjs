import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { parse, compileScript, compileStyle } from '@vue/compiler-sfc'

const filename = 'ManufacturingOutputHandoff.vue'
const source = fs.readFileSync(new URL('../../src/meta/pages/components/ManufacturingOutputHandoff.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parse(source, { filename })
assert.deepEqual(errors, [])
for (const style of descriptor.styles) {
  assert.deepEqual(compileStyle({ source: style.content, filename, id: 'publication-completion', scoped: style.scoped }).errors, [])
}
const compiled = compileScript(descriptor, { id: 'publication-completion', inlineTemplate: true }).content
const executable = compiled
  .replace(/import\s*\{([^}]+)\}\s*from\s*['"]vue['"]/g, (_all, bindings) => `const {${bindings.replace(/\bas\b/g, ':')}} = Vue`)
  .replace(/import PceBusinessStatus from [^\n]+/, 'const PceBusinessStatus = Status')
  .replace('export default', 'return')
const Status = Vue.defineComponent({ props: ['statusLabel'], setup: props => () => Vue.h('span', props.statusLabel) })
const Component = new Function('Vue', 'Status', executable)(Vue, Status)
const PassThrough = Vue.defineComponent({ setup: (_props, context) => () => Vue.h('div', context.attrs, context.slots.default?.()) })

const proof = { completed: true, actorId: 23, actorUsername: 'pce_emp107', auditId: 10947,
  writeRequestId: 3422, businessStateTransitionId: 6591, releasedAt: '2026-10-21T15:33:29' }
const projection = changes => ({
  releaseAllowed: false, releaseCompleted: false, sourceReady: true,
  statusLabelForReadiness: '制造发布准入阻断', completionMessage: '', releaseReadback: proof,
  eligiblePublishers: [], gates: [], actionContract: {
    actionCode: 'pde.manufacturing_output.release', displayName: '正式发布至制造', requiredPermission: 'production.engineering.release',
  }, ...changes,
})
async function render(manufacturingRelease) {
  const candidate = { orderNo: 'SO-SSR-ONLY', lineNo: 1, statusLabel: '已生成',
    output: { id: 5, statusLabel: '已发布至制造', manufacturingReleaseExecuted: true, generationReadback: {} },
    manufacturingRelease }
  const app = Vue.createSSRApp(Component, { candidate })
  app.config.warnHandler = () => {}
  for (const name of ['el-alert', 'el-button', 'el-input', 'el-select', 'el-option']) app.component(name, PassThrough)
  return renderToString(app)
}

test('服务端完成证明直接显示原生操作者审计时间且不出现重复办理失败提示', async () => {
  const html = await render(projection({ releaseCompleted: true, statusLabelForReadiness: '已完成正式制造发布',
    completionMessage: '正式制造发布已完成，无需重复办理；未自动创建下游业务。' }))
  assert.match(html, /manufacturing-output-release-completed/)
  assert.match(html, /manufacturing-output-release-native-proof/)
  for (const value of ['pce_emp107', '10947', '3422', '6591', '2026-10-21T15:33:29']) assert.ok(html.includes(value))
  assert.doesNotMatch(html, /title="制造发布已阻断"/)
  assert.doesNotMatch(html, /制造发布理由/)
})

test('仅有已发布状态或旧output标志不能由前端判为完成', async () => {
  const html = await render(projection({ firstBlockerCode: 'MANUFACTURING_RELEASE_FACT_INCOMPLETE',
    firstBlockerMessage: '正式发布证明尚未完整' }))
  assert.doesNotMatch(html, /manufacturing-output-release-completed/)
  assert.doesNotMatch(html, /manufacturing-output-release-native-proof/)
  assert.match(html, /正式发布证明尚未完整/)
})

test('已发布对象的真实来源失效警告仍显示', async () => {
  const html = await render(projection({ sourceReady: false, firstBlockerCode: 'MANUFACTURING_RELEASE_CONTENT_CHANGED',
    firstBlockerMessage: '正式发布冻结来源已变化' }))
  assert.match(html, /title="制造发布已阻断"/)
  assert.match(html, /正式发布冻结来源已变化/)
  assert.doesNotMatch(html, /manufacturing-output-release-completed/)
})

test('原草稿发布动作仍只依赖服务端releaseAllowed', async () => {
  const html = await render(projection({ releaseAllowed: true, statusLabelForReadiness: '制造发布准入通过' }))
  assert.match(html, /请由合法发布人填写制造发布理由/)
  assert.match(html, /正式发布至制造/)
  assert.doesNotMatch(html, /manufacturing-output-release-completed/)
})
