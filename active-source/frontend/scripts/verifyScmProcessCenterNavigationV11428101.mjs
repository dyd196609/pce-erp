import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import { validateScmPurchaseProcessCenterRegistry } from '../src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const governanceFiles = ['PCE-ERP开发治理总规范.md', '节点开发模板.md', '页面开发模板.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(workspaceRoot, 'docs', 'governance', name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const primary = nodes.slice(0, 12)
const requiredOrder = ['采购申请', '采购审批', '询价准备', '采购询价', '供应商报价', '报价比较',
  '采购核价', '供应商推荐', '采购订单准入', '采购订单', '收货', '来料检验']
const registryValidation = validateScmPurchaseProcessCenterRegistry()
const routerSource = readFrontend('src/router/index.js')
const centerSource = readFrontend('src/meta/pages/EnterpriseOSPage.vue')
const componentSource = readFrontend('src/meta/components/ProcessNodeNavigation.vue')
const navigationSource = readFrontend('src/meta/process/scmProcessNavigationContract.js')
const acceptancePath = path.join(workspaceRoot, 'docs', 'acceptance', 'SCM-PROCESS-CENTER-NAVIGATION.md')

const nodeRegistry = registryValidation.valid && nodes.length === 22 && nodes.every((node, index) =>
  node.nodeCode && node.nodeName && node.pageRoute && node.acceptanceProfile
  && node.previousNode === (index ? nodes[index - 1].nodeCode : null)
  && node.nextNode === (index < nodes.length - 1 ? nodes[index + 1].nodeCode : null))
const processOrder = primary.map(node => node.nodeName).join('>') === requiredOrder.join('>')
const pageMapping = routerSource.includes("path: 'scm/supplier-quotes'")
  && routerSource.includes("path: 'scm/quote-comparisons'")
  && routerSource.includes("path: 'scm/price-approval'")
  && nodes.find(node => node.nodeCode === 'supplier-quote')?.pageRoute === '/scm/supplier-quotes'
  && nodes.find(node => node.nodeCode === 'quote-comparison')?.pageRoute === '/scm/quote-comparisons'
  && nodes.find(node => node.nodeCode === 'price-approval')?.pageRoute === '/scm/price-approval'
const supplierQuoteNode = Object.entries({ nodeCode: 'supplier-quote', nodeName: '供应商报价',
  previousNode: 'purchase-inquiry', nextNode: 'quote-comparison', pageRoute: '/scm/supplier-quotes',
  acceptanceProfile: 'supplierQuoteAcceptanceProfileV114289' }).every(([field, value]) =>
  nodes.find(node => node.nodeCode === 'supplier-quote')?.[field] === value)
const quoteComparisonNode = Object.entries({ nodeCode: 'quote-comparison', nodeName: '报价比较',
  previousNode: 'supplier-quote', nextNode: 'price-approval', pageRoute: '/scm/quote-comparisons',
  acceptanceProfile: 'quoteComparisonAcceptanceProfileV1142810' }).every(([field, value]) =>
  nodes.find(node => node.nodeCode === 'quote-comparison')?.[field] === value)
const navigation = centerSource.includes('scmPurchaseProcessNodes')
  && centerSource.includes('statusDescription')
  && componentSource.includes('data-process-node-action="view-page"')
  && componentSource.includes('data-process-node-action="new-tab"')
  && navigationSource.includes('SCM_PURCHASE_PROCESS_CENTER_NODES')
  && nodes.every(node => node.allowNewTab === true)
const process009 = fs.existsSync(acceptancePath)
  && fs.readFileSync(acceptancePath, 'utf8').includes('- 结果：PASS')

const tests = spawnSync(process.execPath, ['--test',
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
  ['Governance Files Loaded', governanceLoaded], ['Node Registry', nodeRegistry],
  ['Process Order', processOrder], ['Page Mapping', pageMapping],
  ['SupplierQuote Node', supplierQuoteNode], ['QuoteComparison Node', quoteComparisonNode],
  ['Navigation', navigation], ['PROCESS-009', process009], ['Regression', regression],
  ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('未通过项清单：')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'SCM_PROCESS_CENTER_NAVIGATION_SYNC_ISSUES_FOUND'
  : 'SCM_PROCESS_CENTER_NAVIGATION_SYNC_READY')
if (failures.length) process.exitCode = 1
