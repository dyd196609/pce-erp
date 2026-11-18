import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadProcessCenterRuntimeModel } from '../src/meta/runtime/processCenterRuntime.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const model = loadProcessCenterRuntimeModel()
const failures = []

const assert = (condition, message) => {
  if (!condition) failures.push(message)
}

const processCodes = new Set()
for (const process of model.processes) {
  assert(!processCodes.has(process.processCode), `duplicate processCode: ${process.processCode}`)
  processCodes.add(process.processCode)
}

const results = model.modules.map((module) => {
  const processes = model.processes.filter(process => process.moduleCode === module.moduleCode)
  assert(processes.length <= 1, `${module.moduleCode} has ${processes.length} formal root processes`)
  const process = processes[0] || null
  if (process) {
    assert(process.nodes.every(node => node.moduleCode === module.moduleCode), `${module.moduleCode} contains foreign nodes`)
    assert(process.nodes.every(node => !node.pageUrl || node.pageCode), `${module.moduleCode} contains a route without pageCode`)
  }
  return {
    moduleCode: module.moduleCode,
    processCode: process?.processCode || null,
    formalRootCount: processes.length,
    nodeCount: process?.nodes?.length || 0,
    result: processes.length === 1 ? 'FORMAL_FLOW' : 'EXPLICIT_EMPTY',
  }
})

const pde = model.processes.find(process => process.moduleCode === 'PDE')
const expectedPdeCapabilities = new Map([
  ['product-order-demand', '/pde/product-requirements'],
  ['engineering-readiness-control', '/pde/engineering-readiness'],
  ['product-requirement-review', '/pde/product-requirement-reviews'],
  ['product-design-management', '/pde/product-definitions'],
  ['product-version-management', '/pde/product-versions'],
  ['engineering-material-calculation', '/pde/engineering-calculations'],
  ['bom-management', '/pde/product-boms'],
  ['bom-version-management', '/pde/bom-versions'],
  ['routing-management', '/pde/routings'],
  ['routing-version-management', '/pde/routing-versions'],
  ['engineering-data-release', '/pde/engineering-documents'],
  ['engineering-change-ecn', '/pde/engineering-changes'],
  ['trial-production-validation', '/pde/trial-production-validations'],
  ['mass-production-introduction', '/pde/mass-production-introductions'],
  ['manufacturing-output-confirmation', '/pde/manufacturing-outputs'],
  ['manufacturing-admission-confirmation', '/pde/manufacturing-admissions'],
  ['production-demand-admission', '/sales/orders'],
  ['mrp-input-preparation', '/pde/mrp-input-preparation'],
])
assert(Boolean(pde), 'PDE formal process missing')
assert(!pde?.nodes?.some(node => node.nodeCode === 'pde-product-engineering-workbench'), 'PDE duplicate portal rendered as a formal node')
const pdeNodeCodes = pde?.nodes?.map(node => node.nodeCode) || []
const calculationIndexes = pdeNodeCodes
  .map((nodeCode, index) => nodeCode === 'engineering-material-calculation' ? index : -1)
  .filter(index => index >= 0)
assert(calculationIndexes.length === 1, `engineering-material-calculation occurrence count: ${calculationIndexes.length}`)
const calculationIndex = calculationIndexes[0] ?? -1
assert(pdeNodeCodes[calculationIndex - 1] === 'product-version-management', 'engineering-material-calculation previous node must be product-version-management')
assert(pdeNodeCodes[calculationIndex + 1] === 'bom-management', 'engineering-material-calculation next node must be bom-management')
for (const [nodeCode, route] of expectedPdeCapabilities) {
  const node = pde?.nodes?.find(item => item.nodeCode === nodeCode)
  assert(Boolean(node), `PDE capability missing: ${nodeCode}`)
  assert(node?.pageUrl === route, `PDE route mismatch: ${nodeCode}`)
}
assert(pde?.nodes?.[14]?.nodeCode === 'manufacturing-output-confirmation', 'PDE node15 engineering output identity changed')
assert(pde?.nodes?.[15]?.nodeCode === 'manufacturing-admission-confirmation', 'PDE node16 must map to manufacturing admission')
assert(pde?.nodes?.[15]?.workflowBinding?.processDefinitionId === 10, 'manufacturing admission process binding missing')
assert(pde?.nodes?.[15]?.workflowBinding?.workflowNodeId === 48, 'manufacturing admission node binding missing')
assert(pde?.nodes?.find(node => node.nodeCode === 'mrp-input-preparation')?.sequence > 16, 'MRP input preparation must remain a later planning node')

const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/EnterpriseOSPage.vue'), 'utf8')
assert(routerSource.includes("name: 'PdeProductEngineeringWorkbenchLegacyRedirect'"), 'legacy PDE workbench redirect missing')
assert(routerSource.includes("path: '/process-center'"), 'legacy PDE redirect does not use canonical process center')
assert(!pageSource.includes('pde-workbench-primary-entry'), 'PDE portal region remains in process center')
assert(!pageSource.includes('process-center-page-navigation'), 'secondary page catalog remains in process center')
assert(pageSource.includes('本模块尚未配置正式运作流程'), 'explicit no-flow empty state missing')

const report = {
  generatedAt: new Date().toISOString(),
  rule: 'SINGLE MODULE / SINGLE FORMAL FLOW',
  moduleCount: model.modules.length,
  processCount: model.processes.length,
  modules: results,
  pdeExpectedCapabilityCount: expectedPdeCapabilities.size,
  pdeNodeCodes,
  pdeCalculationSequence: calculationIndex >= 0 ? calculationIndex + 1 : null,
  pdeCalculationPreviousNode: pdeNodeCodes[calculationIndex - 1] || null,
  pdeCalculationNextNode: pdeNodeCodes[calculationIndex + 1] || null,
  pdeDuplicatePortalCount: pde?.nodes?.filter(node => node.nodeCode === 'pde-product-engineering-workbench').length || 0,
  productionWrites: 0,
  failures,
  passed: failures.length === 0,
}

const outputDir = path.join(frontendRoot, 'test-results', 'single-formal-flow')
fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(path.join(outputDir, 'static-runtime-report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exitCode = 1
