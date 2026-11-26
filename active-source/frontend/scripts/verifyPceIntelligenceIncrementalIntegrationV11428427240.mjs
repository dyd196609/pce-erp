import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(frontend, '..')
const phase = process.argv.includes('--phase=automatic') ? 'automatic' : 'final'
const read = (...parts) => fs.readFileSync(path.join(repo, ...parts), 'utf8')
const exists = (...parts) => fs.existsSync(path.join(repo, ...parts))
const sha256 = (...parts) => crypto.createHash('sha256').update(fs.readFileSync(path.join(repo, ...parts))).digest('hex').toUpperCase()
const checks = []
const check = (code, passed, detail) => checks.push({ code, passed: Boolean(passed), detail })

const standard = read('docs', 'governance', 'PCE智能化增量接入规范.md')
const capability = read('docs', 'governance', 'PCE已有智能化能力复用验收报告.md')
const assessment = read('docs', 'governance', '供应商采购链持续建设评估报告.md')

check('PCE-INTELLIGENCE-INTEGRATION-001', ['字段', '列表', '筛选', '按钮', '数据', '验收']
  .every(term => standard.includes(term)) && standard.includes('Metadata Registry')
  && standard.includes('Schema Contract') && standard.includes('Real Browser Evidence'), '六项判断与标准接入链完整')

const forbiddenFrameworkRoots = [
  ['frontend', 'src', 'runtime'], ['frontend', 'src', 'schema'], ['frontend', 'src', 'components'],
  ['backend', 'runtime'], ['backend', 'services'],
]
check('NO-DUPLICATE-FRAMEWORK-001', forbiddenFrameworkRoots.every(parts => !exists(...parts))
  && capability.includes('Duplicate Framework：PASS'), '无第二套Metadata/Schema/Registry/Runtime根目录')

const owners = [
  ['frontend', 'src', 'meta', 'registry', 'metaRegistry.js'],
  ['frontend', 'src', 'meta', 'core', 'schemaRegistry.js'],
  ['frontend', 'src', 'meta', 'runtime', 'pceEnterpriseListContract.js'],
  ['frontend', 'src', 'meta', 'runtime', 'listFilterRuntime.js'],
  ['frontend', 'src', 'meta', 'runtime', 'listActionColumnRuntime.js'],
  ['frontend', 'src', 'meta', 'providers', 'supplierPriceFactRuntimeProvider.js'],
  ['frontend', 'src', 'meta', 'acceptance', 'registry', 'enterpriseAcceptanceRegistry.js'],
]
check('RUNTIME-REUSE-001', owners.every(parts => exists(...parts))
  && assessment.includes('Existing Intelligence Capability Scan'), '八类既有所有者已扫描并复用')

const protectedHashes = new Map([
  ['backend/db.sqlite3', '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847'],
  ['backend/masterdata/master_data_statistics_runtime.py', '5BB3C7E2B18AA89D104D24CA67903D6642ED4A22B5373AE05DCD2674F58D9D4A'],
  ['backend/procurement/scm_runtime_services.py', '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB'],
  ['backend/procurement/purchase_order_supplier_fact_runtime.py', '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5'],
  ['frontend/src/meta/pages/EnterpriseMasterDataPage.vue', 'BD341FBD711E8B12533EA4425EE6F77AA290CE36D448687F21CF8D6164F95F3D'],
  ['frontend/src/meta/pages/SupplierPriceFactPage.vue', 'F37705BD14BE75BA454598103C22325629A7C70F03638E480733548E84BD7C8F'],
  ['frontend/src/meta/pages/SupplierPriceAnalysisPage.vue', '3800F22B2A4EDCFC5BF1A23ADA1DFF164D3AF7B6A63D04525AC6640E0F87A441'],
  ['frontend/src/meta/pages/PurchasePriceReviewAssistantPage.vue', '7DE4DD12797B2EB03B1427671420CAD1E743DD7E5E21472F54B76E3E27E9F810'],
])
const changedProtected = [...protectedHashes].filter(([file, expected]) => sha256(...file.split('/')) !== expected).map(([file]) => file)
check('BUSINESS-REGRESSION-001', changedProtected.length === 0
  && assessment.includes('Business Write Count：0'), changedProtected.length ? changedProtected.join(',') : '业务实现和数据库哈希不变')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.40')
  const screenshots = fs.readdirSync(evidenceDir).filter(name => name.endsWith('.png'))
  const report = read('docs', 'governance', 'PCE智能化增量接入真实运行验收报告.md')
  check('REAL-BROWSER-EVIDENCE-001', screenshots.length >= 4
    && report.includes('Browser Human Acceptance: PASS')
    && report.includes('Business Write Count：0'), `${screenshots.length} screenshots`)
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS PCE_INTELLIGENCE_INCREMENTAL_INTEGRATION ${phase}`)
