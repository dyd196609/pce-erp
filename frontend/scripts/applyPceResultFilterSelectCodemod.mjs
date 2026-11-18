import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const mappings = {
  'PurchaseReceivePage.vue': { advancedFilters: 'receives' },
  'QmsPage.vue': { advancedFilters: 'inspections' },
  'PayablePreparePage.vue': { filters: 'rows' },
  'PayableCheckPage.vue': { advancedFilters: 'rows' },
  'PayableCheckPage.vue': { filters: 'rows' },
  'SupplierSettlementPage.vue': { filters: 'rows' },
  'InvoicePreparePage.vue': { filters: 'sourceRows' },
  'AccountPayableDraftPage.vue': { filters: 'rows' },
  'AccountPayableConfirmPage.vue': { filters: 'sourceRows' },
  'PaymentApplicationPage.vue': { filters: 'sourceRows' },
  'PaymentInstructionPreparePage.vue': { filterState: 'rows' },
  'PaymentExecutionPreparePage.vue': { filterState: 'paymentExecutionListRows' },
  'SupplierPaymentDraftPage.vue': { sourceFilters: 'sourceRows', draftFilters: 'draftRows' },
  'PaymentOrderPreparePage.vue': { sourceFilters: 'sourceRows', prepareFilters: 'prepareRows' },
  'PaymentExecutionPage.vue': { sourceFilters: 'sortedSources', filters: 'sortedExecutions' },
  'PaymentRecordReviewPage.vue': { sourceFilters: 'sortedSources', filters: 'sortedReviews' },
  'PaymentVoucherReviewPage.vue': { sourceFilters: 'sortedSources' },
}

const keepText = /remark|reason|note|keyword|description|comment/i
let changedCount = 0

for (const [file, modelRows] of Object.entries(mappings)) {
  const filePath = path.join(root, 'src', 'meta', 'pages', file)
  let source = fs.readFileSync(filePath, 'utf8')
  let replacements = 0

  const replaceControl = (full, model, key, attributes = '') => {
    if (!modelRows[model] || keepText.test(key)) return full
    if (/\blist=|type="(?:date|number|daterange)"/.test(attributes)) return full
    replacements += 1
    return `<PceResultFilterSelect v-model="${model}.${key}" :rows="${modelRows[model]}" :fields="['${key}']" />`
  }

  source = source.replace(/<el-input\b([^>]*\bv-model="(advancedFilters|filters|filterState|sourceFilters|draftFilters|prepareFilters)\.([^"]+)"[^>]*)\/>/g, (full, attributes, model, key) => replaceControl(full, model, key, attributes))
  source = source.replace(/<input\b([^>]*\bv-model="(advancedFilters|filters|filterState|sourceFilters|draftFilters|prepareFilters)\.([^"]+)"[^>]*)\/>/g, (full, attributes, model, key) => replaceControl(full, model, key, attributes))

  if (!replacements) continue
  if (!source.includes("import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'")) {
    source = source.replace(/(import \{[^\n]+\} from 'vue'\r?\n)/, `$1import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'\n`)
  }
  fs.writeFileSync(filePath, source, 'utf8')
  changedCount += replacements
  console.log(`${file}: ${replacements}`)
}

console.log(`PceResultFilterSelect replacements: ${changedCount}`)
