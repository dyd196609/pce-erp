import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { listScmNodePageMappingsV11428103,
  validateScmNodePageGovernanceV11428103 } from '../src/meta/process/scmNodePageGovernanceV11428103.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')
const governanceFiles = ['PCE-ERP开发治理总规范.md', '节点开发模板.md', '页面开发模板.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(workspaceRoot, 'docs/governance', name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const governanceResult = validateScmNodePageGovernanceV11428103()
const mappings = listScmNodePageMappingsV11428103()
const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT').slice(0, 9)
const routerSource = readFrontend('src/router/index.js')
const caseLibrary = readWorkspace('docs/governance/问题案例库.md')
const nodePageRule = readWorkspace('docs/governance/NODE-PAGE-001节点页面唯一映射规范.md')
const pages = {
  inquiryPreparation: readFrontend('src/meta/pages/ScmInquiryPreparationPage.vue'),
  purchaseInquiry: readFrontend('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
  supplierRecommendation: readFrontend('src/meta/pages/ScmSupplierRecommendationPage.vue'),
  purchaseOrderGate: readFrontend('src/meta/pages/ScmPurchaseOrderGatePage.vue'),
}

const nodePage001 = governanceResult.nodePage001 && nodePageRule.includes('NODE-PAGE-001')
  && caseLibrary.includes('CASE-SCM-017')
const pageIdentity = mappings.every(mapping => {
  const identity = resolveScmPageIdentity(mapping.pageContract.route)
  return identity && ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject']
    .every(field => identity[field] === mapping.pageContract[field])
})
const navigation = processNodes.length === mappings.length && processNodes.every((node, index) =>
  node.nodeCode === mappings[index].nodeCode && node.pageCode === mappings[index].pageContract.pageCode
  && node.pageRoute === mappings[index].pageContract.route && node.allowNewTab === true)
const process011 = governanceResult.process011 && pageIdentity && navigation
  && routerSource.includes("path: 'scm/inquiry-preparations'")
  && routerSource.includes("path: 'scm/supplier-recommendations'")
  && routerSource.includes("path: 'scm/purchase-order-gate'")
  && routerSource.includes("ScmPurchaseInquiryNodePage.vue")
const inquiryPreparationPage = pages.inquiryPreparation.includes('data-page-code="inquiry-preparation"')
  && ['询价准备编号', '来源采购申请', '供应商候选', 'START_PURCHASE_INQUIRY'].every(value => pages.inquiryPreparation.includes(value))
const purchaseInquiryPage = pages.purchaseInquiry.includes('data-page-code="purchase-inquiry"')
  && ['询价编号', '物料与供应商决策', '准备供应商报价'].every(value => pages.purchaseInquiry.includes(value))
  && ['supplier-recommendation-runtime', 'purchase-order-gate-runtime', 'pending-inquiry-preparations']
    .every(value => !pages.purchaseInquiry.includes(value))
const supplierRecommendationPage = pages.supplierRecommendation.includes('data-page-code="supplier-recommendation"')
  && ['比较证据', '推荐候选', '推荐理由'].every(value => pages.supplierRecommendation.includes(value))
  && !pages.supplierRecommendation.includes('createPurchaseOrder')
const purchaseOrderGatePage = pages.purchaseOrderGate.includes('data-page-code="purchase-order-gate"')
  && ['准入编号', '准入检查', '采购订单'].every(value => pages.purchaseOrderGate.includes(value))
  && !pages.purchaseOrderGate.includes('createPurchaseOrder')
const acceptanceFiles = ['PAGE-INQUIRY-PREPARATION.md', 'PAGE-PURCHASE-INQUIRY.md',
  'PAGE-SUPPLIER-RECOMMENDATION.md', 'PAGE-PURCHASE-ORDER-GATE.md']
const process009 = acceptanceFiles.every(name => {
  const file = path.join(workspaceRoot, 'docs/acceptance', name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').includes('人工验收结果：PASS')
})

const tests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseScmNodePageGovernanceV11428103.test.mjs',
  'tests/acceptance/enterpriseScmProcessCenterNavigationV11428101.test.mjs',
  'tests/acceptance/processNodeNavigationV1142819.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const golden = spawnSync(process.execPath, ['scripts/verifyScmPurchaseGoldenPathV114288.mjs'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const regression = tests.status === 0 && golden.status === 0
  && golden.stdout.includes('SCM_PURCHASE_GOLDEN_PATH_STABILIZED')
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
if (tests.status !== 0) process.stderr.write(`${tests.stdout || ''}${tests.stderr || ''}`)
if (golden.status !== 0) process.stderr.write(`${golden.stdout || ''}${golden.stderr || ''}`)
if (build.status !== 0) process.stderr.write(`${build.stdout || ''}${build.stderr || ''}`)

const checks = [
  ['Governance Files Loaded', governanceLoaded], ['NODE-PAGE-001', nodePage001],
  ['PROCESS-011', process011], ['Inquiry Preparation Page', inquiryPreparationPage],
  ['Purchase Inquiry Page', purchaseInquiryPage], ['Supplier Recommendation Page', supplierRecommendationPage],
  ['Purchase Order Gate Page', purchaseOrderGatePage], ['Page Identity', pageIdentity],
  ['Navigation', navigation], ['PROCESS-009', process009], ['Regression', regression],
  ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('未通过项清单：')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_NODE_PAGE_GOVERNANCE_ISSUES_FOUND' : 'SCM_NODE_PAGE_GOVERNANCE_READY')
if (failures.length) process.exitCode = 1
