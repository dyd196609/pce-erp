import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildFormalPurchaseOrderV114284271 } from
  '../../src/meta/actions/scm/createPurchaseOrderActionV114284271.js'
import { assertCanonicalPurchaseOrderNumberV11428427212,
  createCanonicalPurchaseOrderNumberV11428427212 } from
  '../../src/meta/runtime/purchaseOrderNumberRuntimeV11428427212.js'
import { buildPurchaseOrderImportWorkbookV11428427212 } from
  '../../src/meta/runtime/purchaseOrderImportTemplateRuntimeV11428427212.js'
import { PURCHASE_ORDER_HEADER_IMPORT_SCHEMA_FIELDS,
  PURCHASE_ORDER_ITEM_IMPORT_SCHEMA_FIELDS } from
  '../../src/meta/schema/purchase/purchaseOrder.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path)))
  .digest('hex').toUpperCase()

test('governance files and active replacements are loaded before implementation', () => {
  const files = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/archive/legacy-specs/PCE-ERP开发治理总规范.md',
    'docs/governance/页面真实运行验收规范.md',
    'docs/governance/页面需求执行闭环规范.md',
    'docs/governance/Codex执行证据规范.md',
    'docs/governance/archive/legacy-specs/页面开发模板.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/采购订单导入模板规范.md',
  ]
  const governance = files.map(read).join('\n')
  for (const rule of ['GOV-001', 'PAGE-RUNTIME-001', 'BROWSER-ACTION-001',
    'CODEX-EVIDENCE-001', 'PURCHASE-ORDER-IMPORT-TEMPLATE-002']) {
    assert.ok(governance.includes(rule), rule)
  }
})

test('purchase order list refresh binds click, provider reload, DOM rerender and feedback', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const shell = read('frontend/src/meta/components/PceListPageShell.vue')
  const provider = read('frontend/src/meta/providers/purchaseOrderListDataProviderV1142842729.js')
  assert.match(shell, /data-acceptance-id="page-refresh-button"/)
  assert.match(shell, /@click="refreshCurrentPage"/)
  assert.match(shell, /刷新中\.\.\./)
  assert.match(shell, /刷新成功/)
  assert.match(page, /loadFacts:\s*readPurchaseOrderListFactSnapshotV1142842729/)
  assert.match(page, /loadPurchaseOrderRuntimeCollection/)
  assert.match(provider, /const snapshot = getScmState\(\)/)
  assert.match(page, /scmState\.value = result\.snapshot/)
  assert.match(page, /purchaseOrderListRenderVersion\.value \+= 1/)
  assert.match(page, /await nextTick\(\)/)
  assert.match(page, /最近刷新时间：\$\{purchaseOrderListLastRefreshTime\.value\}/)
  assert.doesNotMatch(page, /window\.location\.reload\(|router\.go\(0\)/)
})

test('formal PurchaseOrder number is dedicated and does not concatenate source identities', () => {
  const first = createCanonicalPurchaseOrderNumberV11428427212({
    issuedAt: '2026-08-10T12:34:56.789Z', sequence: 1,
  })
  const second = createCanonicalPurchaseOrderNumberV11428427212({
    issuedAt: '2026-08-10T12:34:56.789Z', sequence: 2,
  })
  assert.match(first.poNo, /^PO\d{20}$/)
  assert.notEqual(first.poNo, second.poNo)
  const packageResult = buildFormalPurchaseOrderV114284271({
    gate: { gateId: 'POG-SRDB-PAP-PI-001', purchaseRequestId: 'PR-001' },
    supplierPurchaseDraft: { supplierId: 'SUP-001', supplierName: '供应商一' },
    now: '2026-08-10T12:34:56.789Z', sequence: 3,
  })
  assert.equal(packageResult.purchaseOrder.purchaseOrderNo, 'PO20260810123456789003')
  assert.equal(packageResult.purchaseOrder.poNo, packageResult.purchaseOrder.purchaseOrderNo)
  assert.equal(packageResult.purchaseOrder.poNo.includes('SRDB'), false)
  assert.equal(packageResult.purchaseOrder.poNo.includes('SUP'), false)
  assert.equal(assertCanonicalPurchaseOrderNumberV11428427212(
    packageResult.purchaseOrder).valid, true)
})

test('purchase order list displays PurchaseOrder canonical number field', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const store = read('frontend/src/meta/scm/scmStore.js')
  assert.match(page, /key === 'objectNo'\) return getPurchaseOrderNumber\(row\)/)
  assert.match(store, /purchaseOrderNo:\s*canonicalObjectNo/)
  assert.match(store, /poNo:\s*canonicalObjectNo/)
})

test('XLSX template has related Header and Detail sheets from governed Contract', () => {
  const workbook = buildPurchaseOrderImportWorkbookV11428427212()
  assert.equal(workbook.fileName, '采购订单导入模板.xlsx')
  assert.deepEqual(workbook.sheetNames, ['采购订单基本信息', '采购订单物料明细'])
  assert.equal(workbook.bytes[0], 0x50)
  assert.equal(workbook.bytes[1], 0x4b)
  assert.equal(workbook.businessWriteCount, 0)
  assert.deepEqual(workbook.definition.schemaSource, {
    basic: 'PurchaseOrder Schema', item: 'PurchaseOrderItem Schema',
  })
  const basic = workbook.entries.find(entry => entry.name.endsWith('sheet1.xml')).content
  const items = workbook.entries.find(entry => entry.name.endsWith('sheet2.xml')).content
  assert.equal(workbook.entries.some(entry => entry.name.endsWith('sheet3.xml')), false)
  for (const field of PURCHASE_ORDER_HEADER_IMPORT_SCHEMA_FIELDS) {
    assert.ok(basic.includes(field.label), `基本信息:${field.label}`)
  }
  for (const field of PURCHASE_ORDER_ITEM_IMPORT_SCHEMA_FIELDS) {
    assert.ok(items.includes(field.label), `物料明细:${field.label}`)
  }
  assert.ok(basic.includes('采购订单编号'))
  assert.ok(items.includes('采购订单编号'))
  for (const systemLabel of ['状态', '创建时间']) {
    assert.equal(basic.includes(systemLabel), false, systemLabel)
    assert.equal(items.includes(systemLabel), false, systemLabel)
  }
})

test('Gate, lifecycle and database frozen assets remain unchanged', () => {
  const frozen = JSON.parse(read('purchase_order_true_runtime_scan_v11428427210.json'))
    .frozenAssetBaseline
  const paths = {
    purchaseOrderGateSha256: 'frontend/src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js',
    lifecycleStateMachineSha256: 'frontend/src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRuntimeV114284272.js',
    databaseSha256: 'backend/db.sqlite3',
  }
  Object.entries(paths).forEach(([key, path]) => assert.equal(sha256(path), frozen[key], path))
})
