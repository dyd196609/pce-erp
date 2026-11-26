import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceChangeEvidence } from '../../src/meta/process/scm/priceApproval/priceChangeEvidence.js'
import { MATERIAL_PRICE_CONTEXT_TYPES, createMaterialPriceContext,
  detectMaterialPriceContextType } from '../../src/meta/process/scm/priceApproval/materialPriceContext.js'
import { createPriceReferenceProvider } from '../../src/meta/providers/priceReferenceProvider.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('Material Type Detection 按物料采购历史识别而非当前供应商',()=>{
  assert.equal(detectMaterialPriceContextType([]),MATERIAL_PRICE_CONTEXT_TYPES.NEW_MATERIAL)
  assert.equal(detectMaterialPriceContextType([{purchasePrice:100,supplierCode:'SUP-HISTORY'}]),
    MATERIAL_PRICE_CONTEXT_TYPES.EXISTING_MATERIAL)
  const provider=createPriceReferenceProvider({historyLoader:()=>[
    {materialCode:'MAT-001',supplierCode:'SUP-HISTORY',purchasePrice:100,purchaseDate:'2026-07-01'},
  ]})
  const facts=provider.load({currentQuotes:[{inquiryNo:'PI-001',materialCode:'MAT-001',
    supplierCode:'SUP-NEW',supplierName:'新供应商',quotePrice:120}]})
  assert.equal(facts.records[0].materialPriceContextType,'existing_material')
})

test('New Material Context 保留报价、比较、供应商和人工意见且不造历史',()=>{
  const context=createMaterialPriceContext({inquiryNo:'PI-NEW',materialCode:'MAT-NEW',materialName:'新物料',
    supplierCode:'SUP-01',supplierName:'供应商一',supplierQuote:88,
    comparisonResult:{summary:'报价最低'},manualAssessment:'待采购人员复核',historicalPurchases:[]})
  assert.equal(context.contextType,'new_material')
  assert.equal(context.priceReferenceContext,null)
  assert.deepEqual(Object.keys(context.newMaterialPriceAssessmentContext)
    .filter(key=>['materialCode','materialName','supplierQuote','comparisonResult','manualAssessment'].includes(key)),
  ['materialCode','materialName','supplierQuote','comparisonResult','manualAssessment'])
  assert.equal(context.newMaterialPriceAssessmentContext.supplierQuote,88)
})

test('Existing Material Context 提供最低、最近、日期、次数、当前价和变化比例',()=>{
  const context=createMaterialPriceContext({inquiryNo:'PI-OLD',materialCode:'MAT-OLD',currentQuote:120,
    historicalPurchases:[
      {purchasePrice:80,purchaseDate:'2026-05-01',supplierCode:'SUP-A'},
      {purchasePrice:100,purchaseDate:'2026-07-01',supplierCode:'SUP-B'},
    ]})
  const reference=context.priceReferenceContext
  assert.equal(context.contextType,'existing_material')
  assert.equal(reference.historicalLowestPurchasePrice,80)
  assert.equal(reference.latestPurchasePrice,100)
  assert.equal(reference.lastPurchaseDate,'2026-07-01')
  assert.equal(reference.historicalPurchaseCount,2)
  assert.equal(reference.currentQuote,120)
  assert.equal(reference.priceChangeRatio,0.2)
  assert.equal(reference.historicalPriceList.length,2)
})

test('Price Reference Evidence 只解释数值变化',()=>{
  const evidence=createPriceChangeEvidence({historyPrice:100,currentPrice:120,
    referenceDate:'2026-07-01',evidenceSource:'PurchaseOrderHistory'})
  assert.equal(evidence.changeRate,0.2)
  assert.equal(evidence.reasonablenessDecision,null)
  assert.equal(evidence.approvalDecision,null)
  assert.equal(evidence.supplierRecommendation,null)
})

test('Manual Decision Boundary 保持零自动决策与零业务写入',()=>{
  const context=createMaterialPriceContext({inquiryNo:'PI-BOUNDARY',materialCode:'MAT-NEW'})
  assert.equal(context.automaticQuoteRejection,false)
  assert.equal(context.automaticQuoteApproval,false)
  assert.equal(context.automaticSupplierRecommendation,false)
  assert.equal(context.purchaseOrderCreated,false)
  assert.equal(context.businessWriteCount,0)
  assert.equal(context.productionDataWritten,false)
})

test('核价页面包含新旧物料只读价格参考区域',()=>{
  const page=read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  for(const text of ['material-price-reference-region','暂无历史价格参考','历史最低采购价','最近采购价格',
    '历史采购次数','价格变化比例','采购人员核价意见'])assert.match(page,new RegExp(text))
  assert.match(page,/data-read-only="true"/)
  assert.doesNotMatch(page,/自动批准报价|自动拒绝报价|自动推荐供应商|自动生成采购订单/)
})
