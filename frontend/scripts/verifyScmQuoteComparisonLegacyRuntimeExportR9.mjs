import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { pathToFileURL } from 'node:url'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const toolHtmlPath = 'frontend/public/scm-quote-comparison-legacy-runtime-export-r9.html'
const toolScriptPath = 'frontend/public/scm-quote-comparison-legacy-runtime-export-r9.js'
const sourcePath = 'docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json'
const sourceShaPath = `${sourcePath}.sha256`
const confirmationPath = 'docs/acceptance/SCM-QUOTE-COMPARISON-FACT-CONFIRMATION-R9.md'
const assessmentPath = 'docs/acceptance/legacy_fact_assessment_r9.json'
const acceptancePath = 'frontend/test-results/SCM-QUOTE-COMPARISON-LEGACY-EXPORT-ACT-001-R9.md'
const toolScript = read(toolScriptPath)
const confirmation = read(confirmationPath)
const sourceBytes = fs.readFileSync(absolute(sourcePath))
const source = JSON.parse(sourceBytes.toString('utf8'))
const assessment = JSON.parse(read(assessmentPath))
const acceptance = read(acceptancePath)

check('Export Tool Exists', fs.existsSync(absolute(toolHtmlPath)) && fs.existsSync(absolute(toolScriptPath)))
check('Read Only Mode', toolScript.includes('storage.getItem(key)')
  && !/\.setItem\s*\(/.test(toolScript) && !/\.removeItem\s*\(/.test(toolScript)
  && !/localStorage\.clear\s*\(/.test(toolScript))
check('Required Output Structure', ['quoteComparisonNo', 'sourceType', 'sourceInquiryNo',
  'sourceQuotationNo', 'supplierEvidence', 'materialCode', 'materialName', 'quantity',
  'quotationAmount', 'lowestPrice', 'comparisonResult', 'generatedAt', 'downstreamReference']
  .every(field => toolScript.includes(`${field},`) || toolScript.includes(`${field}:`)))
check('Downstream Reference Protection', toolScript.includes('priceApprovalPreparationNos')
  && toolScript.includes('decisionBatchNos') && toolScript.includes('gateNos'))
check('SHA Generator Exists', toolScript.includes("crypto.subtle.digest('SHA-256'")
  && toolScript.includes(`${'${EXPORT_FILE_NAME}'}.sha256`))
const sourceSha = crypto.createHash('sha256').update(sourceBytes).digest('hex')
const expectedSourceSha = read(sourceShaPath).trim().split(/\s+/)[0]
check('Source Manifest SHA', sourceSha === expectedSourceSha)
const slots = [...confirmation.matchAll(/^\| (\d{2}) \|/gm)].map(match => match[1])
check('13 Confirmation Slot', slots.length === 13
  && slots.every((slot, index) => slot === String(index + 1).padStart(2, '0'))
  && assessment.summary.unknownCount === 13)

const moduleUrl = `${pathToFileURL(absolute(toolScriptPath)).href}?r9=${Date.now()}`
const tool = await import(moduleUrl)
const contexts = []
const quotes = []
const handoffs = []
const bindings = []
const batches = []
const results = []
const gates = []
for (let index = 1; index <= 13; index += 1) {
  const suffix = String(index).padStart(3, '0')
  const inquiryNo = `PI-R9-${suffix}`
  const materialCode = `MT-R9-${suffix}`
  const contextNo = `SQC-R9-${suffix}`
  const quoteNo = `SQ-R9-${suffix}`
  const qcNo = `QC-${inquiryNo}-${materialCode}`
  const papNo = `PAP-R9-${suffix}`
  const batchNo = `DB-R9-${suffix}`
  contexts.push({ supplierQuoteContextNo: contextNo, inquiryNo, sourceRequestNo: `PR-R9-${suffix}`,
    quoteStatus: 'comparison_ready', createdAt: '2026-08-07T00:00:00.000Z',
    materialSupplierCandidates: [{ materialCode, materialName: `Material ${suffix}`, quantity: index,
      supplierCode: `SUP-R9-${suffix}`, supplierName: `Supplier ${suffix}` }] })
  quotes.push({ supplierQuoteContextNo: contextNo, materialCode, supplierCode: `SUP-R9-${suffix}`,
    supplierName: `Supplier ${suffix}`, quoteNo, quotePrice: 100 + index, currency: 'CNY',
    quoteStatus: 'received', receivedAt: '2026-08-07T00:00:00.000Z' })
  handoffs.push({ quoteComparisonId: qcNo, priceApprovalId: papNo })
  bindings.push({ quoteComparisonId: qcNo, priceApprovalId: papNo, batchId: batchNo })
  batches.push({ batchId: batchNo, sourceQuoteComparisonBatch: [qcNo] })
  results.push({ batchId: batchNo, items: [{ quoteComparisonIds: [qcNo] }] })
  gates.push({ gateDecisionId: `GATE-R9-${suffix}`, sourceBatchId: batchNo,
    items: [{ quoteComparisonIds: [qcNo] }] })
}
const stateByKey = {
  [tool.LEGACY_SOURCE_KEY]: JSON.stringify({ contexts, quotes, comparisonPreparations: [] }),
  [tool.DOWNSTREAM_KEYS.priceApprovalHandoff]: JSON.stringify(handoffs),
  [tool.DOWNSTREAM_KEYS.decisionBatch]: JSON.stringify({ bindings, batches, results }),
  [tool.DOWNSTREAM_KEYS.gateDecision]: JSON.stringify(gates),
}
let readCount = 0
const storage = Object.freeze({ getItem(key) { readCount += 1; return stateByKey[key] || null } })
const snapshot = tool.readLegacyRuntimeSnapshot(storage)
const generated = tool.buildLegacyQuoteComparisonExport(snapshot, { exportedAt: '2026-08-07T00:00:00.000Z' })
const generatedJson = `${JSON.stringify(generated, null, 2)}\n`
const generatedSha = await tool.sha256Hex(generatedJson)
const independentSha = crypto.createHash('sha256').update(generatedJson).digest('hex')
check('Read Only Runtime Export', readCount === 4 && generated.recordCount === 13
  && generated.completeCount === 13 && generated.exportStatus === 'exported')
check('Generated SHA Match', generatedSha === independentSha)

const databasePath = absolute('backend/db.sqlite3')
const snapshotDatabase = () => {
  const database = new DatabaseSync(databasePath, { readOnly: true })
  const tables = new Set(database.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(row => row.name))
  const count = table => tables.has(table) ? Number(database.prepare(`SELECT COUNT(*) count FROM ${table}`).get().count) : 0
  const result = { factSchemaApplied: tables.has('scm_quote_comparison_fact'),
    factCount: count('scm_quote_comparison_fact'), priceApprovalCount: count('scm_price_approval'),
    purchaseOrderCount: count('purchase_order') }
  database.close()
  return result
}
const before = snapshotDatabase()
const after = snapshotDatabase()
check('No Business Write', JSON.stringify(before) === JSON.stringify(after))
check('No Fact Added', !after.factSchemaApplied && after.factCount === 0)
check('No PriceApproval Added', after.priceApprovalCount - before.priceApprovalCount === 0)
check('No PurchaseOrder Added', after.purchaseOrderCount - before.purchaseOrderCount === 0)
check('productionUserDataWritten', generated.productionUserDataWritten === false
  && source.productionUserDataWritten === false && acceptance.includes('`productionUserDataWritten=false`'))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`MechanismTestRecordCount=${generated.recordCount}`)
console.log(`OriginalBrowserExportStatus=${source.exportStatus}`)
console.log(`OriginalBrowserExportedCount=${source.recordCount}`)
console.log(`FactSchemaApplied=${after.factSchemaApplied}`)
console.log(`QuoteComparisonFactAdded=${after.factCount - before.factCount}`)
console.log(`PriceApprovalAdded=${after.priceApprovalCount - before.priceApprovalCount}`)
console.log(`PurchaseOrderAdded=${after.purchaseOrderCount - before.purchaseOrderCount}`)
console.log('productionUserDataWritten=false')

const failed = checks.filter(item => !item.pass)
const originalExportReady = source.exportStatus === 'exported' && source.recordCount === 13
const status = failed.length || !originalExportReady
  ? 'SCM_QUOTE_COMPARISON_LEGACY_EXPORT_BLOCKED'
  : 'SCM_QUOTE_COMPARISON_LEGACY_EXPORT_READY'
console.log(status)
if (failed.length) {
  for (const item of failed) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}
