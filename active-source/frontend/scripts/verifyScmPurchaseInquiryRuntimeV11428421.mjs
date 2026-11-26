import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(repositoryRoot, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(repositoryRoot, relative))

const router = read('frontend/src/router/index.js')
const page = read('frontend/src/meta/pages/ScmPurchaseInquiryNodePage.vue')
const provider = read('frontend/src/meta/providers/purchaseInquiryProvider.js')
const api = read('frontend/src/api/purchaseCanary.js')
const projection = read('backend/purchase_canary/purchase_inquiry_runtime.py')
const factsView = read('backend/procurement/scm_page_facts.py')
const profile = read('frontend/src/meta/acceptance/scm/purchaseInquiryAcceptanceProfile.js')
const shell = read('frontend/src/meta/components/PceListPageShell.vue')

const scenarios = [
  'HAPPY_PATH', 'PRICE_EXCEPTION', 'QUALITY_FAIL', 'QUANTITY_DIFFERENCE',
  'SOURCE_MISSING', 'INVOICE_VALIDATION_FAILED', 'DUPLICATE_INVOICE', 'SOURCE_STALE',
]
const database = new DatabaseSync(path.join(repositoryRoot, 'backend/canary-data/scm-canary-flow-v1.sqlite3'), { readOnly: true })
const sourceRows = database.prepare(`
  SELECT pr.object_no AS request_no, pi.object_no AS inquiry_no
  FROM pce_purchase_canary_module_object pr
  JOIN pce_purchase_canary_module_object pi
    ON pi.scenario_id = pr.scenario_id AND pi.module_code = 'purchase-inquiry'
  WHERE pr.module_code = 'purchase-request'
  ORDER BY pr.object_no
`).all()
database.close()

const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })
const canonicalRoutes = router.match(/path:\s*['"]scm\/purchase-inquiry['"]/g) || []
const sourceMappingPass = scenarios.every((scenario, index) =>
  projection.includes(`"${scenario}": ${index + 1}`)
  && sourceRows.some(row => row.request_no === `PRQ-CAN-${String(index + 1).padStart(3, '0')}`
    && row.inquiry_no === `PI-CAN-${String(index + 1).padStart(3, '0')}`))

check('Governance Files Loaded', [
  'PCE-ERP开发治理总规范.md', '页面开发规范.md', 'PCE-ERP统一页面验收标准V1.1.md',
  '一页一验收规范.md', '金丝雀测试管理规范.md',
].every(name => exists(`docs/governance/${name}`)))
check('Current State Report', exists('docs/acceptance/scm_purchase_inquiry_current_state_report.md'))
check('One Page Acceptance Archive', exists('frontend/test-results/SCM-PURCHASE-INQUIRY-ACT-001.md')
  && read('frontend/test-results/SCM-PURCHASE-INQUIRY-ACT-001.md').includes('PAGE_READY'))
check('Page Unique', canonicalRoutes.length === 1 && (router.match(/ScmPurchaseInquiryNodePage\.vue/g) || []).length === 1)
check('Single Page Canary Ownership', router.includes("{ pageOwnsCanary: true }")
  && shell.includes("pageOwnsCanary: { type: Boolean, default: false }")
  && shell.includes("enterpriseCanaryMode && !props.pageOwnsCanary"))
check('Production/Canary Isolation', provider.includes("dataMode = canary.isCanaryMode ? 'canary_acceptance' : 'production'")
  && provider.includes('productionApiCallCount: canary.isCanaryMode ? 0 : 1')
  && provider.includes('canaryApiCallCount: canary.isCanaryMode ? 1 : 0'))
check('Eight Scenario Mapping', sourceMappingPass, sourceRows)
check('Production/Canary API Mutual Exclusion', provider.includes("await getScmStandardPageFacts('purchase-inquiry')")
  && provider.includes('await getPurchaseInquiryCanaryRuntime')
  && api.includes('/api/pce/purchase-canary/purchase-inquiry-runtime'))
check('PurchaseRequest Traceable', factsView.includes('"sourceRequestNo": value.source_purchase_request.request_no')
  && projection.includes('"sourceEvidence"') && page.includes('data-acceptance-region="source-purchase-request"'))
check('Refresh Persistence', page.includes('route.query.canaryBatchId') && page.includes('route.query.scenarioCode')
  && page.includes('watch(()=>[route.query.canaryBatchId,route.query.scenarioCode],refresh)'))
check('SCM-INQUIRY-001', profile.includes("'SCM-INQUIRY-001'")
  && /pageAcceptanceCode:\s*'SCM-PURCHASE-INQUIRY-ACT-001(?:-R1)?'/.test(profile)
  && page.includes('data-guide-contract="GUIDE-001..010"'))
check('No PurchaseOrder Creation', provider.includes('purchaseOrderCreated: false')
  && projection.includes('"purchaseOrderCreated": False')
  && !page.includes('createPurchaseOrder'))
check('Production Data Protection', provider.includes('productionUserDataWritten: false')
  && projection.includes('"productionUserDataWritten": False'))

const staticPassed = checks.every(item => item.pass)
let buildPassed = false
if (staticPassed) {
  const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
    cwd: frontendRoot,
    encoding: 'utf8',
    timeout: 180000,
  })
  buildPassed = build.status === 0
  check('Build', buildPassed, buildPassed ? 'vite build completed' : `${build.stdout}\n${build.stderr}`.slice(-3000))
} else check('Build', false, 'blocked by static acceptance failure')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
const passed = checks.every(item => item.pass)
console.log(`productionUserDataWritten=${false}`)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_RUNTIME_READY' : 'SCM_PURCHASE_INQUIRY_RUNTIME_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${JSON.stringify(item.evidence)}`)
  process.exitCode = 1
}
