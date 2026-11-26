import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

import {
  createPceEnterpriseListContract,
  isPceLongListText,
  isPceTechnicalListField,
  summarizePceSourceRelation,
} from '../../src/meta/runtime/pceEnterpriseListContract.js'

const root = resolve(import.meta.dirname, '../../..')
const read = path => readFileSync(resolve(root, path), 'utf8')
const sha256 = path => createHash('sha256').update(readFileSync(resolve(root, path))).digest('hex').toUpperCase()

function files(path) {
  return readdirSync(path, { withFileTypes: true })
    .flatMap(entry => entry.isDirectory() ? files(join(path, entry.name)) : [join(path, entry.name)])
    .sort()
}

function treeSha256(path) {
  const hash = createHash('sha256')
  for (const file of files(resolve(root, path))) {
    hash.update(relative(root, file).replaceAll('\\', '/'))
    hash.update('\0')
    hash.update(readFileSync(file))
    hash.update('\0')
  }
  return hash.digest('hex').toUpperCase()
}

test('governance files and list display rules are loaded in existing specifications', () => {
  const paths = [
    'docs/governance/01-开发治理总纲/PCE-ERP开发治理总纲.md',
    'docs/governance/02-架构与运行边界/PCE-ERP架构与运行边界规范.md',
    'docs/governance/03-业务流程运行治理/PCE-ERP业务流程运行治理规范.md',
    'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
    'docs/governance/05-自动验收治理/PCE-ERP自动验收与证据治理规范.md',
  ]
  paths.forEach(path => assert.ok(read(path).trim(), path))
  const governance = paths.map(read).join('\n')
  for (const code of ['PAGE-RUNTIME-FREEZE-001', 'DATA-IDENTITY-001',
    'DATA-EXTRACT-001', 'ARRAY-COMPLETENESS-001', 'LIST-DISPLAY-001',
    'TECH-FIELD-SEPARATION-001', 'TABLE-ROW-HEIGHT-001']) {
    assert.ok(governance.includes(code), code)
  }
  assert.ok(governance.includes('PCE_LIST_DISPLAY_GOVERNANCE_READY'))
})

test('pre-scan enumerates public contracts and affected pages', () => {
  const scan = JSON.parse(read('pce_list_display_governance_scan_v1142842722.json'))
  assert.equal(scan.version, 'V1.14.2.8.4.27.2.2')
  assert.equal(scan.findingsBeforeImplementation.length, 3)
  assert.ok(scan.publicComponents.length >= 4)
  assert.ok(scan.affectedPagesList.length >= 20)
  assert.equal(scan.compatibility.businessActionsChanged, false)
  assert.equal(scan.compatibility.detailsKeepFullSourceEvidence, true)
})

test('enterprise list runtime freezes summary, technical-field and row-height contracts', () => {
  const contract = createPceEnterpriseListContract({
    pageCode: 'acceptance-list', pageType: 'list', title: '验收列表', moduleCode: 'PCE',
  })
  assert.equal(contract.display.businessSummaryOnly, true)
  assert.equal(contract.display.technicalFieldsHidden, true)
  assert.equal(contract.display.rowDensity, 'compact')
  assert.equal(contract.display.longTextMode, 'ellipsis-tooltip-detail')
  assert.equal(contract.display.diagnosticDefaultCollapsed, true)
  for (const field of ['objectId', 'sourceRelations', 'gateId', 'apiUrl',
    'runtimeDiagnostics', 'json', 'statusCode']) assert.equal(isPceTechnicalListField(field), true)
  assert.equal(isPceTechnicalListField('purchaseOrderNo'), false)
  assert.equal(summarizePceSourceRelation('GATE-LONG-ID'), '已关联Gate')
  assert.equal(summarizePceSourceRelation('GATE-LONG-ID', 6), '来源数量：6')
  assert.equal(isPceLongListText('01234567890123456789'), true)
})

