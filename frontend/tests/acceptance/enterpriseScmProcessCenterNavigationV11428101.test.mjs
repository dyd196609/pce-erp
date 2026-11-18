import test from 'node:test'
import assert from 'node:assert/strict'

import { listBusinessProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'
import { listScmProcessFlowPages, resolveScmProcessNavigation } from '../../src/meta/process/scmProcessNavigationContract.js'
import { SCM_PURCHASE_PRIMARY_NODE_CODES, listScmPurchaseProcessCenterNodes,
  validateScmPurchaseProcessCenterRegistry } from '../../src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js'
import { openProcessNodeInCurrentPage, openProcessNodeInNewTab } from '../../src/meta/process/processNodeNavigation.js'

const primaryNames = ['采购申请', '采购审批', '询价准备', '采购询价', '供应商报价', '报价比较',
  '采购核价', '供应商推荐', '采购订单准入', '采购订单', '收货', '来料检验']

test('SCM采购主路径节点顺序完整且结算后续节点保持', () => {
  const validation = validateScmPurchaseProcessCenterRegistry()
  const registered = listScmPurchaseProcessCenterNodes()
  const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.primaryNodeCount, 12)
  assert.equal(registered.length, 22)
  assert.deepEqual(processNodes.slice(0, 12).map(item => item.nodeCode), [...SCM_PURCHASE_PRIMARY_NODE_CODES])
  assert.deepEqual(processNodes.slice(0, 12).map(item => item.nodeName), primaryNames)
  assert.deepEqual(processNodes.map(item => item.nodeCode), registered.map(item => item.nodeCode))
  assert.equal(processNodes.at(-1).nodeCode, 'buyer-performance')
})

test('每个流程节点拥有身份、前后关系、页面和验收档案', () => {
  const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
  nodes.forEach((node, index) => {
    assert.ok(node.nodeCode)
    assert.ok(node.nodeName)
    assert.equal(node.previousNode, index ? nodes[index - 1].nodeCode : null)
    assert.equal(node.nextNode, index < nodes.length - 1 ? nodes[index + 1].nodeCode : null)
    assert.equal(node.pageRoute, node.pageUrl)
    assert.ok(node.pageRoute)
    assert.ok(node.acceptanceProfile)
    assert.equal(node.allowNewTab, true)
    assert.ok(node.statusDescription)
  })
})

test('供应商报价、报价比较和供应商推荐节点登记正确', () => {
  const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
  const expected = {
    'supplier-quote': ['SCM_SUPPLIER_QUOTE', '/scm/supplier-quotes', 'supplierQuoteAcceptanceProfileV114289'],
    'quote-comparison': ['SCM_QUOTE_COMPARISON', '/scm/quote-comparisons', 'quoteComparisonAcceptanceProfileV1142810'],
    'supplier-recommendation': ['SCM_SUPPLIER_RECOMMENDATION_DECISION', '/scm/supplier-recommendations', 'PAGE-SUPPLIER-RECOMMENDATION'],
  }
  for (const [code, [runtimeNodeCode, route, profile]] of Object.entries(expected)) {
    const node = nodes.find(item => item.nodeCode === code)
    assert.equal(node.runtimeNodeCode, runtimeNodeCode)
    assert.equal(node.pageRoute, route)
    assert.equal(node.acceptanceProfile, profile)
  }
})

test('流程导航、当前页查看和新标签使用同一页面映射', async () => {
  const flow = listScmProcessFlowPages()
  assert.equal(flow.length, 22)
  for (const node of flow) {
    const navigation = resolveScmProcessNavigation(node.nodeCode)
    assert.equal(navigation.pageUrl, node.pageUrl)
  }
  const quoteComparison = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
    .find(item => item.nodeCode === 'quote-comparison')
  const pushes = []
  const current = await openProcessNodeInCurrentPage(quoteComparison, { async push(route) { pushes.push(route) } })
  assert.deepEqual(pushes, ['/scm/quote-comparisons'])
  assert.equal(current.opened, true)
  const opened = []
  const result = openProcessNodeInNewTab(quoteComparison, {
    location: { origin: 'http://localhost:5173', pathname: '/', hash: '#/process-center' },
    open(url, target) { opened.push({ url, target }); return {} },
  })
  assert.equal(result.opened, true)
  assert.deepEqual(opened, [{ url: 'http://localhost:5173/#/scm/quote-comparisons', target: '_blank' }])
})
