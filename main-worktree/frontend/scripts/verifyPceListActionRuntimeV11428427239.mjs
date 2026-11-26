import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createActionColumnWidthRuntime, getActionColumnWidth } from '../src/meta/runtime/tableActionColumnEngine.js'
import { createSchemaActionContracts } from '../src/meta/runtime/listActionColumnRuntime.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(root, '..')
const phase = process.argv.includes('--phase=automatic') ? 'automatic' : 'final'
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8')
const readRepo = (...parts) => fs.readFileSync(path.join(repo, ...parts), 'utf8')
const checks = []
const check = (code, passed, detail) => checks.push({ code, passed: Boolean(passed), detail })

const one = createSchemaActionContracts(['view'])
const two = createSchemaActionContracts(['view', 'edit'])
const four = createSchemaActionContracts(['view', 'edit', 'toggle-status', 'delete'])
const oneRuntime = createActionColumnWidthRuntime(one)
const twoRuntime = createActionColumnWidthRuntime(two)
const fourRuntime = createActionColumnWidthRuntime(four)

check('ACTION-COLUMN-WIDTH-001', oneRuntime.width >= 80 && oneRuntime.width <= 100
  && twoRuntime.width >= 120 && twoRuntime.width <= 160
  && fourRuntime.width > twoRuntime.width
  && getActionColumnWidth([]) >= 80, `1=${oneRuntime.width}px;2=${twoRuntime.width}px;4=${fourRuntime.width}px`)

const listRuntime = read('src', 'meta', 'runtime', 'listActionColumnRuntime.js')
const widthRuntime = read('src', 'meta', 'runtime', 'tableActionColumnEngine.js')
const table = read('src', 'meta', 'components', 'PceEnterpriseListTable.vue')
const registry = read('src', 'meta', 'master-data', 'masterDataRegistry.js')
const foundation = read('src', 'meta', 'components', 'FoundationMetadataList.vue')
const enterprise = read('src', 'meta', 'pages', 'EnterpriseMasterDataPage.vue')

check('LIST-ACTION-SOURCE-001', listRuntime.includes('createSchemaActionContracts')
  && listRuntime.includes("source: 'Action Contract'")
  && table.includes(':action-contracts') === false
  && table.includes('data-pce-action-source="Action Contract"')
  && foundation.includes(':action-contracts="actionContracts"')
  && enterprise.includes(':action-contracts="actionContracts"'), 'Metadata actionPolicy -> Action Contract -> table')

const targetSources = [foundation, enterprise,
  read('src', 'meta', 'pages', 'SupplierPriceAnalysisPage.vue'),
  read('src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')]
check('NO-HARDCODE-ACTION-WIDTH-001', targetSources.every(source => !/action-width\s*=/.test(source))
  && !foundation.includes('<template #actions') && !enterprise.includes('<template #actions'), '目标页无固定action-width或template动作')

check('METADATA-DRIVEN-LIST-001', registry.includes('MASTER_DATA_PAGE_ACTION_POLICIES')
  && registry.includes('readonlyMaster')
  && foundation.includes('metadata.columns')
  && foundation.includes('metadata.actionPolicy')
  && enterprise.includes('definition.columns')
  && enterprise.includes('definition.actionPolicy'), '列与动作均由masterDataRegistry驱动')

check('ACTION-RUNTIME-DIAGNOSTICS-001', widthRuntime.includes('ActionColumnWidthRuntime')
  && table.includes('data-pce-action-column-runtime')
  && table.includes('data-pce-action-column-width')
  && table.includes('data-pce-action-count'), 'DOM暴露Runtime、宽度与动作数量')

const governance = readRepo('docs', 'governance', 'PCE统一列表操作列智能宽度规范.md')
const implementation = readRepo('docs', 'governance', 'PCE统一列表操作列智能宽度Runtime实施报告.md')
check('GOVERNANCE-TRACE-001', governance.includes('ACTION-COLUMN-WIDTH-001')
  && implementation.includes('ListRuntimeCapabilityInventory'), '规范与能力清单存在')

if (phase === 'final') {
  const evidenceDir = path.join(root, 'test-results', 'V1.14.2.8.4.27.2.39')
  const screenshots = fs.existsSync(evidenceDir)
    ? fs.readdirSync(evidenceDir).filter(name => name.endsWith('.png')) : []
  const browserReport = readRepo('docs', 'governance', 'PCE统一列表操作列智能宽度真实运行验收报告.md')
  check('REAL-BROWSER-EVIDENCE-001', screenshots.length >= 24
    && browserReport.includes('Browser Human Acceptance: PASS')
    && browserReport.includes('1440x900') && browserReport.includes('375x812'), `${screenshots.length} screenshots`)
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS PCE_LIST_ACTION_RUNTIME_STANDARD ${phase}`)
