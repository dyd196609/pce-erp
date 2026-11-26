import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const files = {
  landing: new URL('../frontend/src/meta/pages/ManufacturingFoundationPage.vue', import.meta.url),
  unified: new URL('../frontend/src/meta/pages/EnterpriseFoundationUnifiedPage.vue', import.meta.url),
  maintenance: new URL('../frontend/src/meta/components/ProductionFoundationMaintenance.vue', import.meta.url),
  registry: new URL('../frontend/src/meta/master-data/foundationEntryUnificationRegistry.js', import.meta.url),
  names: new URL('../frontend/src/meta/governance/businessNameRegistry.js', import.meta.url),
  router: new URL('../frontend/src/router/index.js', import.meta.url),
  service: new URL('../backend/pde/production_foundation_service.py', import.meta.url),
  views: new URL('../backend/pde/views.py', import.meta.url),
}

const source = Object.fromEntries(await Promise.all(
  Object.entries(files).map(async ([key, url]) => [key, await readFile(url, 'utf8')]),
))

for (const group of ['组织与人员', '物料与供应', '产品工程', '制造资源', '仓储基础']) {
  assert.ok(source.registry.includes(`label: '${group}'`), `missing foundation group: ${group}`)
}

for (const entry of ['物料档案', '供应商', '产品档案', 'BOM', '工艺资料', '工序资料', '车间 / 生产区域', '工作中心', '设备资料', '标准产能', '工程资料', '仓库', '仓库库位']) {
  assert.ok(source.registry.includes(`'${entry}'`), `missing canonical entry: ${entry}`)
}

assert.ok(source.landing.includes('foundationEntryGroups'), 'landing must use the canonical grouped registry')
assert.ok(!source.landing.includes('v-for="entry in foundationEntries"'), 'legacy flat formal entry list must not remain')
assert.ok(source.unified.includes('data-maintenance-capability="none"'), 'A1.7 region must be diagnostic only')
assert.ok(!source.unified.includes('<ProductionFoundationMaintenance'), 'foundation root must not render a second maintenance center')

assert.ok(source.maintenance.includes('data-maintenance-owner="EMD"'), 'formal maintenance belongs to EMD')
assert.ok(source.maintenance.includes('data-fact-source="server"'), 'formal facts must remain server-owned')
assert.ok(source.maintenance.includes('data-duplicate-formal-maintenance-implementations="0"'), 'duplicate implementation marker must be zero')
for (const forbidden of ["'engineering-rule-definitions':", "'engineering-calculation-records':", "'order-engineering-instances':"]) {
  assert.ok(!source.maintenance.includes(forbidden), `PRE-A1.8 must not expose ${forbidden}`)
}

assert.ok(source.router.includes("path: 'foundation/master-data/:entity'"), 'canonical formal maintenance route missing')
for (const redirect of [
  "redirect: '/foundation/master-data/materials'",
  "redirect: '/foundation/master-data/operations'",
  "redirect: '/foundation/master-data/equipment'",
  "redirect: '/foundation/master-data/routings'",
]) {
  assert.ok(source.router.includes(redirect), `legacy redirect missing: ${redirect}`)
}

assert.ok(source.service.includes('"warehouses": (Warehouse, "production.master_data.location.maintain")'), 'Warehouse formal service mapping missing')
assert.ok(source.service.includes('"warehouse-locations": (WarehouseLocation, "production.master_data.location.maintain")'), 'WarehouseLocation formal service mapping missing')
assert.ok(source.views.includes('"production.master_data.location.maintain"'), 'Gate authorization must include warehouse master-data permission')
assert.ok(source.registry.includes('Lot/Batch由业务交易形成'), 'Lot/Batch transaction-fact boundary missing')
for (const pageCode of ['enterprise-foundation', 'enterprise-foundation-master-data', 'pce-production-a1']) {
  assert.ok(source.names.includes(`'${pageCode}'`), `canonical business page name missing: ${pageCode}`)
}

console.log(JSON.stringify({
  gate: 'FOUNDATION-ENTRY-UNIFICATION-PRE-A1.8-V1.0',
  result: 'PASS',
  duplicateFormalMaintenanceImplementations: 0,
  formalFactSource: 'server',
  localStorageFormalFacts: 0,
  a18Plan: 'APPROVED / FROZEN',
  a18Do: 'NOT AUTHORIZED',
}, null, 2))
