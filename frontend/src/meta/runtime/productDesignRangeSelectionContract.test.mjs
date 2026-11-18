import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../pages/PdeProductDesignPage.vue', import.meta.url), 'utf8')
const runtime = readFileSync(new URL('./productDesignComprehensiveRuntime.js', import.meta.url), 'utf8')

for (const phrase of [
  '范围产品分类（目标查找，不修改业务字段）',
  '将本范围全部加入修改',
  '下方列表搜索、高级筛选、排序和分页仅用于浏览，不参与本范围计算。',
  '当前订单在所选分类/分组下无可加入的设计项。',
  '追加并按稳定ID去重',
  '确认只冻结并追加以上 ProductDesignItem 稳定ID',
]) {
  assert.ok(page.includes(phrase), `范围选择页面缺少受控口径：${phrase}`)
}

assert.match(page, /filterProductDesignRange\(rows\.value/)
assert.doesNotMatch(page, /filterProductDesignRange\(filteredRows\.value/)
assert.match(page, /assertCompleteProductDesignRangeSource\(rows\.value/)
assert.match(page, /resolveProductDesignTargets\(rows\.value, snapshot\.targetIds\)/)
assert.match(runtime, /appendProductDesignTargetIds\(selectedIds, rangeIds\)/)
assert.match(runtime, /expected !== \(rows \|\| \[\]\)\.length/)

console.log('productDesignRangeSelectionContract.test: PASS (scope/source/snapshot/dedupe contract)')
