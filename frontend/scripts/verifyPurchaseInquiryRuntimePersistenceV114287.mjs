import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createPurchaseInquiryRuntimeStore } from '../src/meta/runtime/purchaseInquiryRuntimeStore.js'
import { createPurchaseInquiryProvider } from '../src/meta/providers/purchaseInquiryProvider.js'
import { createSupplierCandidateProvider } from '../src/meta/providers/supplierCandidateProvider.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const workbench = read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue')
const detailPage = read('src/meta/pages/ScmPurchaseInquiryDetailPage.vue')
const editPage = read('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const acceptancePage = read('src/meta/pages/ScmPurchaseInquiryAcceptancePage.vue')
const lifecycleProviderSource = read('src/meta/providers/purchaseInquiryLifecycleProvider.js')
const values = new Map()
const storage = { getItem: key => values.has(key) ? values.get(key) : null,
  setItem: (key, value) => values.set(key, String(value)) }
const inquiry = Object.freeze({ inquiryNo: 'PI-PERSIST-VERIFY-001', sourcePreparationNo: 'IPR-PERSIST-VERIFY-001',
  sourceRequestNo: 'PR-PERSIST-VERIFY-001', buyer: '采购员A', inquiryTitle: '持久化验证询价',
  inquiryDate: '2026-08-04', lines: [{ materialCode: 'MAT-001', materialName: '物料A', quantity: 2 }],
  suppliers: [{ supplierId: 'SUP-001', supplierName: '供应商A' }],
  status: 'draft', statusCode: 'draft', runtimeState: 'inquiry_draft' })
const firstStore = createPurchaseInquiryRuntimeStore({ storage, storageKey: 'verify-runtime-store' })
const created = firstStore.create(inquiry)
const saved = firstStore.save({ ...created, buyer: '采购员B', lines: [{ ...created.lines[0], quantity: 8 }] })
const reopenedStore = createPurchaseInquiryRuntimeStore({ storage, storageKey: 'verify-runtime-store' })
const reloaded = reopenedStore.reload()
const runtimeStore = created.inquiryNo === inquiry.inquiryNo && saved.buyer === '采购员B'
  && ['inquiryNo', 'sourcePreparationNo', 'sourceRequestNo', 'buyer', 'lines', 'suppliers', 'status']
    .every(field => field in reloaded[0])
const reload = reloaded.length === 1 && reloaded[0].lines[0].quantity === 8
  && reloaded[0].persistenceMode === 'browser_runtime_store'
const provider = createPurchaseInquiryProvider({ runtimeStore: reopenedStore })
const providerFacts = provider.load({ serverFacts: { objects: [] } })
const listRestore = providerFacts.existingInquiryList.some(item => item.inquiryNo === inquiry.inquiryNo)
  && lifecycleProviderSource.includes('purchaseInquiryProvider.load')
  && lifecycleProviderSource.includes('existingInquiryList')
const supplierProvider = createSupplierCandidateProvider({ supplierMasterLoader: () => [
  { id: 'SUP-001', supplierCode: 'SUP-001', supplierName: '供应商A', enabled: true },
  { id: 'SUP-002', supplierCode: 'SUP-002', supplierName: '供应商B', enabled: true },
] })
const supplierSearch = supplierProvider.load({ query: 'SUP-001' })
const supplierProviderPassed = supplierSearch.recordCount === 1 && supplierSearch.searchable
  && supplierSearch.selectable && supplierSearch.canAddCandidate && !supplierSearch.allowFreeText
  && editPage.includes('data-provider-code="SupplierCandidateProvider"')
  && !editPage.includes('allow-create')
const actionName = workbench.includes('批量准备供应商报价')
  && !workbench.includes('批量查看') && !workbench.includes('批量编辑')
const nextAction = [workbench, detailPage, editPage, acceptancePage].every(source => source.includes('当前状态'))
  && workbench.includes('下一步业务动作') && detailPage.includes('下一流程动作')
  && editPage.includes('SAVE_PURCHASE_INQUIRY') && detailPage.includes('PREPARE_SUPPLIER_QUOTE')
const regression = providerFacts.recordCount >= 1 && saved.statusCode === 'draft'
  && saved.sentToSupplier !== true && saved.createdPurchaseOrder !== true && saved.productionDataWritten === false

const testRun = spawnSync(process.execPath,
  ['--test', 'tests/acceptance/enterprisePurchaseInquiryRuntimePersistenceV114287.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryBusinessRuntimeV114286.test.mjs',
    'tests/acceptance/enterprisePurchaseInquiryNodeRuntimeV11428184.test.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }
const checks = [['Runtime Store', runtimeStore], ['Reload', reload], ['List Restore', listRestore],
  ['Supplier Provider', supplierProviderPassed], ['Action Name', actionName], ['Next Action', nextAction],
  ['Regression', regression && testRun.status === 0], ['Build', build.status === 0]]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_RUNTIME_PERSISTENCE_READY'
  : 'SCM_PURCHASE_INQUIRY_RUNTIME_PERSISTENCE_FAILED')
if (!passed) process.exitCode = 1
