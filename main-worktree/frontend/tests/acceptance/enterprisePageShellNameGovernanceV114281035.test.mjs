import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePageNameConsumption } from '../../src/meta/governance/pageNameConsumer.js'
import { validateBusinessNameRegistry } from '../../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../../src/meta/governance/businessNameCoverageScanner.js'
import { createPageShellNameSourceReport, validatePageShellNameGovernance } from '../../src/meta/governance/pageShellNameGovernance.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')

test('NAME-GOV-004 aligns process, Registry, shell, content and browser names', () => {
  const validation = validatePageShellNameGovernance()
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.pageCount, 9)
  for (const row of createPageShellNameSourceReport()) {
    assert.equal(row.nameSource, 'BusinessNameRegistry')
    assert.equal(row.processCenterName, row.registryName)
    assert.equal(row.registryName, row.shellHeaderName)
    assert.equal(row.shellHeaderName, row.contentHeaderName)
    assert.equal(row.contentHeaderName, row.browserTitle)
  }
})

test('PceListPageShell has no local or fallback business name source', () => {
  const shell = read('src/meta/components/PceListPageShell.vue')
  assert.match(shell, /data-name-source="BusinessNameRegistry"/)
  assert.match(shell, /PceBusinessNameConsumer/)
  assert.match(shell, /resolvePageNameConsumption/)
  assert.match(shell, /nameConsumption\.moduleCode/)
  assert.match(shell, /nameConsumption\.businessObject/)
  assert.match(shell, /governedPage\?\.version \|\| financePage\?\.runtimeBusinessVersion/)
  assert.doesNotMatch(shell, /fallbackTitle/)
  assert.doesNotMatch(shell, /resolvePceCanonicalName/)
  assert.doesNotMatch(shell, /governedPage\.value\?\.pageName/)
  assert.doesNotMatch(shell, /governedPage\.pageName/)
  assert.match(shell, /const pageTitle = computed\(\(\) => nameConsumption\.value\.pageTitle\)/)
})

test('router cannot inject a fallback title into the shared shell', () => {
  const router = read('src/router/index.js')
  assert.doesNotMatch(router, /fallbackTitle\s*:/)
})

test('unregistered shell identity fails visibly instead of consuming a local name', () => {
  const missing = resolvePageNameConsumption({ pageCode: 'not-registered', route: '/not-registered' })
  assert.equal(missing.result, 'FAIL')
  assert.equal(missing.nameSource, 'BusinessNameRegistry')
  assert.equal(missing.pageTitle, '页面名称未登记')
  assert.equal(missing.moduleCode, '')
  assert.equal(missing.businessObject, '')
})

test('shared shell source contains no hard-coded page name assignment', () => {
  const shellFiles = [
    'src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceDetailPageShell.vue',
    'src/meta/components/PceFormPageShell.vue',
    'src/meta/components/PceProcessPageShell.vue',
    'src/meta/components/BusinessOperationPageShell.vue',
  ]
  for (const file of shellFiles) {
    const source = read(file)
    assert.doesNotMatch(source, /(?:headerTitle|moduleTitle|displayTitle)\s*[:=]\s*['"][^'"]+['"]/, file)
    assert.doesNotMatch(source, /<h1(?:\s[^>]*)?>\s*[^<{\n][^<\n]*<\/h1>/, file)
  }
  assert.equal(validateBusinessNameRegistry().result, 'PASS')
  assert.equal(scanBusinessNameCoverage().result, 'PASS')
})
