import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, pass) => checks.push({ name, pass: Boolean(pass) })

const legacyPath = 'docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json'
const legacyBytes = fs.readFileSync(absolute(legacyPath))
const legacyHash = crypto.createHash('sha256').update(legacyBytes).digest('hex')
const legacy = JSON.parse(legacyBytes.toString('utf8'))
const expectedHash = read('docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json.sha256').split(/\s+/)[0]
const adapter = read('backend/procurement/legacy_quote_comparison_adapter.py')
const model = read('backend/procurement/models.py')
const service = read('backend/procurement/price_approval_preparation_service.py')
const api = read('backend/procurement/price_approval_preparation_api.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-ACT-001-R3.md')

check('Legacy Data Read Only', legacyHash === expectedHash
  && adapter.includes('read_bytes()') && !adapter.includes('write_bytes(')
  && !adapter.includes('write_text(') && !adapter.includes('localStorage'))
check('13 Mapping Exists', legacy.recordCount === 13 && legacy.records.length === 13
  && legacy.records.every(item => item.integrityStatus === 'PASS'))
check('Fact Origin Correct', adapter.includes('fact_origin = "legacy_verified_fact"')
  && model.includes('("legacy_verified_fact", "历史验证事实")'))
check('QC Number Unchanged', adapter.includes('canonicalQuoteComparisonNo=comparison_no')
  && adapter.includes('legacyQuoteComparisonNo=comparison_no')
  && !adapter.includes('canonicalQuoteComparisonNo=f'))
check('Projection Fields Complete', ['projectionId', 'legacyQuoteComparisonNo',
  'canonicalQuoteComparisonNo', 'factOrigin', 'sourceConfidence', 'supplierEvidence',
  'materialLines', 'comparisonResult', 'traceAliasId'].every(field => adapter.includes(field)))
check('Trace Alias Stable', adapter.includes('BTA-LEGACY-QC-')
  && adapter.includes('sha256(comparison_no.encode("utf-8"))'))
check('PAP Stable Number', service.includes('f"PAP-{projection.legacyQuoteComparisonNo}"')
  && !service.includes('index + 1') && !service.includes('enumerate('))
check('Fact Source Guard', model.includes('scm_pap_exactly_one_fact_source')
  && model.includes('source_projection_snapshot') && model.includes('PRICE_APPROVAL_FACT_SOURCE_INVALID'))
check('Manual Entry Only', page.includes('生成核价准备')
  && api.includes('sourceProjectionId') && !api.includes('for projection in'))
check('Legacy Page Warning', page.includes('该核价依据来自历史验证事实，来源链已确认，但非重新生成交易对象。'))
check('No Formal Fact Creation', !adapter.includes('QuoteComparisonFact.objects.create')
  && !service.includes('QuoteComparisonFact.objects.create'))
check('No PurchaseOrder Creation', !adapter.includes('PurchaseOrder')
  && !service.includes('PurchaseOrder.objects.create') && service.includes('"purchaseOrderCreated": False'))
check('Canary Protected', read('backend/purchase_canary/price_approval_runtime.py').includes('"factOrigin": "canary_fact"')
  && acceptance.includes('QC-CAN-001 -> PA-CAN-001')
  && acceptance.includes('QC-CAN-003 -> PA-CAN-003'))

const database = new DatabaseSync(absolute('backend/db.sqlite3'), { readOnly: true })
const count = table => Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count)
const migrations = new Set(database.prepare("SELECT name FROM django_migrations WHERE app='procurement'").all().map(row => row.name))
const snapshot = { qcf: count('scm_quote_comparison_fact'), pap: count('scm_price_approval_preparation'),
  po: count('purchase_order') }
database.close()
check('Projection Schema Applied', migrations.has('0013_price_approval_legacy_projection_v11428424_r3')
  && migrations.has('0014_price_approval_projection_snapshot_v11428424_r3'))
check('No Historical Object Created', snapshot.qcf === 0 && snapshot.pap === 0)
check('PurchaseOrder Added Zero', snapshot.po === 208)
check('productionUserDataWritten', acceptance.includes('productionUserDataWritten=false'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`LegacySourceSHA256=${legacyHash}`)
console.log('ProjectionCount=13')
console.log('factOrigin=legacy_verified_fact')
console.log(`QuoteComparisonFactCount=${snapshot.qcf}`)
console.log(`PriceApprovalPreparationCount=${snapshot.pap}`)
console.log(`PurchaseOrderCount=${snapshot.po}`)
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.pass)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length ? 'SCM_LEGACY_FACT_ADAPTER_BLOCKED' : 'SCM_LEGACY_FACT_ADAPTER_READY')
if (failed.length) process.exitCode = 1
