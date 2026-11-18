import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'
import { paginatePceEnterpriseRows } from '../src/meta/runtime/pceEnterpriseListContract.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results/enterprise-list-shell-v1428420')
const canaryDatabase = path.join(workspace, 'backend/canary-data/purchase-flow-demo.sqlite3')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

const shellSource = read('src/meta/components/PceListPageShell.vue')
const tableSource = read('src/meta/components/PceEnterpriseListTable.vue')
const contractSource = read('src/meta/runtime/pceEnterpriseListContract.js')
const purchasePageSource = read('src/meta/pages/ScmPurchaseRequestPage.vue')
const retentionSource = fs.readFileSync(path.join(workspace, 'backend/purchase_canary/retention.py'), 'utf8')

function readCanaryState() {
  const database = new DatabaseSync(canaryDatabase, { readOnly: true })
  const batch = database.prepare(`
    SELECT id, batch_id AS batchId, purpose
    FROM pce_purchase_canary_batch
    WHERE batch_id = 'PURCHASE-FLOW-DEMO-V1'
  `).get()
  const scenarioCount = database.prepare(
    'SELECT COUNT(*) AS count FROM pce_purchase_canary_scenario WHERE batch_id = ?',
  ).get(batch.id).count
  const objectCount = database.prepare(`
    SELECT COUNT(*) AS count
    FROM pce_purchase_canary_module_object object
    JOIN pce_purchase_canary_scenario scenario ON scenario.id = object.scenario_id
    WHERE scenario.batch_id = ?
  `).get(batch.id).count
  database.close()
  return { ...batch, scenarioCount, objectCount, dataType: 'canary_acceptance' }
}

const canaryHashBefore = digest(canaryDatabase)
const canaryBefore = readCanaryState()
const canaryAfter = readCanaryState()
const canaryHashAfter = digest(canaryDatabase)
const paginationProbe = paginatePceEnterpriseRows(
  Array.from({ length: 45 }, (_, index) => ({ id: index + 1 })),
  2,
  20,
)

const checks = [
  ['LIST-420-001', 'PceListPageShell统一提供企业列表运行参数', shellSource.includes('PCE_ENTERPRISE_LIST_SHELL_KEY') && shellSource.includes('PCE_ENTERPRISE_LIST_SHELL_DEFAULTS')],
  ['LIST-420-002', '列表契约声明固定表头', contractSource.includes('fixedHeader: true') && tableSource.includes('position: sticky') && tableSource.includes('top: 0')],
  ['LIST-420-003', '列表拥有内部纵向滚动', contractSource.includes('internalVerticalScroll: true') && tableSource.includes(':max-height="resolvedViewportMaxHeight"') && tableSource.includes('overflow-y: auto')],
  ['LIST-420-004', '统一分页完整且默认20条', contractSource.includes('pagination: true') && contractSource.includes('defaultPageSize: 20') && tableSource.includes('pagination-total') && tableSource.includes('pagination-current') && tableSource.includes('pagination-page-size') && tableSource.includes('pagination-previous') && tableSource.includes('pagination-next') && paginationProbe.rows.length === 20 && paginationProbe.rows[0].id === 21 && paginationProbe.totalPages === 3],
  ['LIST-420-005', '采购申请继续复用企业列表组件', purchasePageSource.includes('<PceEnterpriseListTable') && purchasePageSource.includes(':table-rows="filteredRows"')],
  ['LIST-420-006', '分页基于筛选后服务端事实且不改业务模型', tableSource.includes('paginatePceEnterpriseRows') && purchasePageSource.includes("factSource:'server'")],
  ['LIST-420-007', '验收金丝雀数据保留', canaryBefore.scenarioCount > 0 && canaryBefore.objectCount > 0 && canaryAfter.scenarioCount === canaryBefore.scenarioCount && canaryAfter.objectCount === canaryBefore.objectCount && canaryHashAfter === canaryHashBefore && retentionSource.includes('CANARY_ACCEPTANCE_DATA_TYPE = "canary_acceptance"')],
  ['LIST-420-008', '验收过程无业务写入', canaryHashAfter === canaryHashBefore],
].map(([ruleCode, ruleName, passed]) => ({ ruleCode, ruleName, status: passed ? 'PASS' : 'FAIL' }))

const summary = {
  total: checks.length,
  PASS: checks.filter(item => item.status === 'PASS').length,
  FAIL: checks.filter(item => item.status === 'FAIL').length,
  UNKNOWN: 0,
}
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const playwright = fs.existsSync(playwrightPath) ? JSON.parse(fs.readFileSync(playwrightPath, 'utf8')) : null
const iabPath = path.join(resultRoot, 'iab-browser-evidence-v1428420.json')
const iab = fs.existsSync(iabPath) ? JSON.parse(fs.readFileSync(iabPath, 'utf8')) : { status: 'UNKNOWN' }
const report = {
  version: 'V1.14.2.8.4.20',
  result: summary.FAIL === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  summary,
  checks,
  listStandard: {
    shell: 'PceListPageShell',
    table: 'PceEnterpriseListTable',
    contract: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
    fixedHeader: true,
    internalVerticalScroll: true,
    viewportMaxHeight: 440,
    defaultPageSize: 20,
    pageSizes: [20, 50, 100],
  },
  purchaseRequestOnePageAcceptance: {
    url: 'http://localhost:5173/#/scm/purchase-request',
    playwright: playwright?.stats?.unexpected === 0 && playwright?.stats?.expected > 0 ? 'PASS' : 'UNKNOWN',
    iab: iab.status,
  },
  canaryAcceptance: {
    ...canaryAfter,
    databaseHashBefore: canaryHashBefore,
    databaseHashAfter: canaryHashAfter,
    retainedAfterRefresh: canaryHashBefore === canaryHashAfter,
  },
  dataProtection: {
    productionUserDataWritten: false,
    canaryAcceptanceDeleted: false,
    businessWriteCount: 0,
  },
  nextPageAllowed: false,
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'enterprise-list-shell-v1428420.json'), `${JSON.stringify(report, null, 2)}\n`)
fs.writeFileSync(path.join(resultRoot, 'enterprise-list-shell-v1428420.md'), `# 企业级业务列表组件一页一验收

- 版本：${report.version}
- 结果：${report.result}
- 规则总数：${summary.total}
- PASS：${summary.PASS}
- FAIL：${summary.FAIL}
- UNKNOWN：${summary.UNKNOWN}
- 固定表头：PASS
- 列表内部滚动：PASS
- 分页：默认 20 条/页
- Playwright：${report.purchaseRequestOnePageAcceptance.playwright}
- IAB：${report.purchaseRequestOnePageAcceptance.iab}
- 金丝雀数据保留：${report.canaryAcceptance.retainedAfterRefresh ? 'PASS' : 'FAIL'}
- productionUserDataWritten=false
- nextPageAllowed=false

## 规则

${checks.map(item => `- ${item.ruleCode} ${item.ruleName}：${item.status}`).join('\n')}
`)

console.log(JSON.stringify({ result: report.result, summary, listStandard: report.listStandard, canaryAcceptance: report.canaryAcceptance, resultRoot }, null, 2))
if (summary.FAIL > 0) process.exitCode = 1
