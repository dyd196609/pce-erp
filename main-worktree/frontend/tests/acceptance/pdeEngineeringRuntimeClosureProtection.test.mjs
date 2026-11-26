import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const repositoryRoot = path.resolve(frontendRoot, '..')
const readRepository = relative => fs.readFileSync(path.join(repositoryRoot, relative), 'utf8')
const sha256 = content => crypto.createHash('sha256').update(content).digest('hex').toUpperCase()
const manifest = JSON.parse(readRepository('docs/governance/evidence/PCE_ENGINEERING_RUNTIME_CLOSURE_SOURCE_BASELINE_V1.json'))
const page = readRepository('frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue')
const service = readRepository('backend/pde/engineering_calculation_service.py')
const projection = readRepository('backend/pde/calculation_batch_reuse.py')
const materialPreviewService = readRepository('backend/pde/order_bom_handoff_service.py')
const r1HandoffService = readRepository('backend/pde/r1_material_requirement_handoff_service.py')
const bomFoundationPage = readRepository('frontend/src/meta/pages/PdeFoundationPage.vue')
const bomHandoffComponent = readRepository('frontend/src/meta/pages/components/OrderBomHandoffPreview.vue')
const pdeApi = readRepository('frontend/src/api/pde.js')
const pdeViews = readRepository('backend/pde/views.py')
const acceptedDifferenceProfile = readRepository('docs/governance/evidence/PCE_SO202609180003_ENGINEERING_ACCEPTED_DIFFERENCES_V1.json')
const registry = readRepository('frontend/src/meta/process/businessProcessRegistry.js')
const router = readRepository('frontend/src/router/index.js')

test('工程核算直接实现文件纳入Completed Work依赖保护', () => {
  assert.equal(manifest.moduleId, 'engineering-calculation-six-continuations')
  assert.equal(manifest.status, 'DEVELOPED_NOT_CURRENTLY_VERIFIED')
  assert.equal(sha256(page), manifest.protectedSources.page)
  assert.equal(sha256(service), manifest.protectedSources.service)
  assert.equal(sha256(projection), manifest.protectedSources.projection)
  assert.equal(sha256(materialPreviewService), manifest.protectedSources.materialRequirementPreviewService)
  assert.equal(sha256(r1HandoffService), manifest.protectedSources.r1MaterialRequirementHandoffService)
  assert.equal(sha256(bomFoundationPage), manifest.protectedSources.bomFoundationPage)
  assert.equal(sha256(bomHandoffComponent), manifest.protectedSources.bomHandoffComponent)
  assert.equal(sha256(acceptedDifferenceProfile), manifest.protectedSources.acceptedDifferenceProfile)
  assert.match(service, /class EngineeringCalculationReadinessService:/)
  assert.match(service, /def build\(cls, \*, user, subview=None\):/)
  assert.match(projection, /def design_calculation_context\(user, source_record_id=None\):/)
  assert.match(materialPreviewService, /def material_requirement_preview\(\*, records, mapping_rules, company_id\):/)
  assert.match(r1HandoffService, /def apply_authorized_so202609180003_representatives\(\*, user\)/)
})

test('共享Registry只保护工程核算节点局部契约', () => {
  const contract = manifest.protectedSources.processNode
  assert.equal(manifest.sharedDependencies[0].protectionMode, 'localized_contract')
  assert.equal(manifest.sharedDependencies[0].fullFileHashIsBlocking, false)
  assert.match(registry, new RegExp(`\\['${contract.nodeCode}', '${contract.nodeName}', '${contract.pageCode}', '${contract.route}'\\]`))
  assert.match(registry, /moduleCode: 'PDE'/)
  assert.match(registry, /pageStatus: pageUrl \? 'active' : 'process_node'/)
  assert.match(registry, /acceptanceStatus: 'PASS'/)
})

test('共享Router只保护工程核算路径、名称和组件局部契约', () => {
  const contract = manifest.protectedSources.route
  assert.equal(manifest.sharedDependencies[1].protectionMode, 'localized_contract')
  assert.equal(manifest.sharedDependencies[1].fullFileHashIsBlocking, false)
  assert.match(router, new RegExp(`path: '${contract.path.slice(1)}',[\\s\\S]*name: '${contract.routeName}',[\\s\\S]*component: ${contract.wrapper}\\(\\)`))
  assert.match(router, new RegExp(`import\\('@/meta/pages/${contract.component.replace('.', '\\.')}'\\)`))
})

test('共享PDE API与View只保护材料承接的局部只读契约', () => {
  const apiContract = manifest.sharedDependencies.find(row => row.path === 'frontend/src/api/pde.js')
  const viewContract = manifest.sharedDependencies.find(row => row.path === 'backend/pde/views.py')
  assert.equal(apiContract.protectionMode, 'localized_contract')
  assert.equal(viewContract.protectionMode, 'localized_contract')
  assert.match(pdeApi, /orderBomHandoff\(params = \{\}\)/)
  assert.match(pdeApi, /method: 'GET'/)
  assert.match(pdeApi, /params: \{ handoff: 1, \.\.\.params \}/)
  assert.match(pdeViews, /class ProductBomListView/)
  assert.match(pdeViews, /materialRequirementPreview/)
  assert.match(pdeViews, /"apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"/)
})

test('保护基线Hash只覆盖工程核算直接实现与共享局部契约', () => {
  const actual = sha256(JSON.stringify(manifest.protectedSources))
  assert.equal(actual, manifest.baselineHash)
  assert.deepEqual(manifest.dependencyImpact.frozenModulesImpacted, [])
  assert.deepEqual(manifest.dependencyImpact.unrelatedModuleBaselineUpdates, [])
  assert.deepEqual(manifest.dependencyImpact.sharedSourceFilesModifiedByThisRemediation, [
    'frontend/src/api/pde.js#orderBomHandoff',
    'backend/pde/views.py#ProductBomListView.handoff',
    'frontend/src/meta/pages/PdeFoundationPage.vue#BomMaterialDetailReadback',
    'backend/pde/views.py#ProductBomListView.serialize',
  ])
})
