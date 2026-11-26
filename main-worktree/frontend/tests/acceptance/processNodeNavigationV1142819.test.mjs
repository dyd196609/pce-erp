import test from 'node:test'
import assert from 'node:assert/strict'

import { listBusinessProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'
import {
  buildProcessNodeTabUrl,
  openProcessNodeInCurrentPage,
  openProcessNodeInNewTab,
} from '../../src/meta/process/processNodeNavigation.js'

test('SCM synchronized nodes expose canonical page URL and new-tab capability', () => {
  const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
  assert.equal(nodes.length, 22)
  for (const node of nodes) {
    assert.ok(node.pageCode, `${node.nodeCode} pageCode`)
    assert.ok(node.pageUrl, `${node.nodeCode} pageUrl`)
    assert.equal(node.allowNewTab, true, `${node.nodeCode} allowNewTab`)
  }
  assert.equal(nodes[0].pageUrl, '/scm/purchase-request')
  assert.equal(nodes[1].pageUrl, '/scm/purchase-approvals')
  assert.equal(nodes[2].pageUrl, '/scm/inquiry-preparations')
  assert.equal(nodes[4].pageUrl, '/scm/supplier-quotes')
  assert.equal(nodes[5].pageUrl, '/scm/quote-comparisons')
  assert.equal(nodes[6].pageUrl, '/scm/price-approval')
  assert.equal(nodes[9].pageUrl, '/scm/purchase-order')
})

test('view-page action uses the same pageUrl in the current tab', async () => {
  const pushes = []
  const node = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
    .find(item => item.nodeCode === 'supplier-reconciliation')
  const result = await openProcessNodeInCurrentPage(node, {
    async push(pageUrl) { pushes.push(pageUrl) },
  })

  assert.deepEqual(pushes, ['/scm/supplier-reconciliations'])
  assert.equal(result.opened, true)
  assert.equal(result.target, '_self')
  assert.equal(result.pageUrl, node.pageUrl)
})

test('new-tab navigation keeps the process-center location unchanged', () => {
  const opened = []
  const browserWindow = {
    location: {
      origin: 'http://localhost:5173',
      pathname: '/',
      hash: '#/process-center',
    },
    open(url, target, features) {
      opened.push({ url, target, features })
      return { closed: false }
    },
  }
  const node = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')[0]
  const originalHash = browserWindow.location.hash
  const expectedUrl = buildProcessNodeTabUrl(node, browserWindow.location)
  const result = openProcessNodeInNewTab(node, browserWindow)

  assert.equal(expectedUrl, 'http://localhost:5173/#/scm/purchase-request')
  assert.equal(result.opened, true)
  assert.equal(result.target, '_blank')
  assert.equal(result.processCenterPreserved, true)
  assert.deepEqual(opened, [{
    url: expectedUrl,
    target: '_blank',
    features: undefined,
  }])
  assert.equal(browserWindow.location.hash, originalHash)
})
