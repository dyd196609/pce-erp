import { DatabaseSync } from 'node:sqlite'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { getFoundationCanonicalModule } from '../src/meta/master-data/foundationEntryUnificationRegistry.js'

const root = resolve(import.meta.dirname, '..', '..')
const sourcePath = resolve(root, 'backend', 'masterdata', 'group3_comparison_source.json')
const source = JSON.parse(readFileSync(sourcePath, 'utf8'))
const runtimeSource = readFileSync(resolve(root, 'backend', 'masterdata', 'group3_comparison_runtime.py'), 'utf8')
const pageSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'pages', 'Group3ManufacturingEngineeringAcceptancePage.vue'), 'utf8')
const maintenanceSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'components', 'ProductionFoundationMaintenance.vue'), 'utf8')
const entrySource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'master-data', 'foundationEntryUnificationRegistry.js'), 'utf8')
const routerSource = readFileSync(resolve(root, 'frontend', 'src', 'router', 'index.js'), 'utf8')
const acceptanceCenterSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'pages', 'BaseDataManualAcceptanceCenterPage.vue'), 'utf8')
const foundationPortalSource = readFileSync(resolve(root, 'frontend', 'src', 'meta', 'pages', 'EnterpriseFoundationUnifiedPage.vue'), 'utf8')
const dbPath = resolve(root, 'backend', 'db.sqlite3')
const dbBytes = readFileSync(dbPath)
const dbHash = createHash('sha256').update(dbBytes).digest('hex').toUpperCase()
const db = new DatabaseSync(dbPath, { readOnly: true })
const scalar = (sql) => Number(db.prepare(sql).get().value)
const operationRows = db.prepare(`
  select id, code, name, display_order, default_transition_mode
  from system_process where company_id = 1 order by display_order, id
`).all()
const aliases = db.prepare(`
  select external_id, target_entity_id, mapping_status
  from masterdata_external_identity
  where organization_id = 1 and source_system = '02工艺路线.xlsx'
    and source_type = 'USER_VALIDATED_ALIAS'
    and source_object_type = 'ROUTING_STEP_OPERATION_VALUE'
    and external_id = '拉丝' and target_entity_type = 'operations'
`).all()
const formalCounts = {
  routing: scalar('select count(*) as value from pde_routing where company_id = 1'),
  routingVersion: scalar('select count(*) as value from pde_routing_version'),
  routingStep: scalar('select count(*) as value from pde_routing_step'),
}
const formalIntegrity = {
  categoryScopedRoutes: scalar("select count(*) as value from pde_routing where company_id = 1 and applicability_scope = 'PRODUCT_CATEGORY' and product_category_id is not null and manufacturing_process_type_id is not null and product_id is null and order_engineering_instance_id is null"),
  systemInitialVersions: scalar("select count(*) as value from pde_routing_version where routing_version = 'SYSTEM_INITIAL_VERSION' and product_id is null and product_version_id is null and status = 'released'"),
  pinpiSteps: scalar("select count(*) as value from pde_routing_step s join system_process p on p.id=s.operation_id where p.name = '拼皮'"),
  lasiSteps: scalar("select count(*) as value from pde_routing_step s join system_process p on p.id=s.operation_id where p.name = '拉丝/打磨'"),
  lasiSourceTrace: scalar("select count(*) as value from masterdata_external_identity where target_entity_type = 'routing-steps' and mapping_status = 'MATCH' and json_extract(audit_metadata, '$.sourceOperationName') = '拉丝'"),
  bom: scalar('select count(*) as value from pde_product_bom'),
  bomVersion: scalar('select count(*) as value from pde_bom_version'),
  bomItem: scalar('select count(*) as value from pde_bom_item'),
  productDefinition: scalar('select count(*) as value from pde_product_definition'),
  productVersion: scalar('select count(*) as value from pde_product_version'),
}
db.close()

