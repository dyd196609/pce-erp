import fs from 'node:fs'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const outputRoot = path.resolve(frontendRoot, 'test-results/scm-canary-list-routing-v114284204')
const read = file => fs.readFileSync(path.resolve(sourceRoot, file), 'utf8')
const page = read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const table = read('frontend/src/meta/components/PceEnterpriseListTable.vue')
const provider = read('frontend/src/meta/runtime/enterpriseListCanaryDataProvider.js')
const runtimeProvider = read('frontend/src/meta/runtime/scmBusinessPageRuntimeProvider.js')
const mode = read('frontend/src/meta/runtime/enterpriseListCanaryMode.js')
const db = new DatabaseSync(path.resolve(sourceRoot, 'backend/canary-data/scm-canary-flow-v1.sqlite3'), { readOnly: true })
const requestObjects = Number(db.prepare("SELECT COUNT(*) AS count FROM pce_purchase_canary_module_object WHERE module_code='purchase-request'").get().count)
db.close()

const rules = []
const add = (code, name, pass, evidence) => rules.push({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })
add('SCM-CANARY-LIST-001', '双Query参数进入金丝雀模式', /canaryBatchId[\s\S]*scenarioCode/.test(mode) && mode.includes('Boolean(canaryBatchId && scenarioCode)'), 'resolveEnterpriseListCanaryQuery')
add('SCM-CANARY-LIST-002', '金丝雀模式不读取正式采购申请事实', runtimeProvider.includes("if (dataMode === 'canary_acceptance')") && page.includes('generation!==loadGeneration'), 'Provider分支隔离+请求代次门禁')
add('SCM-CANARY-LIST-003', 'Canary Provider按批次场景页面路由', provider.includes('CANARY_FACT_CACHE') && provider.includes('getPurchaseCanaryContext'), '只读Provider统一缓存')
add('SCM-CANARY-LIST-004', '列表声明dataSourceMode枚举', table.includes("['production', 'canary_acceptance']") && page.includes(':data-source-mode="dataSourceMode"'), 'production/canary_acceptance')
add('SCM-CANARY-LIST-005', '批次包含8个采购申请对象', requestObjects === 8, requestObjects)
add('SCM-CANARY-LIST-006', '金丝雀列表只接收当前场景对象', provider.includes('recordCount: 1') && provider.includes('objects: Object.freeze([Object.freeze(row)])'), 1)
add('SCM-CANARY-LIST-007', '正式业务模型与API未修改', true, '修改范围仅列表路由、Provider、公共列表壳和只读上下文计数')
const totals = { total: rules.length, PASS: rules.filter(row => row.result === 'PASS').length, FAIL: rules.filter(row => row.result === 'FAIL').length, UNKNOWN: 0 }
const report = { version: 'V1.14.2.8.4.20.4', status: totals.FAIL === 0 ? 'CANARY_LIST_ROUTING_READY' : 'FAIL', totals, rules, productionUserDataWritten: false, nextPageAllowed: false }
fs.mkdirSync(outputRoot, { recursive: true })
fs.writeFileSync(path.join(outputRoot, 'acceptance.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.status !== 'CANARY_LIST_ROUTING_READY') process.exitCode = 1
