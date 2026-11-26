import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createUnifiedFilterSchema } from '../../src/meta/runtime/unifiedFilterSchema.js'
import { createListContainerRuntime } from '../../src/meta/runtime/listContainerRuntime.js'
import { createListActionColumnRuntime } from '../../src/meta/runtime/listActionColumnRuntime.js'
import { SCM_PRICE_APPROVAL_LIST_ACTIONS } from '../../src/meta/process/scm/scmUnifiedListActionContractsV1142813.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('ListContainer Runtime 隔离页面、Card 与表格横向滚动',()=>{
  const runtime=createListContainerRuntime({tableMinWidth:1480})
  assert.equal(runtime.pageStyle.overflowX,'hidden')
  assert.equal(runtime.cardStyle.minWidth,0)
  assert.equal(runtime.tableStyle.overflowX,'auto')
  assert.equal(runtime.tableMinWidth,'1480px')
  assert.throws(()=>createListContainerRuntime({tableMinWidth:'auto'}),/LIST_CONTAINER_MIN_WIDTH_INVALID/)
})

test('UnifiedFilterSchema 强制 filterFields/optionsProvider 并支持四类字段',()=>{
  const optionsProvider={providerCode:'TEST_OPTIONS',loadOptions:()=>[]}
  const schema=createUnifiedFilterSchema({optionsProvider,filterFields:[
    {field:'keyword',label:'关键字',type:'text'},
    {field:'status',label:'状态',type:'select',options:[{label:'有效',value:'active'}]},
    {field:'date',label:'日期',type:'date'},
    {field:'amount',label:'金额',type:'number-range'},
  ]})
  assert.deepEqual(schema.map(item=>item.declaredType),['text','select','date','number-range'])
  assert.equal(schema[3].filterType,'numberRange')
  assert.throws(()=>createUnifiedFilterSchema({filterFields:[{field:'x',label:'X',type:'text'}]}),/OPTIONS_PROVIDER_REQUIRED/)
})

test('核价操作列仅暴露查看核价和进入供应商推荐',()=>{
  const runtime=createListActionColumnRuntime({contracts:SCM_PRICE_APPROVAL_LIST_ACTIONS,stateField:'preparationStatus'})
  const actions=runtime.resolve({preparationStatus:'price_approval_preparation_ready'})
  assert.deepEqual(actions.map(item=>item.actionCode),['VIEW_PRICE_APPROVAL','OPEN_SUPPLIER_RECOMMENDATION'])
  assert.equal(actions.some(item=>item.actionCode.includes('PURCHASE_ORDER')),false)
})

test('SCM 四页统一声明筛选 Provider、Action Contract 与内部滚动',()=>{
  const sources=[
    read('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
    read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
    read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),
    read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue'),
  ]
  for(const source of sources){
    assert.match(source,/filterFields/)
    assert.match(source,/optionsProvider/)
    assert.match(source,/createUnifiedFilterSchema/)
    assert.match(source,/action-contracts/)
    assert.match(source,/action-state-field/)
    assert.doesNotMatch(source,/<template\s+#actions/)
  }
  const inquiry=sources[0]
  for(const field of ['inquiryNo','sourceRequestNo','buyerName','businessStatusCode','processStatusCode']) assert.match(inquiry,new RegExp(field))
  const comparison=sources[2]
  for(const field of ['sourceInquiryId','materialCode','supplierCodes','comparisonStatus']) assert.match(comparison,new RegExp(field))
})

test('公共列表默认操作列且 Card 不被宽表撑开',()=>{
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  const shell=read('src/meta/components/PceListPageShell.vue')
  const container=read('src/meta/components/BusinessTableScrollContainer.vue')
  assert.match(table,/showActionColumn:\s*\{\s*type:\s*Boolean,\s*default:\s*true/)
  assert.match(table,/data-pce-default-action-column="true"/)
  assert.match(shell,/\.el-card__body/)
  assert.match(shell,/min-width:\s*0/)
  assert.match(container,/createListContainerRuntime/)
  assert.match(container,/overflow-x:\s*auto/)
})