const operationsByName = new Map(operationRows.map((row) => [row.name, row]))
const aliasTarget = aliases.length === 1 ? operationRows.find((row) => String(row.id) === aliases[0].target_entity_id) : null
const stepResolutions = source.routingStepRows.map((row) => {
  if (operationsByName.has(row.operationName)) return { ...row, status: 'RESOLVED', target: row.operationName }
  if (row.operationName === '拉丝' && aliasTarget?.name === '拉丝/打磨' && aliases[0].mapping_status === 'MATCH') {
    return { ...row, status: 'RESOLVED', target: aliasTarget.name }
  }
  return { ...row, status: 'UNRESOLVED', target: '' }
})
const categorySummary = Object.fromEntries(['房门', '饰面', '柜体'].map((category) => {
  const routes = source.routingRows.filter((row) => row.applicableProductCategory === category)
  return [category, {
    routeCount: routes.length,
    minSteps: Math.min(...routes.map((row) => row.stepCount)),
    maxSteps: Math.max(...routes.map((row) => row.stepCount)),
  }]
}))
const routeTypes = new Set(source.routingRows.map((row) => row.routeCode.replace(/\/(FM|SM|GT)$/, '')))
const anomalyRoutes = source.routingRows.filter((route) => {
  const steps = source.routingStepRows.filter((step) => step.routeCode === route.routeCode).sort((a, b) => a.sequence - b.sequence)
  const sequences = steps.map((step) => step.sequence)
  const names = steps.map((step) => step.operationName)
  const expected = Array.from({ length: steps.length }, (_, index) => index + 1)
  return new Set(sequences).size !== sequences.length
    || new Set(names).size !== names.length
    || sequences.some((value, index) => value !== expected[index])
    || steps[0]?.predecessorSequence != null
    || steps.at(-1)?.nextSequence != null
    || steps.some((step) => step.predecessorSequence != null && step.predecessorSequence >= step.sequence)
})
const kittingNames = operationRows.filter((row) => row.default_transition_mode === 'KITTING').map((row) => row.name)
const checks = {
  sourceRouteCount42: source.routingRows.length === 42,
  sourceStepCount1137: source.routingStepRows.length === 1137,
  categoryCounts14Each: Object.values(categorySummary).every((row) => row.routeCount === 14),
  categoryStepRange11To30: Object.values(categorySummary).every((row) => row.minSteps === 11 && row.maxSteps === 30),
  interpretedAs14TypesTimes3Categories: routeTypes.size === 14,
  formalRoutingCountsExact: formalCounts.routing === 42 && formalCounts.routingVersion === 42 && formalCounts.routingStep === 1137,
  formalApplicabilityExact: formalIntegrity.categoryScopedRoutes === 42 && formalIntegrity.systemInitialVersions === 42,
  protectedFormalCountsZero: formalIntegrity.bom === 0 && formalIntegrity.bomVersion === 0 && formalIntegrity.bomItem === 0
    && formalIntegrity.productDefinition === 0 && formalIntegrity.productVersion === 0,
  operationCount33Frozen: operationRows.length === 33,
  operationOrderFrozen: operationRows[0]?.name === '开料' && operationRows[0]?.display_order === 1
    && operationRows[1]?.name === '拼皮' && operationRows[1]?.display_order === 2,
  transitionDecisionFrozen: kittingNames.length === 3 && ['白坯检验', '试装', '成品检'].every((name) => kittingNames.includes(name))
    && operationRows.filter((row) => row.default_transition_mode === 'GENERAL').length === 30,
  allStepsResolved: stepResolutions.every((row) => row.status === 'RESOLVED'),
  aliasThreeOfThree: stepResolutions.filter((row) => row.operationName === '拉丝' && row.target === '拉丝/打磨').length === 3,
  pinpiNotInvented: source.routingStepRows.every((row) => row.operationName !== '拼皮'),
  formalAliasAndPinpiExact: formalIntegrity.lasiSourceTrace === 3 && formalIntegrity.lasiSteps >= 3 && formalIntegrity.pinpiSteps === 0,
  structuralAnomalyCountZero: anomalyRoutes.length === 0,
  backendBuildsRouteCards: runtimeSource.includes('"routeCards": route_cards')
    && runtimeSource.includes('"anomalyRouteCount": anomaly_route_count')
    && runtimeSource.includes('"productionManufacturingMasterDataWriteCount": 0')
    && runtimeSource.includes('result["strictFacts"] = strict_facts'),
  uiShowsRepresentativeAndAll42: pageSource.includes('第一批代表路线')
    && pageSource.includes('查看全部42张路线卡') && pageSource.includes('v-for="step in card.steps"'),
  uiFirstScreenShows14TypesAnd6Representatives: pageSource.includes('data-acceptance-id="group3b-user-visible-first-screen"')
    && pageSource.includes('aria-label="首屏工艺类型与代表路线速览"')
    && pageSource.includes('routeTypeGroups.length')
    && pageSource.includes('facts.representativeRouteCards?.length || 0'),
  uiShowsRequiredStepFacts: ['前一道：', '下一道：', 'transitionModeLabel', 'operationMappingStatusLabel', '异常/待确认：'].every((token) => pageSource.includes(token)),
  sameModuleAcceptanceEntry: getFoundationCanonicalModule('routing')?.availableModes.includes('acceptance')
    && maintenanceSource.includes("setModuleMode('acceptance')") && maintenanceSource.includes('currentIdentity.value.routeName')
    && maintenanceSource.includes("'routing-acceptance-mode': routingSubview"),
  normalProductEngineeringEntry: getFoundationCanonicalModule('routing')?.routePath === '/foundation/master-data/routings'
    && getFoundationCanonicalModule('routing')?.navigationKey === 'product-engineering.routing'
    && foundationPortalSource.includes('本模块含来源人工验收')
    && !entrySource.includes("module('routing', 'routings', 'product-engineering', '工艺资料'"),
  group1And2AcceptanceRoutesPreserved: routerSource.includes("name: 'BaseDataComparisonPreview'")
    && routerSource.includes("name: 'Group2ComparisonPreview'")
    && acceptanceCenterSource.includes('facts.groups') && acceptanceCenterSource.includes('moduleActions(group, item)'),
}

if (Object.values(checks).some((value) => !value)) {
  console.error(JSON.stringify({ result: 'failed', checks, formalCounts, formalIntegrity, categorySummary, kittingNames, dbHash }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({
  result: 'passed', checks, dbHash, formalCounts, formalIntegrity,
  source: { routeCount: source.routingRows.length, stepCount: source.routingStepRows.length, routeTypeCount: routeTypes.size },
  mapping: {
    resolved: stepResolutions.filter((row) => row.status === 'RESOLVED').length,
    unresolved: stepResolutions.filter((row) => row.status === 'UNRESOLVED').length,
    conflict: 0,
    alias: { source: '拉丝', target: '拉丝/打磨', resolved: 3, total: 3 },
    pinpiSourceOccurrences: 0,
    structuralAnomalyRoutes: anomalyRoutes.map((row) => row.routeCode),
  },
  categorySummary, group3aFrozen: { operationCount: operationRows.length, firstTwo: operationRows.slice(0, 2), kittingNames },
  bomFormalWrite: 0,
}, null, 2))
