import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listPceBusinessModules } from '../../src/meta/runtime/pceBusinessModuleRegistry.js'
import { listBusinessProcesses } from '../../src/meta/process/businessProcessRegistry.js'
import { validateBusinessNameRegistry } from '../../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../../src/meta/governance/businessNameCoverageScanner.js'
import { applyConsumedBrowserTitle, resolvePageNameConsumption } from '../../src/meta/governance/pageNameConsumer.js'
import { createPageNameConsumerReport, validatePageNameConsumptionGovernance } from '../../src/meta/governance/pageNameConsumptionGovernance.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const registeredComponents = [...new Set(listPceBusinessModules().map(page => page.pageComponent).filter(Boolean))]

test('NAME-GOV-003 aligns Registry, Header, Browser Title and internal title', () => {
  const validation = validatePageNameConsumptionGovernance()
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.pageCount, 9)
  for (const row of createPageNameConsumerReport()) {
    assert.equal(row.nameSource, 'BusinessNameRegistry')
    assert.equal(row.registryName, row.headerName)
    assert.equal(row.headerName, row.browserTitle)
    assert.equal(row.browserTitle, row.internalTitle)
  }
})

test('PCE Enterprise Page V2 consumes Registry names and exact browserTitle', () => {
  const shell = read('src/meta/components/PceListPageShell.vue')
  assert.match(shell, /PceBusinessNameConsumer/)
  assert.match(shell, /resolvePageNameConsumption/)
  assert.match(shell, /applyConsumedBrowserTitle/)
  assert.doesNotMatch(shell, /pageName\}\s*\|\s*PCE-ERP/)
  const consumption = resolvePageNameConsumption('/wms/inventory-balances')
  const fakeDocument = { title: '' }
  assert.equal(applyConsumedBrowserTitle(consumption, fakeDocument), `未登录｜${consumption.browserTitle}`)
  assert.equal(fakeDocument.title, `未登录｜${consumption.browserTitle}`)
})

test('registered business page components contain no hard-coded page H1 or internal subject title', () => {
  assert.equal(registeredComponents.length, 45)
  for (const componentFile of registeredComponents) {
    const source = read(componentFile)
    assert.doesNotMatch(source, /<h1(?:\s[^>]*)?>\s*[^<{\n][^<\n]*<\/h1>/, componentFile)
    assert.doesNotMatch(source, /data-acceptance-id=["']page-internal-subject-title["'][^>]*>\s*[^<{\n][^<\n]*/, componentFile)
  }
})

test('page sources cannot assign document.title outside the governed title consumer', () => {
  const sourceRoot = path.join(frontendRoot, 'src')
  const pending = [sourceRoot]
  const violations = []
  while (pending.length) {
    const current = pending.pop()
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const target = path.join(current, entry.name)
      if (entry.isDirectory()) pending.push(target)
      else if (/\.(vue|js|ts)$/.test(entry.name) && /document\.title\s*=/.test(fs.readFileSync(target, 'utf8'))) violations.push(path.relative(frontendRoot, target))
    }
  }
  assert.deepEqual(violations, [])
})

test('sampled page components explicitly consume the unified source', () => {
  for (const row of createPageNameConsumerReport()) {
    const source = read(row.componentFile)
    assert.match(source, /(resolvePageNameConsumption|resolveBusinessName|PceBusinessNameConsumer)/, row.componentFile)
  }
  const processNodes = listBusinessProcesses().flatMap(process => process.nodes || [])
  for (const row of createPageNameConsumerReport()) {
    const node = processNodes.find(item => item.pageUrl === row.route)
    if (node) assert.equal(node.nodeName, row.registryName)
  }
  assert.equal(validateBusinessNameRegistry().result, 'PASS')
  assert.equal(scanBusinessNameCoverage().result, 'PASS')
})
