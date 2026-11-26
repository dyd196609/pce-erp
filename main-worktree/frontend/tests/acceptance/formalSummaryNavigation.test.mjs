import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFormalSummaryReturnContext,
  resolveFormalSummaryReturnTarget,
} from '../../src/meta/runtime/formalSummaryNavigation.js'

const summary = {
  sourceRecordId: 388,
  sourceVersion: 'ENG-V9',
  orderNo: 'SO-4-LINES',
  linkedOrders: [{ orderNo: 'SO-4-LINES', lineCount: 4 }],
}
const summaries = [summary]

test('all four order line identities map back to the same exact summary', () => {
  for (const salesOrderItemId of [7101, 7102, 7103, 7104]) {
    const context = buildFormalSummaryReturnContext({ summary, line: { salesOrderItemId, orderNo: 'SO-4-LINES' } })
    const target = resolveFormalSummaryReturnTarget({ context, summaries, selectedLine: { salesOrderItemId, orderNo: 'SO-4-LINES' } })
    assert.equal(target?.summary, summary)
    assert.equal(target?.lineCount, 4)
    assert.equal(target?.sourceRecordId, '388')
  }
})

test('refresh restores the exact source summary from URL context', () => {
  const target = resolveFormalSummaryReturnTarget({
    routeQuery: { returnSourceRecord: '388', returnOrderNo: 'SO-4-LINES', returnEngineeringVersion: 'ENG-V9', returnLineCount: '4' },
    summaries,
    selectedLine: { salesOrderItemId: 7102, orderNo: 'SO-4-LINES' },
  })
  assert.equal(target?.summary, summary)
  assert.equal(target?.engineeringVersion, 'ENG-V9')
})

test('direct line entry only recovers a unique exact linked order and never crosses orders', () => {
  assert.equal(resolveFormalSummaryReturnTarget({ summaries, selectedLine: { orderNo: 'SO-4-LINES' } })?.summary, summary)
  assert.equal(resolveFormalSummaryReturnTarget({ routeQuery: { returnSourceRecord: '388', returnOrderNo: 'OTHER' }, summaries, selectedLine: { orderNo: 'OTHER' } }), null)
  assert.equal(resolveFormalSummaryReturnTarget({ summaries: [...summaries, { ...summary, sourceRecordId: 389 }], selectedLine: { orderNo: 'SO-4-LINES' } }), null)
})
