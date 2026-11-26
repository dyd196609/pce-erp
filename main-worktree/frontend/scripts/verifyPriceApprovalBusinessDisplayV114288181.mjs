import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createPriceApprovalPreparationProvider }
  from '../src/meta/providers/priceApprovalPreparationProvider.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'src/meta/pages/ScmPage.vue'), 'utf8')
const start = source.indexOf('data-acceptance-id="price-approval-current-quote-preparation"')
const end = source.indexOf('<section v-else-if="activeConfig && pageMode === \'list\'"', start)
const businessRegion = source.slice(start, end)
const visibleText = businessRegion.replace(/<[^>]+>/g, ' ')

const quotePreparation = Object.freeze({ objectType: 'QuotePreparationContext',
  quotePreparationNo: 'QPC-PI-DISPLAY-001', inquiryNo: 'PI-DISPLAY-001', sourceRequestNo: 'PR-DISPLAY-001',
  preparationStatus: 'quote_preparation_ready',
  materialLines: [{ materialCode: 'MAT-A', materialName: '物料A', quantity: 1 }],
  materialSupplierCandidates: [{ materialCode: 'MAT-A', materialName: '物料A', supplierCode: 'SUP-A',
    supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' }] })
const facts = createPriceApprovalPreparationProvider({ quoteProvider: {
  load: () => ({ records: [quotePreparation], recordCount: 1 }),
} }).load()

const priceApprovalData = start >= 0 && businessRegion.includes('priceApprovalPreparationRows')
  && businessRegion.includes('询价编号') && businessRegion.includes('供应商候选')
const indexColumn = businessRegion.includes('<el-table-column type="index" label="序号"')
const chineseStatus = source.includes("quote_preparation_ready: '已进入供应商报价准备'")
  && source.includes("enabled: '启用'") && source.includes("active: '有效'")
  && businessRegion.includes('prop="supplierStatusLabel"')
  && businessRegion.includes('prop="preparationStatusLabel"')
const noTechnicalEnglish = !['Context', 'Runtime', 'Provider', 'Object']
  .some(word => visibleText.includes(word))
  && businessRegion.includes('label="数据来源">报价准备上下文')
  && !businessRegion.includes('>{{ priceApprovalPreparationFacts.current.preparationStatus }}')
const contextIntegrity = facts.resultCount === 1 && facts.current.inquiryNo === 'PI-DISPLAY-001'
  && facts.current.materialLines.length === 1 && facts.current.materialSupplierCandidates.length === 1
  && facts.current.preparationStatus === 'quote_preparation_ready'
  && facts.legacyDataEnabled === false

const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseScmPurchaseInquiryHandoffV11428818.test.mjs'],
{ cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (testRun.status !== 0) { process.stderr.write(testRun.stdout || ''); process.stderr.write(testRun.stderr || '') }
const vite = path.join(root, 'node_modules/vite/bin/vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (buildRun.status !== 0) { process.stderr.write(buildRun.stdout || ''); process.stderr.write(buildRun.stderr || '') }

const checks = [['PriceApproval Data', priceApprovalData], ['Index Column', indexColumn],
  ['Chinese Status', chineseStatus], ['No Technical English', noTechnicalEnglish],
  ['Context Integrity', contextIntegrity && testRun.status === 0], ['Build', buildRun.status === 0]]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value)
console.log(passed ? 'SCM_PRICE_APPROVAL_BUSINESS_DISPLAY_READY'
  : 'SCM_PRICE_APPROVAL_BUSINESS_DISPLAY_FAILED')
if (!passed) process.exitCode = 1
