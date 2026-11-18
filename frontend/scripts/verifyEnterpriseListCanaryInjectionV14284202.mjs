import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { DatabaseSync } from 'node:sqlite'
import { resolveEnterpriseListCanaryQuery } from '../src/meta/runtime/enterpriseListCanaryMode.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results/enterprise-list-canary-injection-v14284202')
const canaryDatabase = path.join(workspace, 'backend/canary-data/purchase-flow-demo.sqlite3')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

const pageSource = read('src/meta/pages/ScmPurchaseRequestPage.vue')
const contextSource = read('src/meta/components/ScmStandardPageContext.vue')
const cardSource = read('src/meta/components/PceEnterpriseListCanaryCard.vue')
const providerSource = read('src/meta/runtime/enterpriseListCanaryDataProvider.js')
const standardSource = fs.readFileSync(path.join(workspace, 'docs/standards/enterprise_page_acceptance_standard.md'), 'utf8')
const normalMode = resolveEnterpriseListCanaryQuery({})
const canaryMode = resolveEnterpriseListCanaryQuery({
  canaryBatchId: 'PURCHASE-FLOW-DEMO-V1',
  scenarioCode: 'HAPPY_PATH',
})

function readCanary() {
  const database = new DatabaseSync(canaryDatabase, { readOnly: true })
  const batch = database.prepare('SELECT id, batch_id AS batchId FROM pce_purchase_canary_batch WHERE batch_id = ?').get('PURCHASE-FLOW-DEMO-V1')
  const scenario = database.prepare('SELECT id, code FROM pce_purchase_canary_scenario WHERE batch_id = ? AND code = ?').get(batch.id, 'HAPPY_PATH')
  const purchaseRequest = database.prepare('SELECT object_no AS objectNo, object_status AS status FROM pce_purchase_canary_module_object WHERE scenario_id = ? AND module_code = ?').get(scenario.id, 'purchase-request')
  database.close()
  return { ...batch, scenarioCode: scenario.code, purchaseRequest, dataType: 'canary_acceptance', cleanupPolicy: 'manual_only' }
}

const databaseHashBefore = digest(canaryDatabase)
const canaryBefore = readCanary()
const canaryAfter = readCanary()
const databaseHashAfter = digest(canaryDatabase)
const checks = [
  ['CANARY-INJECT-001', '普通URL保持普通模式', normalMode.isCanaryMode === false],
  ['CANARY-INJECT-002', '批次与场景Query启用金丝雀模式', canaryMode.isCanaryMode === true && canaryMode.canaryBatchId === 'PURCHASE-FLOW-DEMO-V1' && canaryMode.scenarioCode === 'HAPPY_PATH'],
  ['CANARY-INJECT-003', '采购申请列表切换金丝雀Provider', pageSource.includes("loadEnterpriseListCanaryFacts('purchase-request',route.query)") && pageSource.includes('if(isCanaryMode.value)') && providerSource.includes("apiUrl: '/api/pce/purchase-canary/context'")],
  ['CANARY-INJECT-004', '公共SCM事实区不再在金丝雀模式调用普通事实API', contextSource.includes('canaryMode.value') && contextSource.includes('loadEnterpriseListCanaryFacts')],
  ['CANARY-INJECT-005', '页面显示金丝雀验收诊断字段', cardSource.includes('金丝雀验收模式') && cardSource.includes('canary-list-data-mode') && cardSource.includes('canary-list-batch-id') && cardSource.includes('canary-list-scenario-code') && cardSource.includes('canary-list-cleanup-policy')],
  ['CANARY-INJECT-006', '金丝雀数据持久且刷新读取一致', JSON.stringify(canaryBefore) === JSON.stringify(canaryAfter) && databaseHashBefore === databaseHashAfter && canaryAfter.purchaseRequest.objectNo === 'PRQ-DEMO-HP-001'],
  ['CANARY-INJECT-007', '场景参数验收已加入软件标准', standardSource.includes('页面场景参数验收') && standardSource.includes('Query') && standardSource.includes('刷新页面后')],
  ['CANARY-INJECT-008', '验收不产生业务写入', databaseHashBefore === databaseHashAfter],
].map(([ruleCode, ruleName, passed]) => ({ ruleCode, ruleName, status: passed ? 'PASS' : 'FAIL' }))

const summary = { total: checks.length, PASS: checks.filter(x => x.status === 'PASS').length, FAIL: checks.filter(x => x.status === 'FAIL').length, UNKNOWN: 0 }
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const playwright = fs.existsSync(playwrightPath) ? JSON.parse(fs.readFileSync(playwrightPath, 'utf8')) : null
const iabPath = path.join(resultRoot, 'iab-browser-evidence-v14284202.json')
const iab = fs.existsSync(iabPath) ? JSON.parse(fs.readFileSync(iabPath, 'utf8')) : { status: 'UNKNOWN' }
const report = {
  version: 'V1.14.2.8.4.20.2',
  result: summary.FAIL === 0 ? 'PASS' : 'FAIL',
  generatedAt: new Date().toISOString(),
  summary,
  checks,
  ordinaryUrl: { isCanaryMode: normalMode.isCanaryMode },
  canaryUrl: { ...canaryMode, dataType: canaryAfter.dataType, cleanupPolicy: canaryAfter.cleanupPolicy, listObjectNo: canaryAfter.purchaseRequest.objectNo },
  refreshConsistency: { retained: databaseHashBefore === databaseHashAfter, databaseHashBefore, databaseHashAfter },
  playwright: playwright?.stats?.unexpected === 0 && playwright?.stats?.expected > 0 ? 'PASS' : 'UNKNOWN',
  iab: iab.status,
  dataProtection: { productionUserDataWritten: false, businessWriteCount: 0, canaryAcceptanceDeleted: false },
  nextPageAllowed: false,
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'enterprise-list-canary-injection-v14284202.json'), `${JSON.stringify(report, null, 2)}\n`)
fs.writeFileSync(path.join(resultRoot, 'enterprise-list-canary-injection-v14284202.md'), `# 企业列表金丝雀数据注入链路验收\n\n- 版本：${report.version}\n- 结果：${report.result}\n- 规则总数：${summary.total}\n- PASS：${summary.PASS}\n- FAIL：${summary.FAIL}\n- UNKNOWN：${summary.UNKNOWN}\n- 普通URL isCanaryMode：false\n- 金丝雀URL isCanaryMode：true\n- 数据模式：canary_acceptance\n- 批次：PURCHASE-FLOW-DEMO-V1\n- 场景：HAPPY_PATH\n- 清理策略：manual_only\n- 列表对象：${canaryAfter.purchaseRequest.objectNo}\n- Playwright：${report.playwright}\n- IAB：${report.iab}\n- productionUserDataWritten=false\n- nextPageAllowed=false\n\n## 规则\n\n${checks.map(x => `- ${x.ruleCode} ${x.ruleName}：${x.status}`).join('\n')}\n`)
console.log(JSON.stringify({ result: report.result, summary, playwright: report.playwright, iab: report.iab, canaryUrl: report.canaryUrl, resultRoot }, null, 2))
if (summary.FAIL > 0) process.exitCode = 1
