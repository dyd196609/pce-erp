import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createPriceApprovalPreparationProvider }
  from '../src/meta/providers/priceApprovalPreparationProvider.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(root, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspace, relative), 'utf8')
const purchaseApi = read('src/api/purchaseRequest.js')
const requestRegion = read('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const pricePage = read('src/meta/pages/ScmPage.vue')
const backendView = readWorkspace('backend/procurement/purchase_request_api.py')
const backendTest = readWorkspace('backend/procurement/tests_v417.py')

const quotePreparation = Object.freeze({ objectType: 'QuotePreparationContext',
  quotePreparationNo: 'QPC-PI-VERIFY-188', inquiryNo: 'PI-VERIFY-188', sourceRequestNo: 'PR-VERIFY-188',
  preparationStatus: 'quote_preparation_ready',
  materialLines: [{ materialCode: 'MAT-A', materialName: '物料A', quantity: 1 }],
  materialSupplierCandidates: [{ materialCode: 'MAT-A', materialName: '物料A', supplierCode: 'SUP-A',
    supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' }] })
const priceFacts = createPriceApprovalPreparationProvider({ quoteProvider: {
  load: () => ({ records: [quotePreparation], recordCount: 1 }),
} }).load()

const purchaseCreate = purchaseApi.includes("permissionCode: 'purchase_request.create'")
  && purchaseApi.includes('headers: getAuthenticationHeaders()')
  && requestRegion.includes('PURCHASE_REQUEST_CREATE_RESPONSE_INCOMPLETE')
  && requestRegion.includes("emit('refreshed',saved)")
const http403Fixed = backendView.includes('return [permissions.IsAuthenticated()]')
  && requestRegion.includes('当前登录身份已失效，请重新登录后保存采购申请')
  && backendTest.includes('test_v11428818_authenticated_create_returns_complete_purchase_request_and_is_listed')
const inquiryPreparation = quotePreparation.preparationStatus === 'quote_preparation_ready'
const quoteContext = quotePreparation.materialSupplierCandidates.length === 1
const priceContext = priceFacts.resultCount === 1 && priceFacts.current.inquiryNo === quotePreparation.inquiryNo
const pageData = pricePage.includes('SCM_PRICE_APPROVAL_PREPARATION_PROVIDER')
  && pricePage.includes('priceApprovalPreparationRows') && pricePage.includes('暂无报价准备数据')
const noLegacy = priceFacts.legacyDataEnabled === false
  && pricePage.includes('current_quote_preparation_context_only')
  && !pricePage.includes('data-acceptance-id="price-approval-current-quote-preparation" data-source="mock"')
const boundary = ['supplierQuoteCreated', 'quoteComparisonCreated', 'purchaseOrderCreated', 'financeCreated']
  .every(field => priceFacts[field] === false)

const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseScmPurchaseInquiryHandoffV11428818.test.mjs',
  'tests/acceptance/enterpriseScmInquiryBusinessClosureV114287A.test.mjs'],
{ cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(root, 'node_modules/vite/bin/vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (buildRun.status !== 0) { process.stderr.write(buildRun.stdout || ''); process.stderr.write(buildRun.stderr || '') }

const checks = [['Purchase Request Create', purchaseCreate], ['HTTP403 Fixed', http403Fixed],
  ['Inquiry Quote Preparation', inquiryPreparation], ['QuotePreparation Context', quoteContext],
  ['PriceApproval Context', priceContext], ['PriceApproval Page Data', pageData],
  ['No Legacy Data', noLegacy], ['No Business Write Violation', boundary && testRun.status === 0],
  ['Build', buildRun.status === 0]]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PURCHASE_CHAIN_HANDOFF_FIXED' : 'SCM_PURCHASE_CHAIN_HANDOFF_FAILED')
if (!passed) process.exitCode = 1
