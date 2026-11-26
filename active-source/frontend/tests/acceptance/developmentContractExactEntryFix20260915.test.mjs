import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { CRM_ORDER_PROCESS_NODES } from '../../src/meta/runtime/crmOrderProcessRegistry.js'
import { buildPageDocumentTitle } from '../../src/meta/runtime/pageTitleManager.js'

test('接单节点进入工作台且两种打开方式共享同一目标', () => {
  const intake = CRM_ORDER_PROCESS_NODES.find(row => row.nodeCode === 'order-intake')
  assert.ok(intake)
  assert.equal(intake.nodeName, '接单')
  assert.equal(intake.pageUrl, '/sales/orders?entry=process-center&module=CRM&process=CRM_ORDER_OPERATION&node=order-intake')
  assert.equal(intake.pageRoute, intake.pageUrl)
  assert.equal(intake.allowNewTab, true)
  assert.equal(intake.pageUrl.includes('whole-house-read-only-preview'), false)
})

test('工作台提供开发合同入口并明确保留历史来源办理', () => {
  const source = readFileSync(new URL('../../src/meta/pages/SalesOrderPage.vue', import.meta.url), 'utf8')
  assert.match(source, />开发合同与报价<\/el-button>/)
  assert.match(source, />历史来源办理<\/el-button>/)
  assert.match(source, /salesApi\.developmentContractEntry\(\)/)
  assert.doesNotMatch(source, /sourceRecord\s*:\s*11/)
})

test('历史来源办理页也提供同源开发合同入口且不硬编码来源', () => {
  const source = readFileSync(new URL('../../src/meta/pages/WholeHouseOrderPreview.vue', import.meta.url), 'utf8')
  assert.match(source, />开发合同与报价<\/el-button>/)
  assert.match(source, /salesApi\.developmentContractEntry\(\)/)
  assert.match(source, /developmentEntry\.value\?\.target/)
  assert.match(source, /developmentEntry\.sourceRowCount/)
  assert.ok(source.indexOf('if(entryResponse.success)') < source.indexOf("if(!r.success)throw"))
  assert.doesNotMatch(source, /sourceRecord\s*:\s*11/)
})

test('开发合同子视图使用逐字对应的浏览器标题', () => {
  assert.equal(buildPageDocumentTitle('/sales/orders?mode=development-contract&sourceRecord=11'), '开发合同与报价')
  assert.equal(buildPageDocumentTitle({ path: '/sales/orders', query: { mode: 'development-contract', sourceRecord: '11' } }), '开发合同与报价')
  assert.equal(buildPageDocumentTitle('/sales/orders'), '销售订单工作台')
  const source = readFileSync(new URL('../../src/meta/pages/DevelopmentContractSamplePage.vue', import.meta.url), 'utf8')
  assert.match(source, /applyPageDocumentTitle\(route\)/)
})
