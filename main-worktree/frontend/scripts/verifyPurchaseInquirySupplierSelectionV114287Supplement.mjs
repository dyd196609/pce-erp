import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createSupplierCandidateProvider } from '../src/meta/providers/supplierCandidateProvider.js'
import { createPurchaseInquirySupplierCandidateContext,
  validatePurchaseInquirySupplierCandidateContext }
  from '../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierCandidateContext.js'
import { createPurchaseInquirySupplierQuoteHandoff }
  from '../src/meta/process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const selector = read('src/meta/components/SupplierCandidateSelector.vue')
const editPage = read('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const provider = createSupplierCandidateProvider({ supplierMasterLoader: () => [
  { id: 'SUP-001', supplierCode: 'SUP-001', supplierName: '供应商A', supplierStatus: 'active',
    supplierCategory: 'strategic', enabled: true },
] })
const option = provider.load({ query: '供应商A' }).options[0]
const context = createPurchaseInquirySupplierCandidateContext([option])
const handoff = createPurchaseInquirySupplierQuoteHandoff({ inquiryNo: 'PI-VERIFY-SUPPLIER-001',
  sourceRequestNo: 'PR-VERIFY-SUPPLIER-001', runtimeState: 'inquiry_draft',
  lines: [{ materialCode: 'MAT-001', materialName: '物料A', quantity: 1 }], suppliers: [option] })

const model = validatePurchaseInquirySupplierCandidateContext(context).valid
  && ['supplierCode', 'supplierName', 'supplierStatus', 'supplierCategory', 'source']
    .every(field => field in context.candidates[0])
const supplierProvider = provider.load().searchable && provider.load().selectable
  && provider.load().canAddCandidate && !provider.load().allowFreeText
const selectorActions = ['data-candidate-action="search"', 'data-candidate-action="add"',
  'data-candidate-action="remove"', 'data-candidate-action="replace"']
  .every(token => selector.includes(token)) && !selector.includes('allow-create')
const page = (editPage.includes('<SupplierCandidateSelector v-model="draft.supplierCandidates"')
  || editPage.includes('<MaterialSupplierCandidateSelector v-model="line.supplierCandidates"'))
  && editPage.includes('savePurchaseInquiryDraft')
const visible = selector.includes('candidate-card-scroll') && selector.includes('overflow-x:auto')
  && selector.includes('当前供应商候选')
const quoteHandoff = handoff.valid && handoff.context.supplierCandidates[0].supplierCategory === 'strategic'
  && handoff.context.supplierQuoteCreated === false && handoff.context.supplierSent === false
  && handoff.context.purchaseOrderCreated === false

const testRun = spawnSync(process.execPath,
  ['--test', 'tests/acceptance/enterprisePurchaseInquirySupplierSelectionV114287Supplement.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryBusinessRuntimeV114286.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryRuntimePersistenceV114287.test.mjs'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(root, 'node_modules/vite/bin/vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (buildRun.status !== 0) { process.stderr.write(buildRun.stdout || ''); process.stderr.write(buildRun.stderr || '') }

const checks = [
  ['Supplier Candidate Context', model], ['Supplier Master Provider', supplierProvider],
  ['Search Select Add', selectorActions], ['Current Candidate List', page],
  ['Visible Supplier Area', visible], ['Save Persistence', testRun.status === 0],
  ['Quote Preparation Handoff', quoteHandoff], ['Regression', testRun.status === 0],
  ['Build', buildRun.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_SUPPLIER_SELECTION_READY'
  : 'SCM_PURCHASE_INQUIRY_SUPPLIER_SELECTION_FAILED')
if (!passed) process.exitCode = 1
