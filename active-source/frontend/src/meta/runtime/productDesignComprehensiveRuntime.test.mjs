import assert from 'node:assert/strict'

import {
  appendProductDesignTargetIds,
  assertCompleteProductDesignRangeSource,
  createProductDesignRangeSnapshot,
  filterProductDesignRange,
  productDesignSelectionKey,
  reconcileProductDesignTargets,
  resolveProductDesignTargets,
  summarizeProductDesignSelection,
} from './productDesignComprehensiveRuntime.js'

const rows = [
  { id: 1, designRevision: { designNotes: 'A', materialId: 10 } },
  { id: 2, designRevision: { designNotes: 'B', materialId: 11 } },
  { id: 3, designRevision: { designNotes: 'C', materialId: 12 } },
]

assert.equal(productDesignSelectionKey([rows[1], rows[0]]), '1|2')

const fromPicker = reconcileProductDesignTargets([rows[0]], [1, 2])
assert.deepEqual(fromPicker.add, [2])
assert.deepEqual(fromPicker.remove, [])

const fromTable = reconcileProductDesignTargets([rows[0], rows[1]], [2, 3])
assert.deepEqual(fromTable.add, [3])
assert.deepEqual(fromTable.remove, [rows[0]])

const cleared = reconcileProductDesignTargets([rows[1], rows[2]], [])
assert.deepEqual(cleared.add, [])
assert.deepEqual(cleared.remove, [rows[1], rows[2]])

const refreshedRows = [
  { id: 6, itemNo: 'SO202609180003-DES-02-SRC-0008' },
  { id: 5, itemNo: 'SO202609180003-DES-01-SRC-0007' },
  { id: 3, itemNo: 'SO202609180003-DES-01-SRC-0005' },
  { id: 7, itemNo: 'SO202609180003-DES-02-SRC-0009' },
  { id: 4, itemNo: 'SO202609180003-DES-01-SRC-0006' },
]
const restored = resolveProductDesignTargets(refreshedRows, [3, 4, 5])
assert.deepEqual(restored.targets.map(row => row.itemNo), [
  'SO202609180003-DES-01-SRC-0005',
  'SO202609180003-DES-01-SRC-0006',
  'SO202609180003-DES-01-SRC-0007',
])
assert.deepEqual(restored.missingIds, [])
assert.equal(restored.targets[0], refreshedRows[2])
assert.deepEqual(resolveProductDesignTargets(refreshedRows, [3, 902]).missingIds, ['902'])

const draftForm = { designNotes: '既有说明', documentReferences: ['图纸-A'] }
const draftSnapshot = {
  ...draftForm,
  documentReferences: [...draftForm.documentReferences],
}
draftForm.documentReferences.push('图纸-B')
assert.deepEqual(draftSnapshot.documentReferences, ['图纸-A'])

const summary = summarizeProductDesignSelection(rows.slice(0, 2))
assert.equal(summary.form.designNotes, null)
assert.ok(summary.mixedFields.includes('designNotes'))
assert.ok(summary.mixedFields.includes('materialId'))

const emptySummary = summarizeProductDesignSelection([])
assert.deepEqual(emptySummary.mixedFields, [])
assert.equal(emptySummary.form.designNotes, null)
assert.deepEqual(emptySummary.form.documentReferences, [])

const rangeRows = Array.from({ length: 71 }, (_, index) => ({
  id: 500 + index * 7,
  orderNo: 'SO-RANGE-001',
  itemNo: `SO-RANGE-001-${String(index + 1).padStart(4, '0')}`,
  productName: index < 5 ? 'A类来源' : index < 8 ? 'B类来源' : index < 70 ? 'C类来源' : 'D类来源',
  productCategoryId: index < 8 ? 31 : 47,
  designGroup: index < 5 ? 'DES-01' : index < 8 ? 'DES-02' : index < 70 ? 'DES-03' : 'DES-04',
  installationPosition: `安装位置-${index + 1}`,
  sourcePosition: `来源-${index + 1}`,
  version: 1,
}))
assert.equal(assertCompleteProductDesignRangeSource(rangeRows, { expectedRecordCount: 71, orderNo: 'SO-RANGE-001' }), true)
assert.equal(filterProductDesignRange(rangeRows, { designGroup: 'DES-03' }).length, 62)
assert.equal(filterProductDesignRange(rangeRows, { productCategoryId: 31 }).length, 8)
assert.equal(filterProductDesignRange(rangeRows, { productCategoryId: 31, designGroup: 'DES-02' }).length, 3)
assert.equal(filterProductDesignRange(rangeRows, { productCategoryId: 999, designGroup: 'DES-02' }).length, 0)

const outsideSelected = [rangeRows[0], rangeRows[70]]
const rangeSnapshot = createProductDesignRangeSnapshot({
  rows: rangeRows,
  selectedRows: outsideSelected,
  productCategoryId: 47,
  designGroup: 'DES-03',
  orderNo: 'SO-RANGE-001',
})
assert.equal(rangeSnapshot.matchedCount, 62)
assert.equal(rangeSnapshot.alreadySelectedCount, 0)
assert.equal(rangeSnapshot.newCount, 62)
assert.equal(rangeSnapshot.selectedOutsideCount, 2)
assert.equal(rangeSnapshot.finalCount, 64)
assert.deepEqual(rangeSnapshot.finalIds.slice(0, 2), outsideSelected.map(row => row.id))
assert.equal(new Set(rangeSnapshot.finalIds.map(String)).size, 64)
assert.deepEqual(appendProductDesignTargetIds(rangeSnapshot.finalIds, rangeSnapshot.targetIds), rangeSnapshot.finalIds)

const allSnapshot = createProductDesignRangeSnapshot({ rows: rangeRows, selectedRows: [], orderNo: 'SO-RANGE-001' })
assert.equal(allSnapshot.matchedCount, 71)
assert.equal(allSnapshot.finalCount, 71)
assert.notEqual(allSnapshot.targetIds[20], 21, '稳定ID不得碰巧等于分页行号')

const versionBefore = rangeSnapshot.targets[0].version
rangeRows.find(row => String(row.id) === String(rangeSnapshot.targetIds[0])).version += 1
assert.equal(rangeSnapshot.targets[0].version, versionBefore, '确认快照不得被后续行版本变化改写')

assert.throws(
  () => assertCompleteProductDesignRangeSource(rangeRows.slice(0, 20), { expectedRecordCount: 71, orderNo: 'SO-RANGE-001' }),
  error => error.code === 'PRODUCT_DESIGN_RANGE_SOURCE_INCOMPLETE',
)
assert.throws(
  () => assertCompleteProductDesignRangeSource([...rangeRows, { ...rangeRows[0] }], { expectedRecordCount: 72, orderNo: 'SO-RANGE-001' }),
  error => error.code === 'PRODUCT_DESIGN_RANGE_ID_INVALID',
)
assert.throws(
  () => assertCompleteProductDesignRangeSource([{ ...rangeRows[0], orderNo: 'SO-OTHER' }], { expectedRecordCount: 1, orderNo: 'SO-RANGE-001' }),
  error => error.code === 'PRODUCT_DESIGN_RANGE_ORDER_MISMATCH',
)

console.log('productDesignComprehensiveRuntime.test: PASS (stable-id picker/table/readback + complete range snapshot identity)')
