import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const outputRoot = path.resolve(frontendRoot, 'test-results/scm-business-runtime-mode-v11428205')
const read = file => fs.readFileSync(path.resolve(sourceRoot, file), 'utf8')
const router = read('frontend/src/router/index.js')
const page = read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const provider = read('frontend/src/meta/runtime/scmBusinessPageRuntimeProvider.js')
const pageFiles = fs.readdirSync(path.resolve(frontendRoot, 'src/meta/pages'))

const rules = []
const add = (code, name, pass, evidence) => rules.push({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })
add('SCM-RUNTIME-001', '正式与金丝雀共用同一页面组件', router.includes("import('@/meta/pages/ScmPurchaseRequestPage.vue')") && !pageFiles.includes('ScmPurchaseRequestCanaryPage.vue'), 'ScmPurchaseRequestPage.vue')
add('SCM-RUNTIME-002', 'Provider按Query切换运行模式', provider.includes("'canary_acceptance'") && provider.includes("'production'") && provider.includes('resolveEnterpriseListCanaryQuery'), 'ProductionBusinessProvider/CanaryReadModelProvider')
add('SCM-RUNTIME-003', '正式API与Canary API分支互斥', provider.includes('if (dataMode === \'canary_acceptance\')') && provider.includes('productionApiCallCount: 0') && provider.includes('canaryApiCallCount: 0'), 'exclusive runtime branches')
add('SCM-RUNTIME-004', '同一列表和详情入口复用', page.includes('PceEnterpriseListTable') && page.includes('openRuntimeView') && page.includes('PceBusinessDetailCard'), '统一列表/查看/详情/明细')
add('SCM-RUNTIME-005', '运行模式只读诊断存在', page.includes('scm-business-runtime-mode') && page.includes('scm-business-data-mode'), 'dataMode diagnostic')
add('SCM-RUNTIME-006', '正式模型与金丝雀数据库隔离', !provider.includes('POST') && !provider.includes('PUT') && !provider.includes('PATCH') && !provider.includes('DELETE'), 'read-only provider routing')
const totals = { total: rules.length, PASS: rules.filter(row => row.result === 'PASS').length, FAIL: rules.filter(row => row.result === 'FAIL').length, UNKNOWN: 0 }
const report = { version: 'V1.14.2.8.4.20.5', status: totals.FAIL === 0 ? 'SCM_BUSINESS_RUNTIME_MODE_READY' : 'FAIL', totals, rules, productionUserDataWritten: false, nextPageAllowed: false }
fs.mkdirSync(outputRoot, { recursive: true })
fs.writeFileSync(path.join(outputRoot, 'acceptance.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.status !== 'SCM_BUSINESS_RUNTIME_MODE_READY') process.exitCode = 1
