import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workspaceRoot = path.resolve(root, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

test('Governance Files Loaded', () => {
  const files = [
    'CODEX执行命令规范.md',
    'PCE-ERP开发治理总规范.md',
    '统一列表运行层规范.md',
    '页面开发模板.md',
    '一页一验收规范.md',
    '治理符合性检查矩阵.md',
    '问题案例库.md',
  ]
  for (const file of files) {
    const source = fs.readFileSync(path.join(workspaceRoot, 'docs', 'governance', file), 'utf8')
    assert.ok(source.trim().length > 0, file)
  }
  assert.match(read('../docs/governance/统一列表运行层规范.md'), /SCM-REGRESSION-ISOLATION-001/)
})

test('Process Center Visual Contract keeps page identity readable', () => {
  const source = read('src/meta/pages/EnterpriseOSPage.vue')
  assert.match(source, /\.page-header > section\s*\{[^}]*flex:\s*0 0 auto[^}]*min-width:\s*180px/s)
  assert.match(source, /\.page-header > section h1\s*\{[^}]*white-space:\s*nowrap/s)
  assert.match(source, /\.page-header > \.page-tabs\s*\{[^}]*flex:\s*1 1 auto[^}]*min-width:\s*0/s)
})

test('SCM upstream lists remain mounted for zero records', () => {
  const inquiry = read('src/meta/pages/ScmPurchaseInquiryNodePage.vue')
  const supplier = read('src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue')
  const comparison = read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
  assert.match(inquiry, /<PceEnterpriseListTable/)
  assert.match(supplier, /<ScmSupplierQuoteEnterpriseList\s+:rows="providerFacts\.records"/)
  assert.doesNotMatch(supplier, /<ScmSupplierQuoteEnterpriseList\s+v-(?:if|else)/)
  assert.match(comparison, /<PceEnterpriseListTable\s+ref="tableRef"/)
  assert.doesNotMatch(comparison, /<PceEnterpriseListTable\s+v-(?:if|else)/)
})

test('Material price context is isolated to price approval read-only region', () => {
  const priceApproval = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const priceApprovalPage = read('src/meta/pages/ScmPage.vue')
  assert.match(priceApproval, /material-price-reference-region/)
  assert.match(priceApproval, /data-read-only="true"/)
  assert.match(priceApproval, /priceReferenceProvider/)
  assert.match(priceApprovalPage, /<ScmPriceApprovalPreparationEnterpriseList :rows="priceApprovalPreparationRows" \/>/)

  const forbiddenConsumers = [
    'src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue',
    'src/router/index.js',
    'src/meta/pages/EnterpriseOSPage.vue',
    'src/meta/pages/ScmPurchaseInquiryNodePage.vue',
    'src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue',
    'src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue',
  ]
  for (const file of forbiddenConsumers) {
    assert.doesNotMatch(read(file), /materialPriceContext|priceReferenceProvider|PriceChangeEvidence/, file)
  }
})

test('Regression recovery contains no business write path', () => {
  const changedBusinessPages = [
    'src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue',
    'src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue',
  ].map(read).join('\n')
  assert.doesNotMatch(changedBusinessPages,
    /from\s+['"][^'"]*(?:purchaseOrder|supplierRecommendation|\/finance\/|\/wms\/|\/mes\/)[^'"]*['"]/i)
  assert.doesNotMatch(changedBusinessPages, /fetch\([^)]*method\s*:\s*['"](?:POST|PUT|PATCH|DELETE)/s)
})
