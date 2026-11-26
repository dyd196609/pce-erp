import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import {
  foundationCanonicalModules,
  foundationCanonicalRouteDefinitions,
  getFoundationCanonicalModule,
  resolveFoundationPageState,
} from '../src/meta/master-data/foundationEntryUnificationRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')
const sha = relative => createHash('sha256').update(readFileSync(path.join(root, relative))).digest('hex')
const routerSource = read('src/router/index.js')
const navigationSource = read('src/meta/master-data/foundationNavigationRegistry.js')
const componentSource = read('src/meta/components/ProductionFoundationMaintenance.vue')
const portalSource = read('src/meta/pages/EnterpriseFoundationUnifiedPage.vue')

const unique = (rows, key) => new Set(rows.map(item => item[key])).size === rows.length
for (const key of ['moduleId', 'entityKey', 'navigationKey', 'pageKey', 'routeName', 'routePath']) {
  assert(unique(foundationCanonicalModules, key), `canonical ${key} must be unique`)
}

const required = ['product-category', 'product-definition', 'bom', 'routing', 'routing-version', 'routing-step', 'operation', 'work-center', 'capacity', 'customer', 'supplier', 'material', 'uom']
for (const moduleId of required) assert(getFoundationCanonicalModule(moduleId), `missing canonical module ${moduleId}`)

assert(routerSource.includes('...foundationCanonicalRouteDefinitions.map'), 'router must generate foundation routes from canonical registry')
assert(routerSource.includes('resolveFoundationPageState(to)'), 'router runtime identity guard missing')
assert(navigationSource.includes('getFoundationCanonicalModuleByAcceptanceCode'), 'navigation must resolve canonical modules')
assert(!navigationSource.includes('FORMAL_MODULE_ROUTES'), 'duplicate navigation route table remains')
assert(componentSource.includes('resolveFoundationPageState'), 'page state contract missing')
assert(componentSource.includes('PAGE IDENTITY MISMATCH'), 'page identity fail-fast guard missing')
assert(componentSource.includes('foundationMaintenanceGroups'), 'component group identity must come from canonical registry')
assert(!componentSource.includes('formalIdentityByEntity'), 'duplicate component identity map remains')
assert(portalSource.includes('foundationEntryGroups'), 'portal must consume canonical-derived navigation')

const identityMatrix = required.map(moduleId => {
  const identity = getFoundationCanonicalModule(moduleId)
  const modeResults = identity.availableModes.map(mode => {
    const queryValue = mode === 'view' ? undefined : mode === 'source_compare' ? 'comparison' : mode
    const state = resolveFoundationPageState({ path: identity.routePath, query: queryValue ? { view: queryValue } : {}, params: {}, meta: { canonicalModuleId: moduleId } })
    assert.equal(state.moduleId, moduleId)
    assert.equal(state.mode, mode)
    assert.equal(state.identity.dataSource, identity.dataSource)
    return mode
  })
  return {
    businessDomain: identity.businessDomain,
    moduleId,
    moduleName: identity.displayName,
    navigationKey: identity.navigationKey,
    pageKey: identity.pageKey,
    routeName: identity.routeName,
    routePath: identity.routePath,
    component: identity.component,
    dataSource: identity.dataSource,
    api: identity.api,
    defaultMode: identity.defaultMode,
    currentTab: identity.entityKey,
    acceptanceEntry: identity.availableModes.includes('acceptance') ? `${identity.routePath}?view=acceptance` : null,
    sourceCompareEntry: identity.availableModes.includes('source_compare') ? `${identity.routePath}?view=comparison` : null,
    maintenanceEntry: identity.availableModes.includes('maintain') ? `${identity.routePath}?view=maintain` : null,
    testedModes: modeResults,
  }
})

assert.throws(() => resolveFoundationPageState({ path: '/foundation/master-data/routings', query: {}, params: {}, meta: { canonicalModuleId: 'product-category' } }), /PAGE IDENTITY MISMATCH/)
assert.throws(() => resolveFoundationPageState({ path: '/foundation/master-data/product-categories', query: { view: 'acceptance' }, params: {}, meta: { canonicalModuleId: 'product-category' } }), /PAGE IDENTITY MISMATCH/)

const routeNames = new Set(foundationCanonicalRouteDefinitions.map(item => item.name))
assert.equal(routeNames.size, foundationCanonicalRouteDefinitions.length)

console.log(JSON.stringify({
  result: 'passed',
  canonicalModuleCount: foundationCanonicalModules.length,
  canonicalMaintenanceRouteCount: foundationCanonicalRouteDefinitions.length,
  duplicateAuthorityCount: 0,
  pageIdentityMismatchCount: 0,
  requiredModuleCount: required.length,
  identityMatrix,
  sourceHashes: {
    routerRegistryHash: sha('src/router/index.js'),
    moduleRegistryHash: sha('src/meta/master-data/foundationEntryUnificationRegistry.js'),
    pageComponentHash: sha('src/meta/components/ProductionFoundationMaintenance.vue'),
  },
}, null, 2))
