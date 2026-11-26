import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { resolveBusinessName } from '../../src/meta/governance/businessNameRegistry.js'
import {
  findPdePageDefinition,
  PDE_MAIN_FLOW,
  resolvePdeFlowAdjacency,
} from '../../src/meta/pages/pdePageDefinitions.js'
import { listPdeProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'
import { buildPageDocumentTitle } from '../../src/meta/runtime/pageTitleManager.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')

test('PDE第9节点Route与共享页面身份合同使用同一正式登记', () => {
  const router = read('src/router/index.js')
  const identity = resolveBusinessName({ route: '/pde/routings' })
  const node = listPdeProcessNodes().find(item => item.nodeCode === 'routing-management')

  assert.match(router, /path: 'pde\/routings',[\s\S]*?name: 'PdeRoutings',[\s\S]*?meta: \{ pageCode: 'pde-routings', moduleCode: 'PDE', businessObject: 'PdeRoutings', requiresServerAuthentication: true \},[\s\S]*?component: wrapPdeGovernedPage\('routings'\)/)
  assert.deepEqual({
    businessObject: identity?.businessObject,
    pageName: identity?.pageName,
    pageCode: identity?.pageCode,
    route: identity?.route,
    moduleCode: identity?.moduleCode,
    moduleDisplayName: identity?.moduleDisplayName,
  }, {
    businessObject: 'PdeRoutings',
    pageName: '工艺路线管理',
    pageCode: 'pde-routings',
    route: '/pde/routings',
    moduleCode: 'PDE',
    moduleDisplayName: 'PDE产品研发与工程管理中心',
  })
  assert.equal(buildPageDocumentTitle('/pde/routings'), '工艺路线管理')
  assert.deepEqual({
    sequence: node?.sequence,
    nodeName: node?.nodeName,
    pageCode: node?.pageCode,
    pageUrl: node?.pageUrl,
    acceptanceStatus: node?.acceptanceStatus,
  }, {
    sequence: 9,
    nodeName: '工艺路线管理',
    pageCode: 'pde-routings',
    pageUrl: '/pde/routings',
    acceptanceStatus: 'PASS',
  })
})

test('第9节点页面定义只把工艺路线管理标为当前，第10节点仅作为下一步', () => {
  const routing = findPdePageDefinition('routings')
  const routingVersion = findPdePageDefinition('routingVersions')

  assert.equal(routing.title, '工艺路线管理')
  assert.equal(routing.pageCode, 'pde-routings')
  assert.equal(routing.governance.currentFlowStep, '工艺路线管理')
  assert.equal(routing.governance.navigation.current.label, '工艺路线管理')
  assert.equal(routing.governance.navigation.next.label, '工艺路线版本管理')
  assert.notEqual(routing.governance.currentFlowStep, '工艺路线版本管理')
  assert.equal(routingVersion.governance.currentFlowStep, '工艺路线版本管理')
})

test('第8至11节点共享主流程邻接合同连续且第10节点不再跳过第9节点', () => {
  const nodes = listPdeProcessNodes()
  const nodeNames = nodes.slice(7, 11).map(item => item.nodeName)
  const expectedNames = ['BOM版本管理', '工艺路线管理', '工艺路线版本管理', '工程资料发布']
  const bomVersion = findPdePageDefinition('bomVersions')
  const routing = findPdePageDefinition('routings')
  const routingVersion = findPdePageDefinition('routingVersions')
  const engineeringDocument = findPdePageDefinition('engineeringDocuments')

  assert.deepEqual(PDE_MAIN_FLOW.slice(7, 11), expectedNames)
  assert.deepEqual(nodeNames, expectedNames)
  assert.deepEqual(resolvePdeFlowAdjacency('工艺路线版本管理'), {
    previous: '工艺路线管理',
    current: '工艺路线版本管理',
    next: '工程资料发布',
  })
  assert.equal(bomVersion.governance.navigation.next.label, '工艺路线管理')
  assert.equal(routing.governance.navigation.previous.label, 'BOM版本管理')
  assert.equal(routing.governance.navigation.next.label, '工艺路线版本管理')
  assert.equal(routingVersion.governance.navigation.previous.label, '工艺路线管理')
  assert.equal(routingVersion.governance.navigation.current.label, '工艺路线版本管理')
  assert.equal(routingVersion.governance.navigation.next.label, '工程资料发布')
  assert.notEqual(routingVersion.governance.navigation.previous.label, 'BOM版本管理')
  assert.equal(engineeringDocument.governance.navigation.previous.label, '工艺路线版本管理')
})

test('共享页面壳显示registry提供的正式模块名称且不存在本地Routing名称回退', () => {
  const shell = read('src/meta/components/PceListPageShell.vue')
  assert.match(shell, /nameConsumption\.moduleDisplayName \|\| nameConsumption\.moduleCode \|\| '未登记'/)
  assert.doesNotMatch(shell, /['"]工艺路线管理['"]/)
})