test('shared table defaults compact, truncates long text and protects editable consumers', () => {
  const table = read('frontend/src/meta/components/PceEnterpriseListTable.vue')
  for (const term of ['data-pce-list-display-rule="LIST-DISPLAY-001"',
    'data-pce-technical-field-separation="TECH-FIELD-SEPARATION-001"',
    'data-pce-long-text-mode="ellipsis-tooltip-detail"', "default: 'compact'",
    'text-overflow: ellipsis', 'white-space: nowrap', 'fixed="right"']) {
    assert.ok(table.includes(term), term)
  }
  const createPage = read('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
  assert.equal((createPage.match(/row-density="comfortable"/g) || []).length, 2)
})

test('purchase order list shows governed business summary while detail keeps full sources', () => {
  const page = read('frontend/src/meta/pages/ScmPage.vue')
  const orderBlock = page.slice(page.indexOf('order: {'), page.indexOf('headerFields:', page.indexOf('order: {')))
  for (const field of ["{ key: 'poNo'", "{ key: 'supplierId'", "{ key: 'status'",
    "{ key: 'totalQuantity'", "{ key: 'totalAmount'", "{ key: 'earliestArrivalDate'",
    "{ key: 'sourceGateId'"]) assert.ok(orderBlock.includes(field), field)
  for (const field of ["{ key: 'rootRequestNo'", "{ key: 'requestDepartment'",
    "{ key: 'demandDepartment'", "{ key: 'classification'"]) assert.equal(orderBlock.includes(field), false, field)
  assert.ok(page.includes('purchaseOrderSourceSummary(row)'))
  assert.ok(page.includes('完整来源关系请进入采购订单详情查看'))
  assert.ok(page.includes('pce-compact-business-table'))
  assert.ok(page.includes("const LIST_DISPLAY_STATE_PREFIX = 'pce-list-display-state:'"))
  assert.ok(page.includes('restoreListDisplayState(route.path)'))
  assert.ok(page.includes('sessionStorage?.setItem'))

  const detailBlock = page.slice(page.indexOf('headerFields:', page.indexOf('order: {')),
    page.indexOf('detailColumns:', page.indexOf('order: {')))
  for (const field of ['sourceGateId', 'sourceRecommendationId', 'sourceInquiryId',
    'sourcePriceApprovalId']) assert.ok(detailBlock.includes(field), field)
  const panel = read('frontend/src/meta/components/ScmPurchaseOrderLifecyclePanelV114284272.vue')
  assert.ok(panel.includes('sourcePurchaseRequestIds'))
  assert.ok(panel.includes('来源追踪'))
})

test('server facts remain loaded but are collapsed behind explicit diagnostic disclosure', () => {
  for (const path of [
    'frontend/src/meta/components/ScmStandardPageContext.vue',
    'frontend/src/meta/components/PceStrictServerFactsPanel.vue',
  ]) {
    const source = read(path)
    assert.ok(source.includes('服务端持久事实'), path)
    assert.ok(source.includes('查看诊断信息'), path)
    assert.ok(source.includes('v-show="diagnosticExpanded"'), path)
    assert.ok(source.includes('const diagnosticExpanded = ref(false)'), path)
    assert.ok(source.includes('data-diagnostic-visibility="authorized-disclosure"'), path)
  }
})

test('forbidden Provider, Action, Store, domain and database assets remain frozen', () => {
  const scan = JSON.parse(read('pce_list_display_governance_scan_v1142842722.json'))
  assert.equal(treeSha256('frontend/src/meta/providers'), scan.frozenBaseline.providersTreeSha256)
  assert.equal(treeSha256('frontend/src/meta/actions'), scan.frozenBaseline.actionsTreeSha256)
  assert.equal(treeSha256('frontend/src/meta/domain'), scan.frozenBaseline.domainTreeSha256)
  assert.equal(sha256('frontend/src/meta/scm/scmStore.js'), scan.frozenBaseline.scmStoreSha256)
  assert.equal(sha256('backend/db.sqlite3'), scan.frozenBaseline.databaseSha256)
  assert.equal(scan.businessWriteCount, 0)
})
