import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { normalizeListFilterSchema, resolveListFilterOptions } from '../../src/meta/runtime/listFilterRuntime.js'
import { createListActionColumnRuntime } from '../../src/meta/runtime/listActionColumnRuntime.js'
import { assertListPageContainerRule, LIST_PAGE_CONTAINER_RULE } from '../../src/meta/runtime/listPageContainerRule.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('List Filter Runtime 统一 text/select/date/number 与选项来源',()=>{
  const schema=normalizeListFilterSchema([
    {field:'keyword',label:'关键字',type:'text',optionsSource:'none'},
    {field:'status',label:'状态',type:'select',optionsSource:'StateContract',options:[{label:'启用',value:'active'}]},
    {field:'businessDate',label:'业务日期',type:'date',optionsSource:'none'},
    {field:'amount',label:'金额',type:'number',optionsSource:'none'},
  ])
  assert.deepEqual(schema.map(item=>item.type),['text','select','date','number'])
  assert.equal(schema.every(item=>item.field&&item.label&&item.optionsSource),true)
  assert.deepEqual(resolveListFilterOptions(schema[1],[]),[{label:'启用',value:'active'}])
  const current=normalizeListFilterSchema([{field:'supplierCode',label:'供应商',type:'select',optionsSource:'current_result'}])[0]
  assert.deepEqual(resolveListFilterOptions(current,[{supplierCode:'S1'},{supplierCode:'S2'},{supplierCode:'S1'}]).map(item=>item.value),['S1','S2'])
  const legacySearchable=normalizeListFilterSchema([{field:'supplierName',label:'供应商',type:'searchable_select'}])[0]
  assert.equal(legacySearchable.filterType,'select')
  assert.equal(legacySearchable.optionsSource,'current_result')
})

test('Action Column Runtime 仅按 Action Contract 与行状态解析按钮',()=>{
  const runtime=createListActionColumnRuntime({stateField:'status',contracts:[
    {actionCode:'EDIT',actionName:'编辑',allowedStates:['draft']},
    {actionCode:'VIEW',actionName:'查看',allowedStates:['draft','completed']},
  ]})
  assert.deepEqual(runtime.resolve({status:'draft'}).map(item=>item.actionCode),['EDIT','VIEW'])
  assert.deepEqual(runtime.resolve({status:'completed'}).map(item=>item.actionCode),['VIEW'])
  assert.equal(runtime.resolve({status:'completed'})[0].source,'Action Contract')
})

test('统一表格容器保持页面无横向滚动、表格内部滚动',()=>{
  assert.equal(assertListPageContainerRule(),LIST_PAGE_CONTAINER_RULE)
  const container=read('src/meta/components/BusinessTableScrollContainer.vue')
  const shell=read('src/meta/components/PceListPageShell.vue')
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  assert.match(container,/overflow-x:\s*auto/)
  assert.match(container,/--pce-table-min-width/)
  assert.match(shell,/overflow-x:\s*hidden/)
  assert.match(table,/fixed="left"/)
  assert.match(table,/fixed="right"/)
  assert.match(table,/data-pce-action-source="Action Contract"/)
})

test('SCM 三页复用统一筛选、操作列和滚动基座',()=>{
  const supplier=read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue')
  const comparison=read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
  const price=read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  for(const source of [supplier,comparison,price]){
    assert.match(source,/PceEnterpriseListTable/)
    assert.match(source,/action-contracts/)
    assert.match(source,/action-state-field/)
    assert.match(source,/optionsSource/)
    assert.doesNotMatch(source,/<template\s+#actions/)
  }
  assert.match(supplier,/supplier-quote-horizontal-scroll/)
  assert.match(comparison,/quote-comparison-horizontal-scroll/)
  assert.match(price,/price-approval-horizontal-scroll/)
})
