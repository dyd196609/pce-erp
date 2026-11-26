import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPceTableColumnRuntime, createSupplierComparisonColumnGroups } from '../../src/meta/runtime/pceTableColumnRuntime.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('报价比较路由只映射统一页面壳与唯一工作台页面',()=>{
  const router=read('src/router/index.js')
  assert.match(router,/path:\s*'scm\/quote-comparisons'[\s\S]*?wrapPceListPage\('quote-comparison-workbench',[\s\S]*?ScmQuoteComparisonWorkbenchPage\.vue/)
})

test('报价比较完整经过统一列表与单一滚动拥有者',()=>{
  const page=read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  const shell=read('src/meta/components/PceListPageShell.vue')
  assert.match(page,/<PceEnterpriseListTable/)
  assert.doesNotMatch(page,/<el-table(?:\s|>)/)
  assert.match(table,/<BusinessTableScrollContainer[\s\S]*?<div[\s\S]*?class="pce-enterprise-list-table"[\s\S]*?<el-table/)
  assert.match(shell,/class="pce-list-page-content"[\s\S]*?data-pce-list-container-runtime="LIST-RUNTIME-002"/)
  assert.match(shell,/\.pce-list-page-content\s*\{[\s\S]*?min-width:\s*0[\s\S]*?overflow-x:\s*hidden/)
})

test('报价比较动态供应商列由统一列运行层生成',()=>{
  const page=read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
  assert.match(page,/createPceTableColumnRuntime/)
  assert.match(page,/createSupplierComparisonColumnGroups/)
  assert.match(page,/v-for="column in columnRuntime\.dynamicGroups\.flatMap/)
  assert.doesNotMatch(page,/prop="supplier[ABC](?:Name|Price)?"/)
  assert.match(page,/:min-width="columnRuntime\.minWidth"/)
})

test('动态列宽按供应商数量增长且至少进入宽表策略',()=>{
  const three=createPceTableColumnRuntime({baseReservedWidth:850,
    dynamicGroups:createSupplierComparisonColumnGroups(3),widthPolicy:'wide'})
  const five=createPceTableColumnRuntime({baseReservedWidth:850,
    dynamicGroups:createSupplierComparisonColumnGroups(5),widthPolicy:'wide'})
  assert.equal(three.dynamicColumnCount,6)
  assert.equal(five.dynamicColumnCount,10)
  assert.ok(three.minWidth>=1600)
  assert.ok(five.minWidth>three.minWidth)
  assert.equal(five.calculatedWidth,2350)
})

test('页面不建立私有滚动所有权且操作列继续来自 Action Contract',()=>{
  const page=read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
  assert.doesNotMatch(page,/overflow-x\s*:/)
  assert.match(page,/:action-contracts="SCM_QUOTE_COMPARISON_LIST_ACTIONS"/)
  assert.match(page,/action-state-field="comparisonStatus"/)
})
