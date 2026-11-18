import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'

import { listBusinessProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'
import { resolveScmPageIdentity } from '../../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { listScmNodePageMappingsV11428103,
  validateScmNodePageGovernanceV11428103 } from '../../src/meta/process/scmNodePageGovernanceV11428103.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readPage = name => fs.readFileSync(path.join(frontendRoot, 'src/meta/pages', name), 'utf8')

test('NODE-PAGE-001 与 PROCESS-011 映射完整且唯一', () => {
  const result = validateScmNodePageGovernanceV11428103()
  const mappings = listScmNodePageMappingsV11428103()
  assert.equal(result.result, 'PASS')
  assert.equal(result.nodePage001, true)
  assert.equal(result.process011, true)
  assert.equal(new Set(mappings.map(item => item.pageContract.pageCode)).size, mappings.length)
  assert.equal(new Set(mappings.map(item => item.pageContract.route)).size, mappings.length)
})

test('Page Contract 与 Page Identity 完全一致', () => {
  for (const mapping of listScmNodePageMappingsV11428103()) {
    const identity = resolveScmPageIdentity(mapping.pageContract.route)
    assert.ok(identity, mapping.nodeCode)
    for (const field of ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject']) {
      assert.equal(identity[field], mapping.pageContract[field], `${mapping.nodeCode}:${field}`)
    }
  }
})

test('流程中心九个采购节点使用唯一页面映射', () => {
  const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT').slice(0, 9)
  const mappings = listScmNodePageMappingsV11428103()
  assert.equal(processNodes.length, mappings.length)
  processNodes.forEach((node, index) => {
    assert.equal(node.nodeCode, mappings[index].nodeCode)
    assert.equal(node.pageCode, mappings[index].pageContract.pageCode)
    assert.equal(node.pageRoute, mappings[index].pageContract.route)
  })
})

test('四个页面拥有独立身份、职责区域且询价页不再承载其他节点', () => {
  const pages = {
    'ScmInquiryPreparationPage.vue': ['data-page-code="inquiry-preparation"', 'START_PURCHASE_INQUIRY', 'preparation-detail'],
    'ScmPurchaseInquiryNodePage.vue': ['data-page-code="purchase-inquiry"', 'material-supplier-decision', '准备供应商报价'],
    'ScmSupplierRecommendationPage.vue': ['data-page-code="supplier-recommendation"', 'comparison-evidence', '推荐理由'],
    'ScmPurchaseOrderGatePage.vue': ['data-page-code="purchase-order-gate"', 'gate-checks', '准入检查'],
  }
  for (const [name, expected] of Object.entries(pages)) {
    const source = readPage(name)
    expected.forEach(value => assert.ok(source.includes(value), `${name}:${value}`))
  }
  const inquiry = readPage('ScmPurchaseInquiryNodePage.vue')
  for (const forbidden of ['supplier-recommendation-runtime', 'purchase-order-gate-runtime',
    'pending-inquiry-preparations', 'supplierRecommendationRuntime', 'purchaseOrderCreationGateRuntime']) {
    assert.equal(inquiry.includes(forbidden), false, forbidden)
  }
  assert.equal(readPage('ScmSupplierRecommendationPage.vue').includes('createPurchaseOrder'), false)
})

test('四份 PROCESS-009 页面验收记录存在', () => {
  for (const name of ['PAGE-INQUIRY-PREPARATION.md', 'PAGE-PURCHASE-INQUIRY.md',
    'PAGE-SUPPLIER-RECOMMENDATION.md', 'PAGE-PURCHASE-ORDER-GATE.md']) {
    const source = fs.readFileSync(path.join(workspaceRoot, 'docs/acceptance', name), 'utf8')
    assert.ok(source.includes('人工验收结果：PASS'), name)
  }
})
