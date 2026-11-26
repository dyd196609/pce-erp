import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { resolveBusinessName } from '../../src/meta/governance/businessNameRegistry.js'
import { listPdeProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'
import { findPdePageDefinition, PDE_MAIN_FLOW } from '../../src/meta/pages/pdePageDefinitions.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')

test('customer demand and PDE preparation consume the unified 16-node flow and canonical names', () => {
  const nodes = listPdeProcessNodes()
  const requirements = findPdePageDefinition('requirements')
  const readiness = findPdePageDefinition('engineeringReadiness')

  assert.equal(nodes.length, 16)
  assert.deepEqual(nodes.slice(0, 3).map(row => row.nodeName), [
    '客户订单需求', 'PDE工程准备', '生产可行性评审',
  ])
  assert.equal(PDE_MAIN_FLOW.length, 16)
  assert.equal(requirements.title, '客户订单需求')
  assert.equal(requirements.governance.navigation.next.label, 'PDE工程准备')
  assert.equal(readiness.title, 'PDE工程准备')
  assert.equal(readiness.governance.navigation.previous.label, '客户订单需求')
  assert.equal(readiness.governance.navigation.next.label, '生产可行性评审')
  assert.equal(resolveBusinessName({ route: '/pde/product-requirements' }).pageTitle, '客户订单需求')
  assert.equal(resolveBusinessName({ route: '/pde/engineering-readiness' }).pageTitle, 'PDE工程准备')
})

test('three pages require tab authentication and retain a safe login return path', () => {
  const router = read('src/router/index.js')
  const login = read('src/views/Login.vue')
  for (const pathValue of ['sales/orders', 'pde/product-requirements', 'pde/engineering-readiness']) {
    const start = router.indexOf(`path: '${pathValue}'`)
    assert.notEqual(start, -1, pathValue)
    assert.match(router.slice(start, start + 500), /requiresServerAuthentication:\s*true/, pathValue)
  }
  assert.match(login, /requested\.startsWith\('\/'\) && !requested\.startsWith\('\/\/'\)/)
  assert.match(login, /登录成功后将返回/)
  assert.doesNotMatch(login, /localStorage\.setItem\(['"]token/)
})

test('PDE list page separates loading, auth failure, permission failure, read failure and valid empty', () => {
  const page = read('src/meta/pages/PdeFoundationPage.vue')
  assert.match(page, /readPceFactLoadEnvelope/)
  assert.match(page, /factLoadStatus/)
  assert.match(page, /httpStatus\) === 401/)
  assert.match(page, /httpStatus\) === 403/)
  assert.match(page, /httpStatus\) >= 500/)
  assert.match(page, /httpStatus\) === 0/)
  assert.match(page, /factsAvailable/)
  assert.match(page, /当前结果数量未取得/)
  assert.match(page, /let refreshSequence = 0/)
  assert.match(page, /current !== refreshSequence/)
  assert.match(page, /pce:authentication-changed/)
})

test('sales and PDE lists render each exact server business status label', () => {
  const salesPage = read('src/meta/pages/SalesOrderPage.vue')
  const pdePage = read('src/meta/pages/PdeFoundationPage.vue')

  assert.match(salesPage, /:status-label="row\.statusLabel"/)
  assert.match(salesPage, /:status-code="row\.status"/)
  assert.doesNotMatch(salesPage, /<PceBusinessStatus\s+:label=/)
  assert.match(pdePage, /:status-label="row\[column\[0\]\]"/)
  assert.doesNotMatch(pdePage, /:status-label="row\.statusLabel"/)
})
