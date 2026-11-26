import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createPurchaseInquirySupplierQuoteHandoff }
  from '../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { validatePurchaseInquiryBusinessStateMapping }
  from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { createQuotePreparationProvider } from '../src/meta/providers/quotePreparationProvider.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const editPage = read('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const workbench = read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue')
const acceptance = read('src/meta/pages/ScmPurchaseInquiryAcceptancePage.vue')
const selector = read('src/meta/components/MaterialSupplierCandidateSelector.vue')
const runtime = read('src/meta/runtime/purchaseInquiryNextActionRuntime.js')
const supplierProvider = read('src/meta/providers/supplierCandidateProvider.js')

const inquiry = { inquiryNo: 'PI-VERIFY-7A', sourceRequestNo: 'PR-VERIFY-7A', statusCode: 'draft',
  statusLabel: '草稿', runtimeState: 'inquiry_draft',
  lines: [{ materialCode: 'MAT-A', materialName: '物料A', quantity: 1,
    supplierCandidates: [{ supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' }] }],
  suppliers: [{ supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' }] }
const handoff = createPurchaseInquirySupplierQuoteHandoff(inquiry)
const quoteFacts = createQuotePreparationProvider({ contextLoader: () => [handoff.context] }).load({ inquiryNo: inquiry.inquiryNo })

const inquiryEdit = editPage.includes('purchase-inquiry-material-supplier-decisions')
  && editPage.includes('询价基本信息') && editPage.includes('报价准备区') && editPage.includes('流程导航区')
const materialDecision = editPage.includes('v-for="(line, index) in draft.materialLines"')
  && editPage.includes('MaterialSupplierCandidateSelector') && selector.includes('MaterialSupplierCandidateContext')
const masterProvider = supplierProvider.includes("source: 'Supplier Master'")
  && supplierProvider.includes('allowFreeText: false') && !selector.includes('allow-create')
const stateMapping = validatePurchaseInquiryBusinessStateMapping({ ...inquiry,
  runtimeState: 'quote_preparation_ready' }).valid
  && workbench.includes('prop="processStatusLabel" label="流程状态"')
const nextAction = editPage.includes('PurchaseInquiryFlowNavigation')
  && editPage.includes('下一步业务动作') && editPage.includes('进入供应商报价节点')
const quoteHandoff = handoff.valid && handoff.context.materialSupplierCandidates.length === 1
  && quoteFacts.current === handoff.context && acceptance.includes('SCM_QUOTE_PREPARATION_PROVIDER')
  && acceptance.includes('暂无报价准备数据。') && handoff.context.supplierQuoteCreated === false
const reloadRecovery = runtime.includes('window.localStorage')
  && runtime.includes('contexts.splice(existingIndex, 1, handoff.context)')

const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseScmInquiryBusinessClosureV114287A.test.mjs',
  'tests/acceptance/enterprisePurchaseInquirySupplierSelectionV114287Supplement.test.mjs',
  'tests/acceptance/enterprisePurchaseInquiryBusinessRuntimeV114286.test.mjs',
  'tests/acceptance/enterprisePurchaseInquiryRuntimePersistenceV114287.test.mjs'],
{ cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(root, 'node_modules/vite/bin/vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (buildRun.status !== 0) { process.stderr.write(buildRun.stdout || ''); process.stderr.write(buildRun.stderr || '') }

const checks = [['Inquiry Edit', inquiryEdit], ['Material Supplier Decision', materialDecision],
  ['Supplier Master Provider', masterProvider], ['Business State Mapping', stateMapping],
  ['Next Action', nextAction], ['QuotePreparation Handoff', quoteHandoff],
  ['Reload Recovery', reloadRecovery], ['Regression', testRun.status === 0], ['Build', buildRun.status === 0]]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_BUSINESS_CLOSURE_READY'
  : 'SCM_PURCHASE_INQUIRY_BUSINESS_CLOSURE_FAILED')
if (!passed) process.exitCode = 1
