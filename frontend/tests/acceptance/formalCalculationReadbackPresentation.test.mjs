import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { calculationInputLines, calculationTraceRows, formalSavedState, FORMAL_READBACK_CONTRACT, readSelectedCalculationDetail, savedPageContextForSelection } from '../../src/meta/runtime/formalCalculationReadbackPresentation.js'

test('renders nested formal object, actual rule inputs and source without object coercion', () => {
  const lines = calculationInputLines({
    object: { designItemNo: 'DES-1', baselineItemId: 72, revision: 6, inputAuthority: 'CONFIRMED_ORDER_ENGINEERING_BASELINE_ITEM', materialId: null },
    ruleInputs: [{ key: 'J', name: '原始高度', value: '2045.000000', unit: 'mm', sourceCell: 'J11' }], sourceCell: 'N11', sourceFormula: '=J11-10',
  }).join('\n')
  assert.match(lines, /设计对象编号：DES-1/)
  assert.match(lines, /基线项ID：72/)
  assert.match(lines, /设计修订：6/)
  assert.match(lines, /实际计算输入 · 原始高度（J）：2045.000000 mm；来源单元格：J11/)
  assert.match(lines, /材料ID：未提供/)
  assert.doesNotMatch(lines, /\[object Object\]/)
})

test('preserves legacy scalar/decimal/unit input, zero, null and unknown nested fields', () => {
  const text = calculationInputLines({ opening_height: { value: { decimal: '0' }, unit: 'mm' }, missing: null, custom: { x: [0, null, false] } }).join('\n')
  assert.match(text, /门洞高度：0 mm/)
  assert.match(text, /missing：未提供/)
  assert.match(text, /x：0；未提供；否/)
  assert.doesNotMatch(text, /\[object Object\]/)
  assert.deepEqual(calculationInputLines(null), ['无输入快照'])
})

test('formal trace only uses the selected persisted record, with no fabricated legacy baseline', () => {
  assert.deepEqual(calculationTraceRows({ id: 99, trace: { legacy: true } }), [])
  const record = { salesOrderItemId: 3, orderEngineeringInstanceId: 2, trace: {
    sourceReference: { id: 11, sourceVersion: 'SOURCE-V1' }, baselineReference: { id: 2, baselineNo: 'BASE-002', orderNo: 'SO-A', selectedItemCount: 5 },
    objectInputSnapshot: [{ designItemNo: 'DES-1', baselineItemId: 72, sourceKey: '房门单:11', input: { revision: 6 } }],
    ruleGraphSnapshot: [{ id: 11, ruleCode: 'APPROVED_SOURCE_NET', version: 'V1' }],
  } }
  const text = calculationTraceRows(record).map(row => row.value).join('\n')
  assert.match(text, /SO-A；订单行ID 3；实例ID 2/)
  assert.match(text, /BASE-002（ID 2）/)
  assert.match(text, /DES-1／R6/)
  assert.match(text, /SOURCE-V1/)
})

test('saved-state labels are server facts; old API, absence and errors are unknown, never false zero', () => {
  const state = { contractVersion: FORMAL_READBACK_CONTRACT, code: 'PARTIALLY_SAVED', label: '本订单1/4行已保存正式核算' }
  assert.equal(formalSavedState(state), state)
  for (const value of [undefined, { code: 'NOT_SAVED', label: '正式核算尚未保存' }]) {
    assert.equal(formalSavedState(value).label, '正式核算保存状态待读取')
  }
  assert.equal(formalSavedState(state, true).label, '正式核算保存状态读取失败')
})

