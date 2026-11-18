import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { foundationCanonicalRouteDefinitions, foundationEntryAuditRows, foundationEntryGroups, getFoundationCanonicalModule } from '../src/meta/master-data/foundationEntryUnificationRegistry.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')
const router = read('src/router/index.js')
const portal = read('src/meta/pages/EnterpriseFoundationUnifiedPage.vue')
const maintenance = read('src/meta/components/ProductionFoundationMaintenance.vue')

const entries = foundationEntryGroups.flatMap(group => group.entries)
const operationEntry = entries.find(item => item.objectCode === 'Process')
const routingEntry = entries.find(item => item.objectCode === 'Routing')
const routingStepAudit = foundationEntryAuditRows.find(item => item.object === 'RoutingStep')

const routeContracts = [
  { entity: 'operations', name: 'FoundationFormalOperations', model: 'system.Process', pageKey: 'foundation-formal-operations' },
  { entity: 'routings', name: 'FoundationFormalRoutings', model: 'pde.Routing', pageKey: 'foundation-formal-routings' },
  { entity: 'routing-steps', name: 'FoundationFormalRoutingSteps', model: 'pde.RoutingStep', pageKey: 'foundation-formal-routing-steps' },
]

const checks = {
  operationCardTargetsOperation: operationEntry?.route === '/foundation/master-data/operations'
    && operationEntry?.routeName === 'FoundationFormalOperations'
    && operationEntry?.navigationKey === 'manufacturing-resource.operation',
  routingCardTargetsRouting: routingEntry?.route === '/foundation/master-data/routings'
    && routingEntry?.routeName === 'FoundationFormalRoutings'
    && routingEntry?.navigationKey === 'product-engineering.routing',
  routingStepTargetsRoutingStep: routingStepAudit?.finalEntry === '/foundation/master-data/routing-steps',
  portalUsesRegisteredNamedTarget: portal.includes(':to="item.routeName ? { name: item.routeName } : item.route"')
    && portal.includes(':data-navigation-key="item.navigationKey"')
    && portal.includes("scrollIntoView({ behavior: 'auto'"),
  explicitRoutesAreDistinct: routeContracts.every(contract => foundationCanonicalRouteDefinitions.some(item => item.entityKey === contract.entity
    && item.name === contract.name
    && item.meta.formalModel === contract.model
    && item.meta.pageCode === contract.pageKey))
    && router.includes('...foundationCanonicalRouteDefinitions.map'),
  pageIdentitiesAreDistinct: routeContracts.every(contract => {
    const identity = getFoundationCanonicalModule(contract.entity === 'operations' ? 'operation' : contract.entity === 'routings' ? 'routing' : 'routing-step')
    return identity?.dataSource === contract.model && identity?.pageKey === contract.pageKey
  }) && maintenance.includes('resolveFoundationPageState'),
  operationUsesExactApi: maintenance.includes("pdeApi.productionFoundationA1('operations')")
    && maintenance.includes("operationFacts.value = requireSuccess(operationResponse)?.facts?.operations || []"),
  operationDoesNotUseRoutingData: getFoundationCanonicalModule('operation')?.dataSource === 'system.Process'
    && getFoundationCanonicalModule('routing')?.dataSource === 'pde.Routing'
    && getFoundationCanonicalModule('routing-step')?.dataSource === 'pde.RoutingStep',
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
if (failed.length) {
  console.error(JSON.stringify({ result: 'failed', failed, checks }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({
  result: 'passed',
  contract: 'P0-USER-VISIBLE-OPERATION-ROUTE-RECOVERY',
  operationTarget: operationEntry,
  routingTarget: routingEntry,
  routingStepTarget: routingStepAudit,
  routeContracts,
  checks,
  productionBusinessDataWrite: 0,
}, null, 2))
