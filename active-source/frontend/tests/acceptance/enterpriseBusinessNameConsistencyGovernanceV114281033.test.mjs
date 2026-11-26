import test from 'node:test'
import assert from 'node:assert/strict'
import {
  listBusinessNames,
  resolveBusinessName,
  validateBusinessNameRegistry,
} from '../../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../../src/meta/governance/businessNameCoverageScanner.js'
import { listBusinessProcesses } from '../../src/meta/process/businessProcessRegistry.js'
import { listPceBusinessModules } from '../../src/meta/runtime/pceBusinessModuleRegistry.js'
import { buildPageDocumentTitle } from '../../src/meta/runtime/pageTitleManager.js'

test('BusinessNameRegistry provides every governed name field from one canonical record', () => {
  const validation = validateBusinessNameRegistry()
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.recordCount, 84)
  for (const record of listBusinessNames()) {
    assert.ok(record.businessObject)
    assert.ok(record.nodeCode)
    assert.equal(record.processName, record.displayName)
    assert.equal(record.pageName, record.displayName)
    assert.equal(record.pageTitle, record.displayName)
    assert.equal(record.browserTitle, record.displayName)
  }
})

test('NAME-GOV-002 covers all discovered ERP business pages', () => {
  const scan = scanBusinessNameCoverage()
  assert.equal(scan.result, 'PASS')
  assert.equal(scan.registeredPageCount, 84)
  assert.equal(scan.discoveredPageCount, 84)
  assert.equal(scan.sourceRecordCount, 127)
  assert.deepEqual(scan.failures, [])
  assert.deepEqual(scan.modules.map(item => item.moduleCode), ['SCM','WMS','QMS','FIN','CRM','PDE','MES'])
})

test('process and page registries project names from BusinessNameRegistry', () => {
  const processes = listBusinessProcesses()
  const processPages = processes.flatMap(process => process.nodes || []).filter(node => node.pageUrl)
  for (const node of processPages) {
    const governed = resolveBusinessName({ route: node.pageUrl })
    assert.ok(governed, `missing process route ${node.pageUrl}`)
    assert.equal(node.nodeName, governed.processName)
    assert.equal(node.nameSource, 'BusinessNameRegistry')
  }
  for (const page of listPceBusinessModules()) {
    const governed = resolveBusinessName({ route: page.route })
    assert.ok(governed, `missing page route ${page.route}`)
    assert.equal(page.canonicalName, governed.pageName)
    assert.equal(page.nameSource, 'BusinessNameRegistry')
  }
})

test('browser titles including dynamic page-family routes come from the registry', () => {
  assert.equal(buildPageDocumentTitle('/scm/purchase-inquiry'), '采购询价')
  assert.equal(buildPageDocumentTitle('/scm/purchase-inquiry/edit/PI-001'), '编辑询价')
  assert.equal(buildPageDocumentTitle('/wms/inventory-balances'), '入库')
  assert.equal(buildPageDocumentTitle('/qms/incoming-inspections'), '来料检验')
  assert.equal(buildPageDocumentTitle('/finance/payable-prepares'), '采购应付预备')
  assert.equal(buildPageDocumentTitle('/pde/manufacturing-outputs'), '制造输出确认')
})