test('page retains one canonical view and consumes per-line state, trace formatter and existing request guards', () => {
  const page = readFileSync(new URL('../../src/meta/pages/PdeOrderEngineeringCalculationPage.vue', import.meta.url), 'utf8')
  assert.match(page, /formalSavedState\(row\.formalCalculationState/)
  assert.match(page, /formalOrderSavedState\.label/)
  assert.match(page, /formalSelectedSavedState\.label/)
  assert.match(page, /calculationInputLines\(row\.inputSnapshot\)/)
  assert.match(page, /calculationTraceRows\(activeCalculation\)/)
  assert.match(page, /requestSequence !== formalReadSequence/)
  assert.match(page, /requestSequence !== conditionPreflightSequence/)
  assert.match(page, /pdeApi\.engineeringCalculation\(id\)/)
  assert.match(page, /unwrap\(await pdeApi\.engineeringCalculation\(id\)\)\.calculation/)
  assert.match(page, /if \(selected\) await chooseCalculation\(selected\)/)
  assert.match(page, /requestedRecord && !selected/)
  assert.match(page, /requestSequence === calculationDetailSequence/)
  assert.doesNotMatch(page, /<td>正式核算尚未保存<\/td>|正式核算仍未保存|尚未形成正式订单核算记录|object=\$\{/)
})

test('loads original detail endpoint record, not the list without trace; rejects scope mismatch', async () => {
  const row = { id: 3, companyId: 1, salesOrderItemId: 3, orderEngineeringInstanceId: 2, sourceRecordId: 11 }
  const detail = { ...row, trace: { baselineReference: { id: 2 } } }
  const calls = []
  assert.equal(await readSelectedCalculationDetail(row, async id => { calls.push(id); return detail }, () => true), detail)
  assert.deepEqual(calls, [3])
  for (const field of Object.keys(row)) {
    await assert.rejects(readSelectedCalculationDetail(row, async () => ({ ...detail, [field]: 999 }), () => true), /身份/)
  }
  await assert.rejects(readSelectedCalculationDetail(row, async () => { throw new Error('read failed') }, () => true), /read failed/)
})

test('slow detail cannot replace a new selection or a returned summary', async () => {
  let current = true, finish
  const read = readSelectedCalculationDetail({ id: 3 }, () => new Promise(resolve => { finish = resolve }), () => current)
  current = false
  finish({ id: 3, trace: { previous: true } })
  assert.equal(await read, null)
})

test('native locators are explicitly not applicable; Excel cells stay intact', () => {
  const native = calculationInputLines({object:{sourceIdentity:{type:'NATIVE_DESIGN_REVISION'},sourceSheet:null,sourceRow:null},sourceCell:null,sourceFormula:null}).join('\n')
  assert.match(native,/来源工作表：不适用／原生设计来源/)
  assert.match(native,/来源单元格：不适用／原生设计来源/)
  assert.match(calculationInputLines({sourceCell:'J11',sourceFormula:'=J11-10'}).join('\n'),/来源单元格：J11/)
})

test('saved context cannot leak across company, order line, instance or record switches', () => {
  const record={id:100,companyId:1,salesOrderItemId:8,orderEngineeringInstanceId:7,sourceRecordId:14}
  const context={...record,calculationId:100,contractVersion:'PDE-SAVED-CALCULATION-CONTEXT-V1',readStatus:'loaded',rows:[{revision:2}]}
  record.savedPageContext=context
  assert.equal(savedPageContextForSelection(record,{salesOrderItemId:8}),context)
  assert.equal(savedPageContextForSelection(record,{salesOrderItemId:9}),null)
  for(const field of ['calculationId','companyId','orderEngineeringInstanceId','sourceRecordId']) {
    assert.equal(savedPageContextForSelection({...record,savedPageContext:{...context,[field]:999}},{salesOrderItemId:8}),null)
  }
  assert.equal(savedPageContextForSelection({...record,savedPageContext:{...context,readStatus:'read_failed'}},{salesOrderItemId:8}),null)
})

test('mismatched server context refuses before any panel may display it',async()=>{
  const row={id:100,companyId:1,salesOrderItemId:8,orderEngineeringInstanceId:7,sourceRecordId:14}
  await assert.rejects(readSelectedCalculationDetail(row,async()=>({...row,savedPageContext:{...row,readStatus:'loaded',calculationId:101}}),()=>true),/不属于/)
})
