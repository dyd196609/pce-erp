import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import * as Vue from 'vue'
import { renderToString } from '@vue/server-renderer'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { formatBusinessStatus } from '../../src/meta/runtime/businessDisplayValueFormatter.js'

const page = await readFile(new URL('../../src/meta/pages/PdeOrderEngineeringCalculationPage.vue', import.meta.url), 'utf8')
const panel = await readFile(new URL('../../src/meta/components/EngineeringCalculationBatchPanel.vue', import.meta.url), 'utf8')
const statusBody = page.match(/function calculationStatusLabel\(row\) \{([\s\S]*?)\n\}/)[1]
const statusLabel = new Function('formatBusinessStatus', `return function(row) {${statusBody}\n}`)(formatBusinessStatus)
const detailTemplate = panel.slice(panel.indexOf('<article v-if="detail" class="detail">'), panel.indexOf('</article>', panel.indexOf('<article v-if="detail" class="detail">')) + '</article>'.length)
const render = new Function('Vue', compile(detailTemplate, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
async function detailHtml(detail, businessInputs = []) {
  const inputBefore = JSON.stringify(detail)
  const html = await renderToString(Vue.createSSRApp({
    data: () => ({ detail, detailEdges: [], catalog: { sources: [{ key: detail.sourceKey, businessInputs }] } }),
    components: { RoomDoorEdgeRequirementPreview: { render: () => null } }, render,
  }))
  assert.equal(JSON.stringify(detail), inputBefore, 'rendering must not mutate authoritative facts')
  return html
}

test('两个原SFC可编译，复用原页面而不是新建工作台', () => {
  for (const [filename, source] of [['PdeOrderEngineeringCalculationPage.vue', page], ['EngineeringCalculationBatchPanel.vue', panel]]) {
    const parsed = parse(source, { filename })
    assert.deepEqual(parsed.errors, [])
    const script = compileScript(parsed.descriptor, { id: filename })
    const result = compileTemplate({ source: parsed.descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  }
})

test('中文状态优先使用服务端标签，原始状态与动作资格不变', () => {
  const row = Object.freeze({ status: 'completed' })
  assert.equal(statusLabel(row), '已完成')
  assert.equal(row.status, 'completed')
  assert.equal(statusLabel({ status: 'completed', statusLabel: '计算完成' }), '计算完成')
  for (const value of ['draft', 'prepared', 'running', 'failed', 'superseded', 'obsolete']) assert.notEqual(statusLabel({ status: value }), value)
  assert.equal(statusLabel({ status: 'future_unknown_state' }), '业务状态未提供')
  assert.match(page, /activeCalculation\?\.status !== 'completed'/)
})

test('缺项直接显示对应服务端来源字段，不显示空规则或伪造原始数量', async () => {
  const html = await detailHtml({ project: '结构封边净长度', sheet: '三合一生产单', row: 9, sourceKey: '三合一生产单:9', state: 'missing', statusLabel: '缺少条件', value: null, reason: '封边方式未填', unit: 'm' }, [
    { name: '封边方式', cell: 'P9', rawValue: null },
    { name: '见光条件', cell: 'O9', rawValue: '白坯' },
    { name: '真实零值', cell: 'X9', rawValue: 0 },
  ])
  assert.match(html, /missing-calculation-trace/)
  assert.match(html, /封边方式 · P9/)
  assert.match(html, /来源未填/)
  assert.match(html, /白坯/)
  assert.match(html, /<dd>0 /)
  assert.doesNotMatch(html, /来源公式：.*原始数量，无公式/)
  assert.doesNotMatch(html, /中间精度|本次表达式/)
})

test('有真实来源公式的缺项保留公式，不伪造本次结果', async () => {
  const html = await detailHtml({ project: '竖线净长', sheet: '房门单', row: 11, sourceKey: '房门单:11', state: 'missing', statusLabel: '缺少条件', value: null, reason: '竖加未填', sourceFormula: '=J11+AP11' })
  assert.match(html, /来源公式（本项尚未算出）/)
  assert.match(html, /=J11\+AP11/)
  assert.doesNotMatch(html, /独立来源：|中间精度/)
})

test('已计算明细及真实零值仍保留数值、单位、公式、版本和独立对账', async () => {
  const html = await detailHtml({ project: '封边皮50净长度', sheet: '房门单', row: 14, sourceKey: '房门单:14', state: 'calculated', statusLabel: '对账一致', value: '0.000000', unit: 'm', expected: 0, difference: '0.000000', sourceCell: 'AA14', expression: 'N * 0', sourceFormula: '=N14*0', ruleVersion: 'preserved-version', precision: 28, scale: 6, rounding: 'ROUND_HALF_UP', inputs: [] })
  assert.match(html, /0.000000/)
  assert.match(html, /AA14|N \* 0|preserved-version/)
  assert.doesNotMatch(html, /missing-calculation-trace/)
})

test('用量提示区分规则输出、净量与毛量，未新增审批或生成动作', () => {
  assert.match(page, /正式材料身份、基本单位和单件／订单总量口径/)
  assert.match(page, /毛量保持未知，不等于已有净量无效/)
  assert.match(page, /不是要求逐个计算结果重新审批/)
  assert.doesNotMatch(page, /材料数量依据：未批准/)
  assert.match(panel, /PceEnterpriseListTable/)
  assert.match(panel, /total\.net \?\? '查看明细，不作数量合计'/)
})
