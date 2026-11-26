import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { listPdeProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const router = read('src/router/index.js')
const page = read('src/meta/pages/PdeOrderEngineeringCalculationPage.vue')

test('PDE工程核算正式节点保持共享流程入口、正式路由与当前页面组件闭包', () => {
  const node = listPdeProcessNodes().find(item => item.nodeCode === 'engineering-material-calculation')
  assert.deepEqual({
    moduleCode: node?.moduleCode,
    nodeName: node?.nodeName,
    pageCode: node?.pageCode,
    pageUrl: node?.pageUrl,
    pageStatus: node?.pageStatus,
    acceptanceStatus: node?.acceptanceStatus,
  }, {
    moduleCode: 'PDE',
    nodeName: '工程核算 / 物料核算',
    pageCode: 'pde-order-engineering-calculation',
    pageUrl: '/pde/engineering-calculations',
    pageStatus: 'active',
    acceptanceStatus: 'PASS',
  })
  assert.match(router, /path: 'pde\/engineering-calculations',[\s\S]*name: 'PdeOrderEngineeringCalculation',[\s\S]*component: wrapPdeOrderEngineeringCalculationPage\(\)/)
  assert.match(router, /defineAsyncComponent\(\(\) => import\('@\/meta\/pages\/PdeOrderEngineeringCalculationPage\.vue'\)\)/)
})

test('无显式订单上下文时不自动选择数据库订单或历史验证订单', () => {
  assert.match(page, /route\.query\.sourceRecord/)
  assert.match(page, /route\.query\.order/)
  assert.match(page, /route\.query\.orderNo/)
  assert.match(page, /requestedFormalOrder/)
  assert.match(page, /selection\.salesOrderItemId = null/)
  assert.match(page, /请选择订单或工程来源/)
  assert.doesNotMatch(page, /stableDesignContext/)
  assert.doesNotMatch(page, /SO202609180003/)
})
