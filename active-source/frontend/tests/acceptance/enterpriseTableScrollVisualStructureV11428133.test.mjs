import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')

test('DOM 强制为 BusinessTableScrollContainer → PceEnterpriseListTable → table',()=>{
  const source=read('src/meta/components/PceEnterpriseListTable.vue')
  const containerStart=source.indexOf('<BusinessTableScrollContainer')
  const pceRoot=source.indexOf('class="pce-enterprise-list-table"')
  const table=source.indexOf('<el-table')
  assert.ok(containerStart>=0&&containerStart<pceRoot&&pceRoot<table)
  assert.equal((source.match(/<BusinessTableScrollContainer/g)||[]).length,1)
})

test('真实表格视口恢复 overflow-x:auto 且无隐藏覆盖',()=>{
  const source=read('src/meta/components/PceEnterpriseListTable.vue')
  const rule=source.match(/\.pce-enterprise-table-scroll\s+:deep\(\.el-scrollbar__wrap\)[\s\S]*?\}/)?.[0]||''
  assert.match(rule,/overflow-x:\s*auto\s*!important/)
  assert.doesNotMatch(rule,/overflow-x:\s*hidden/)
  assert.match(source,/\.el-scrollbar__bar\.is-horizontal[\s\S]*?height:\s*12px/)
})

test('外层内容不再以 1600px 最小宽度撑开页面',()=>{
  const source=read('src/meta/components/BusinessTableScrollContainer.vue')
  const contentRule=source.match(/\.business-table-scroll-content\s*\{[\s\S]*?\}/)?.[0]||''
  assert.match(contentRule,/min-width:\s*0/)
  assert.match(contentRule,/max-width:\s*100%/)
  assert.doesNotMatch(contentRule,/min-width:\s*var\(--pce-table-min-width\)/)
  assert.match(source,/\.el-table__body[\s\S]*?min-width:\s*var\(--pce-table-min-width\)/)
})

test('所有公共 Flex 容器声明 min-width:0',()=>{
  const table=read('src/meta/components/PceEnterpriseListTable.vue')
  const toolbar=read('src/meta/components/StandardListToolbar.vue')
  for(const selector of ['pce-enterprise-row-actions','pce-enterprise-batch-filter','pce-enterprise-pagination']){
    const rule=table.match(new RegExp(`\\.${selector}\\s*\\{[\\s\\S]*?\\}`))?.[0]||''
    assert.match(rule,/display:\s*flex/)
    assert.match(rule,/min-width:\s*0/)
  }
  assert.match(toolbar,/\.standard-list-toolbar\s*\{[\s\S]*?min-width:\s*0/)
})

test('视觉诊断读取 Element Plus 实际滚动视口和滚动条高度',()=>{
  const runtime=read('src/meta/runtime/pceTableScrollRuntime.js')
  const container=read('src/meta/components/BusinessTableScrollContainer.vue')
  assert.match(runtime,/\.el-table__body-wrapper \.el-scrollbar__wrap/)
  assert.match(runtime,/scrollWidth > clientWidth/)
  assert.match(runtime,/scrollbarHeight > 0/)
  assert.match(container,/data-pce-scrollbar-height/)
  assert.match(container,/data-pce-no-page-overflow/)
})
