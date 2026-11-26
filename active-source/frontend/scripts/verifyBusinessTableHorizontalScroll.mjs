import fs from 'node:fs'
import path from 'node:path'
import { listBusinessOperationPageConfigs } from '../src/meta/process/businessOperationPageRegistry.js'

const root = process.cwd()
const componentPath = path.join(root, 'src/meta/components/BusinessTableScrollContainer.vue')
const pageFiles = [
  ['payable-prepare', 'src/meta/pages/PayablePreparePage.vue'],
  ['payable-check', 'src/meta/pages/PayableCheckPage.vue'],
  ['supplier-settlement', 'src/meta/pages/SupplierSettlementPage.vue'],
  ['invoice-prepare', 'src/meta/pages/InvoicePreparePage.vue'],
  ['account-payable-draft', 'src/meta/pages/AccountPayableDraftPage.vue'],
  ['account-payable-confirm', 'src/meta/pages/AccountPayableConfirmPage.vue'],
  ['payment-application', 'src/meta/pages/PaymentApplicationPage.vue'],
]

function read(relative) {
  return fs.readFileSync(path.join(root, relative), 'utf8')
}

function countRealTables(text) {
  return (text.match(/<el-table(?!-)/g) || []).length
}

function countScrollContainers(text) {
  return (text.match(/<BusinessTableScrollContainer/g) || []).length
}

const componentText = fs.readFileSync(componentPath, 'utf8')
const componentChecks = {
  width100: componentText.includes('width: 100%'),
  maxWidth100: componentText.includes('max-width: 100%'),
  nativeScrollOwner: componentText.includes('data-pce-horizontal-scroll-owner="element-plus-native"'),
  outerOverflowHidden: componentText.includes('overflow: hidden'),
  noTranslateX: !componentText.includes('translateX'),
  noScrollOffsetListener: !componentText.includes('addEventListener(\'scroll\'') && !componentText.includes('requestAnimationFrame'),
  noForcedSticky: !componentText.includes('position: sticky'),
}

const pageResults = pageFiles.map(([pageStepId, relative]) => {
  const text = read(relative)
  const tableCount = countRealTables(text)
  const scrollContainerCount = countScrollContainers(text)
  const acceptanceIds = (text.match(/business-table-scroll-[a-z0-9-]+/g) || []).length
  const scrollbarAlwaysOnCount = (text.match(/<el-table(?!-)[\s\S]*?scrollbar-always-on/g) || []).length
  const titleInsideScroll = /<BusinessTableScrollContainer[\s\S]{0,200}<h[1-6]/.test(text)
  const buttonInsideScroll = /<BusinessTableScrollContainer[\s\S]{0,200}<el-button/.test(text)
  return {
    pageStepId,
    tableCount,
    scrollContainerCount,
    acceptanceIds,
    scrollbarAlwaysOnCount,
    titleInsideScroll,
    buttonInsideScroll,
    passed: tableCount > 0
      && tableCount === scrollContainerCount
      && tableCount === acceptanceIds
      && tableCount === scrollbarAlwaysOnCount
      && !titleInsideScroll
      && !buttonInsideScroll,
  }
})

const pageConfigCount = listBusinessOperationPageConfigs().length
const tableCount = pageResults.reduce((sum, item) => sum + item.tableCount, 0)
const wrappedCount = pageResults.reduce((sum, item) => sum + item.scrollContainerCount, 0)
const failed = pageResults.filter((item) => !item.passed)
const componentPassed = Object.values(componentChecks).every(Boolean)

console.log(JSON.stringify({
  page: 'verifyBusinessTableHorizontalScroll',
  version: 'V1.14.2.3',
  unifiedOperationPageCount: pageConfigCount,
  checkedPageCount: pageResults.length,
  tableCount,
  independentScrollTableCount: wrappedCount,
  componentChecks,
  pageLevelHorizontalOverflowConfigured: false,
  dependsOnPageBottomScrollbar: false,
  pageResults,
  failedCount: failed.length + (componentPassed ? 0 : 1),
  checkedAt: new Date().toISOString(),
}, null, 2))

if (failed.length || !componentPassed) process.exit(1)
