import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SYSTEM_CONFIG_CURRENT_MODULE_SET, SYSTEM_CONFIG_EXPECTED_MODULE_SET, assertSystemConfigNonRegression } from '../src/meta/navigation/systemConfigNonRegressionRegistry.js'
import { FOUNDATION_FORMAL_ENTITY_CONTRACT } from '../src/meta/master-data/foundationNavigationRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')
const page = read('src/meta/pages/EnterpriseOSPage.vue')
const maintenance = read('src/meta/components/ProductionFoundationMaintenance.vue')
const businessNameRegistry = read('src/meta/governance/businessNameRegistry.js')

assertSystemConfigNonRegression()
const missingVisibleModules = SYSTEM_CONFIG_CURRENT_MODULE_SET.filter(item => !page.includes(item.label) || !page.includes(item.route))
const entityContractsValid = Object.entries(FOUNDATION_FORMAL_ENTITY_CONTRACT).every(([key, item]) => {
  const expectedModel = { operations: 'system.Process', routings: 'pde.Routing', routingSteps: 'pde.RoutingStep' }[key]
  return item.dataSource === expectedModel && item.routePath.includes(key === 'routingSteps' ? 'routing-steps' : key)
})
const paramChangeGuardPresent = maintenance.includes("watch([() => route.fullPath, () => props.initialEntity]")
const internalNavigationSyncsRoute = maintenance.includes('navigateToEntity(targetEntity)')
  && maintenance.includes('navigateToEntity(key)')
  && maintenance.includes('getFoundationCanonicalModuleByEntity(entity)')
  && maintenance.includes('router.push({ name: identity.routeName })')
const systemConfigTitlesRegistered = ['/admin', '/admin/role-permission', '/admin/config/menu', '/admin/process-template', '/admin/tenant-setting']
  .every(route => businessNameRegistry.includes(`'${route}'`))
const operationCanonicalTitleRegistered = businessNameRegistry.includes("['FoundationFormalOperations','formal-operation-data','工序资料','foundation-formal-operations','/foundation/master-data/operations','EMD']")
export function operationVisibilityContractPresentIn(source, contract) {
  return source.includes(':data-formal-model="currentIdentity.dataSource"')
    && source.includes(":data-api-record-count=\"currentIdentity.dataSource === 'system.Process' ? currentRecordCount : undefined\"")
    // Failed/unloaded facts must remain unknown; raw array length would invent 0.
    && source.includes("const currentRecordCount = computed(() => loadStatus.value === 'loaded' && !providerFailed.value ? currentRows.value.length : null)")
    && source.includes('operationFacts.value = operation.facts.operations')
    && contract.dataSource === 'system.Process'
    && ['calculation_basis_label', 'calculation_uom_label', 'transition_mode_label', 'is_active'].every(field => source.includes(field))
    && ['查看数据', '维护', '来源对照', '人工验收'].every(label => source.includes(`>${label}</button>`))
}
const operationVisibilityContractPresent = operationVisibilityContractPresentIn(maintenance, FOUNDATION_FORMAL_ENTITY_CONTRACT.operations)

if (missingVisibleModules.length || !entityContractsValid || !paramChangeGuardPresent || !internalNavigationSyncsRoute || !systemConfigTitlesRegistered || !operationCanonicalTitleRegistered || !operationVisibilityContractPresent) {
  console.error(JSON.stringify({ result: 'failed', missingVisibleModules, entityContractsValid, paramChangeGuardPresent, internalNavigationSyncsRoute, systemConfigTitlesRegistered, operationCanonicalTitleRegistered, operationVisibilityContractPresent }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({
  result: 'passed',
  principle: 'PCE NON-REGRESSION PRINCIPLE',
  expectedExistingModules: SYSTEM_CONFIG_EXPECTED_MODULE_SET.map(item => item.label),
  currentModules: SYSTEM_CONFIG_CURRENT_MODULE_SET.map(item => item.label),
  existingFunctionRegression: 0,
  internalNavigationSyncsRoute,
  systemConfigTitlesRegistered,
  operationCanonicalTitleRegistered,
  operationVisibilityContractPresent,
  formalEntityContracts: FOUNDATION_FORMAL_ENTITY_CONTRACT,
}, null, 2))
