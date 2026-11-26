import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { validateBusinessNameSingleSourceGovernance } from '../../src/meta/governance/businessNameSingleSourceGovernance.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')

test('NAME-GOV-001 through NAME-GOV-006 form one runtime name chain', () => {
  const validation = validateBusinessNameSingleSourceGovernance()
  assert.equal(validation.result, 'PASS')
  assert.equal(validation.shell.pageCount, 9)
  assert.equal(validation.runtimeSourcesAligned, true)
  assert.equal(validation.runtimeNamesAligned, true)
})

test('NAME-GOV-005 removes Router business titles and Router title consumers', () => {
  const router = readFrontend('src/router/index.js')
  const cockpit = readFrontend('src/meta/shell/ProfitCockpit.vue')
  assert.doesNotMatch(router, /meta\s*:\s*\{[^}]*\btitle\s*:/s)
  assert.doesNotMatch(router, /route\.meta\??\.title/)
  assert.doesNotMatch(cockpit, /route\.meta\??\.title/)
  assert.match(cockpit, /resolvePageNameConsumption\(\{ route: route\.path \}\)/)
})

test('NAME-GOV-006 removes identity fallbacks from title manager and WMS content header', () => {
  const manager = readFrontend('src/meta/runtime/pageTitleManager.js')
  const wms = readFrontend('src/meta/pages/WmsPage.vue')
  const modules = readFrontend('src/meta/runtime/pceBusinessModuleRegistry.js')
  assert.match(manager, /resolveBusinessName\(\{ route: path \}\)/)
  assert.doesNotMatch(manager, /resolvePceCanonicalNameByRoute|findBusinessProcessStepByRoutePath|routeTitleMap/)
  assert.doesNotMatch(wms, /resolvePceCanonicalNameByRoute|currentList\.value\?\.title/)
  const inventoryDefinition = modules.match(/moduleId:\s*'inventory-balances'[\s\S]*?route:\s*'\/wms\/inventory-balances'/)?.[0] || ''
  assert.ok(inventoryDefinition)
  assert.doesNotMatch(inventoryDefinition, /canonicalName\s*:/)
})

test('CASE-WMS-001 and PROCESS-009 have closure evidence', () => {
  const cases = readWorkspace('docs/governance/问题案例库.md')
  const acceptance = readWorkspace('docs/acceptance/PAGE-BUSINESS-NAME-SINGLE-SOURCE-V114281036.md')
  assert.match(cases, /CASE-WMS-001/)
  assert.match(cases, /V1\.14\.2\.8\.18\.10\.3\.6/)
  assert.match(cases, /NAME-GOV-005/)
  assert.match(acceptance, /PROCESS-009/)
  assert.match(acceptance, /BusinessNameRegistry/)
  assert.match(acceptance, /PASS/)
})
