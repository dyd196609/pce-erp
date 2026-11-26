import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPceTableScrollRuntime, measureHorizontalScroll, resolveListWidthPolicy } from '../../src/meta/runtime/pceTableScrollRuntime.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('List Width Policy 固化 normal/wide/ultra-wide 下限',()=>{
  assert.equal(resolveListWidthPolicy({widthPolicy:'normal'}).resolvedMinWidth,1200)
  assert.equal(resolveListWidthPolicy({widthPolicy:'wide',requestedMinWidth:'1320px'}).resolvedMinWidth,1600)
  assert.equal(resolveListWidthPolicy({widthPolicy:'ultra-wide',requestedMinWidth:1700}).resolvedMinWidth,1800)
  assert.equal(resolveListWidthPolicy({widthPolicy:'wide',requestedMinWidth:'1920px'}).resolvedMinWidth,1920)
  assert.equal(resolveListWidthPolicy({widthPolicy:'wide',requestedMinWidth:'100%'}).resolvedMinWidth,1600)
  assert.throws(()=>resolveListWidthPolicy({widthPolicy:'wide',requestedMinWidth:'90%'}),/MIN_WIDTH_INVALID/)
  assert.throws(()=>resolveListWidthPolicy({widthPolicy:'unknown'}),/POLICY_INVALID/)
})

test('PCE Table Scroll Runtime 锁定滚动所有权与容器结构',()=>{
  const runtime=createPceTableScrollRuntime({widthPolicy:'wide'})
  assert.equal(runtime.horizontalScrollOwner,'element-plus-native')
  assert.equal(runtime.pageOverflowX,'hidden')
  assert.equal(runtime.cardOverflowX,'hidden')
  assert.equal(runtime.tableOverflowX,'hidden')
  assert.equal(runtime.width.cssMinWidth,'1600px')
})

test('Horizontal Scroll Visible Check 使用真实几何条件而非 CSS 字符串',()=>{
  const viewport={scrollWidth:1800,clientWidth:960,getBoundingClientRect:()=>({width:960,height:420})}
  const scrollbar={getBoundingClientRect:()=>({height:12})}
  const container={scrollWidth:960,clientWidth:960,getBoundingClientRect:()=>({width:960,height:420}),
    querySelector:selector=>selector.includes('el-scrollbar__wrap')?viewport
      :selector.includes('is-horizontal')?scrollbar:selector.includes('action')?{}:null}
  const page={scrollWidth:1200,clientWidth:1200}
  const facts=measureHorizontalScroll(container,{pageElement:page,getStyle:()=>({overflowX:'auto',display:'block',visibility:'visible'})})
  assert.equal(facts.scrollWidth>facts.clientWidth,true)
  assert.equal(facts.horizontalScrollVisible,true)
  assert.equal(facts.scrollbarHeight,12)
  assert.equal(facts.scrollTarget,'element-plus-body-scrollbar')
  assert.equal(facts.noPageOverflow,true)
  assert.equal(facts.stickyColumnsInsideContainer,true)
  const hiddenViewport={...viewport,getBoundingClientRect:()=>({width:0,height:0})}
  const hidden=measureHorizontalScroll({...container,querySelector:selector=>selector.includes('el-scrollbar__wrap')?hiddenViewport
    :selector.includes('is-horizontal')?scrollbar:null},
    {pageElement:{scrollWidth:1300,clientWidth:1200},getStyle:()=>({overflowX:'auto',display:'block',visibility:'visible'})})
  assert.equal(hidden.horizontalScrollVisible,false)
  assert.equal(hidden.noPageOverflow,false)
})

test('公共 TableContainer 包含 Table 与固定操作列并由 Element Plus 显示底部滚动条',()=>{
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  const container=read('src/meta/components/BusinessTableScrollContainer.vue')
  assert.match(table,/<BusinessTableScrollContainer[\s\S]*?<el-table[\s\S]*?fixed="right"[\s\S]*?<\/BusinessTableScrollContainer>/)
  assert.match(container,/data-pce-table-container-contract="TABLE-SCROLL-RUNTIME-001"/)
  assert.match(container,/data-pce-horizontal-scroll-visible/)
  assert.match(container,/data-pce-horizontal-scroll-owner="element-plus-native"/)
  assert.doesNotMatch(container,/::-webkit-scrollbar/)
})

test('SCM 四页继续复用唯一企业列表组件',()=>{
  const pages=[read('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
    read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
    read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),
    read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')]
  for(const page of pages){assert.match(page,/PceEnterpriseListTable/);assert.match(page,/min-width=/);assert.doesNotMatch(page,/overflow-x\s*:/)}
})
