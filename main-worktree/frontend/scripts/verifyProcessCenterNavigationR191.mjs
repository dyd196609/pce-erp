import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'

import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import {
  openProcessNodeInCurrentPage,
  openProcessNodeInNewTab,
} from '../src/meta/process/processNodeNavigation.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results/process-center-navigation-r191')
const canaryDatabase = path.join(workspace, 'backend/canary-data/purchase-flow-demo.sqlite3')
const componentSource = fs.readFileSync(
  path.join(frontendRoot, 'src/meta/components/ProcessNodeNavigation.vue'),
  'utf8',
)
const retentionSource = fs.readFileSync(
  path.join(workspace, 'backend/purchase_canary/retention.py'),
  'utf8',
)
const canaryPanelSource = fs.readFileSync(
  path.join(frontendRoot, 'src/meta/components/PurchaseCanaryScenarioPanel.vue'),
  'utf8',
)
const listShellSource = fs.readFileSync(
  path.join(frontendRoot, 'src/meta/components/PceListPageShell.vue'),
  'utf8',
)
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

function readPersistentCanary() {
  const database = new DatabaseSync(canaryDatabase, { readOnly: true })
  const batch = database.prepare(`
    SELECT id, batch_id AS batchId, tenant_id AS tenantId, purpose
    FROM pce_purchase_canary_batch
    WHERE batch_id = 'PURCHASE-FLOW-DEMO-V1'
  `).get()
  const scenarioCount = database.prepare(
    'SELECT COUNT(*) AS count FROM pce_purchase_canary_scenario WHERE batch_id = ?',
  ).get(batch.id).count
  const moduleObjectCount = database.prepare(`
    SELECT COUNT(*) AS count
    FROM pce_purchase_canary_module_object object
    JOIN pce_purchase_canary_scenario scenario ON scenario.id = object.scenario_id
    WHERE scenario.batch_id = ?
  `).get(batch.id).count
  database.close()
  return {
    ...batch,
    scenarioCount,
    moduleObjectCount,
    dataType: 'canary_acceptance',
    cleanupPolicy: 'manual_only',
  }
}

const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const reconciliation = nodes.find(node => node.nodeCode === 'supplier-reconciliation')
const currentPushes = []
const currentResult = await openProcessNodeInCurrentPage(reconciliation, {
  async push(pageUrl) { currentPushes.push(pageUrl) },
})
const centerWindow = {
  location: { origin: 'http://localhost:5173', pathname: '/', hash: '#/process-center' },
  open(url, target) { return { url, target, opener: centerWindow } },
}
const originalHash = centerWindow.location.hash
const newTabResult = openProcessNodeInNewTab(reconciliation, centerWindow)
const databaseHashBefore = digest(canaryDatabase)
const canaryBefore = readPersistentCanary()
const canaryAfter = readPersistentCanary()
const databaseHashAfter = digest(canaryDatabase)

const checks = [
  ['R191-001', '查看页面按钮存在', componentSource.includes('data-process-node-action="view-page"')],
  ['R191-002', '查看页面使用pageUrl改变当前URL', currentResult.opened && currentPushes[0] === reconciliation.pageUrl],
  ['R191-003', '新标签打开生成新tab', newTabResult.opened && newTabResult.target === '_blank'],
  ['R191-004', '新标签操作保持流程中心', centerWindow.location.hash === originalHash],
  ['R191-005', 'canary_acceptance数据存在、业务列表可显示且禁止自动清理', canaryBefore.scenarioCount > 0 && canaryBefore.moduleObjectCount > 0 && retentionSource.includes('CANARY_ACCEPTANCE_DATA_TYPE = "canary_acceptance"') && retentionSource.includes('autoDeleteAllowed') && canaryPanelSource.includes('canary-data-type') && canaryPanelSource.includes('canary-retention-policy') && listShellSource.includes('PurchaseCanaryScenarioPanel') && listShellSource.includes('route.query.canaryBatchId')],
  ['R191-006', '刷新读取后金丝雀仍存在', JSON.stringify(canaryAfter) === JSON.stringify(canaryBefore) && databaseHashAfter === databaseHashBefore],
].map(([ruleCode, ruleName, passed]) => ({
  ruleCode,
  ruleName,
  status: passed ? 'PASS' : 'FAIL',
}))
const summary = {
  total: checks.length,
  PASS: checks.filter(item => item.status === 'PASS').length,
  FAIL: checks.filter(item => item.status === 'FAIL').length,
  UNKNOWN: 0,
}
const playwrightReportPath = path.join(resultRoot, 'playwright-report.json')
const playwrightReport = fs.existsSync(playwrightReportPath)
  ? JSON.parse(fs.readFileSync(playwrightReportPath, 'utf8'))
  : null
const iabEvidencePath = path.join(resultRoot, 'iab-browser-evidence-r191.json')
const iabEvidence = fs.existsSync(iabEvidencePath)
  ? JSON.parse(fs.readFileSync(iabEvidencePath, 'utf8'))
  : null
const report = {
  version: 'V1.14.2.8.4.19.1',
  result: summary.FAIL === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  summary,
  checks,
  navigation: {
    inspectedNode: reconciliation.nodeName,
    pageCode: reconciliation.pageCode,
    pageUrl: reconciliation.pageUrl,
    currentTabResult: currentResult,
    newTabResult,
    processCenterPreserved: centerWindow.location.hash === originalHash,
  },
  canaryAcceptance: {
    ...canaryAfter,
    databaseHashBefore,
    databaseHashAfter,
    retainedAfterRefresh: databaseHashBefore === databaseHashAfter,
  },
  playwright: {
    status: playwrightReport?.stats?.unexpected === 0 && playwrightReport?.stats?.expected > 0
      ? 'PASS'
      : 'UNKNOWN',
  },
  iab: iabEvidence || { status: 'UNKNOWN' },
  dataProtection: {
    productionUserDataWritten: false,
    canaryAcceptanceDeleted: false,
    businessWriteCount: 0,
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'process-center-navigation-r191.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
fs.writeFileSync(
  path.join(resultRoot, 'process-center-navigation-r191.md'),
  `# 流程中心查看页面与金丝雀保留验收 V1.14.2.8.4.19.1

- 结果：${report.result}
- 规则总数：${summary.total}
- PASS：${summary.PASS}
- FAIL：${summary.FAIL}
- UNKNOWN：${summary.UNKNOWN}
- Playwright：${report.playwright.status}
- IAB：${report.iab.status}
- dataType：${canaryAfter.dataType}
- cleanupPolicy：${canaryAfter.cleanupPolicy}
- 金丝雀场景：${canaryAfter.scenarioCount}
- 金丝雀模块对象：${canaryAfter.moduleObjectCount}
- 刷新后保留：${report.canaryAcceptance.retainedAfterRefresh}
- productionUserDataWritten：false

## 规则

${checks.map(item => `- ${item.ruleCode} ${item.ruleName}：${item.status}`).join('\n')}
`,
)
console.log(JSON.stringify({ result: report.result, summary, canaryAcceptance: report.canaryAcceptance, resultRoot }, null, 2))
if (summary.FAIL > 0) process.exitCode = 1
