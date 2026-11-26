import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createUnifiedFilterSchema } from '../../src/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '../../src/meta/runtime/remoteSelectOptionsProvider.js'
import { resolveRemoteListFilterOptions } from '../../src/meta/runtime/listFilterRuntime.js'
import { createBatchFilterRuntime } from '../../src/meta/runtime/batchFilterRuntime.js'
import { createPriceReferenceContext } from '../../src/meta/process/scm/priceApproval/priceReferenceContext.js'
import { createPriceReferenceProvider } from '../../src/meta/providers/priceReferenceProvider.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('LIST-RUNTIME-002 将滚动条锁定在表格区域',()=>{
  const container=read('src/meta/components/BusinessTableScrollContainer.vue')
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  assert.match(container,/overflow-x:\s*auto/)
  assert.match(container,/--pce-table-min-width/)
  assert.match(container,/el-scrollbar__bar\.is-horizontal/)
  assert.match(table,/overflow-x:\s*hidden/)
})

test('LIST-FILTER-002 支持五类字段和远程编号选择',async()=>{
  const provider=createRemoteSelectOptionsProvider({providerCode:'TEST_REMOTE'})
  const schema=createUnifiedFilterSchema({optionsProvider:provider,filterFields:[
    {field:'keyword',label:'关键字',type:'text'},
    {field:'status',label:'状态',type:'select',options:[{label:'有效',value:'active'}]},
    {field:'requestNo',label:'申请编号',type:'remote-select',optionsProvider:provider},
    {field:'createdAt',label:'日期',type:'date'},
    {field:'amount',label:'金额',type:'number-range'},
  ]})
  assert.deepEqual(schema.map(item=>item.declaredType),['text','select','remote-select','date','number-range'])
  const options=await resolveRemoteListFilterOptions(schema[2],'002',[{requestNo:'PR-001'},{requestNo:'PR-002'}])
  assert.deepEqual(options.map(item=>item.value),['PR-002'])
})

test('Batch Filter Runtime 从选择集生成字段过滤值',()=>{
  const runtime=createBatchFilterRuntime({schema:[{field:'supplierCode',label:'供应商编号'}]})
  const result=runtime.createFilter([{supplierCode:'SUP-01'},{supplierCode:'SUP-02'},{supplierCode:'SUP-01'}],'supplierCode')
  assert.deepEqual(result.values,['SUP-01','SUP-02'])
  assert.throws(()=>runtime.createFilter([], 'supplierCode'),/SELECTION_EMPTY/)
})

test('Price Reference Context 只读展示历史价格且不做业务判断',()=>{
  const context=createPriceReferenceContext({inquiryNo:'PI-001',materialCode:'MAT-001',
    historicalPurchasePrice:100,lastPurchaseDate:'2026-07-01',currentQuote:110})
  assert.equal(context.priceChangeRatio,0.1)
  assert.equal(context.automaticReasonablenessDecision,false)
  assert.equal(context.automaticQuoteRejection,false)
  assert.equal(context.businessStateAdvanced,false)
  assert.equal(context.businessWriteCount,0)
})

test('Price Reference Provider 复用历史采购事实且缺失时不造价',()=>{
  const provider=createPriceReferenceProvider({historyLoader:()=>[
    {materialCode:'MAT-001',supplierCode:'SUP-01',purchasePrice:80,purchaseDate:'2026-06-01'},
    {materialCode:'MAT-001',supplierCode:'SUP-01',purchasePrice:90,purchaseDate:'2026-07-01'},
  ]})
  const facts=provider.load({currentQuotes:[
    {inquiryNo:'PI-001',materialCode:'MAT-001',supplierCode:'SUP-01',quotePrice:99},
    {inquiryNo:'PI-001',materialCode:'MAT-002',supplierCode:'SUP-01',quotePrice:50},
  ]})
  assert.equal(facts.records[0].historicalPurchasePrice,90)
  assert.equal(facts.records[0].priceChangeRatio,0.1)
  assert.equal(facts.records[1].historicalPurchasePrice,null)
  assert.equal(facts.businessWriteCount,0)
  assert.equal(facts.automaticDecisionCount,0)
})

test('SCM 三个宽表编号字段使用 remote-select，核价展示四项参考',()=>{
  const pages=[read('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
    read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
    read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')]
  for(const page of pages){assert.match(page,/type:'remote-select'/);assert.match(page,/min-width=/)}
  const price=read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  for(const label of ['历史采购价','最近采购日期','当前报价','价格变化比例'])assert.match(price,new RegExp(label))
  assert.doesNotMatch(price,/自动判断价格合理|自动拒绝报价/)
})
