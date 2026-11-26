import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const VERSION = 'V1.14.2.8.4.3'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const evidenceRoot = path.join(root, 'test-results/pce-table-layout-fix')

const requiredTables = [
  ['payment-order-drafts', 'payment-order-drafts-source'],
  ['payment-order-drafts', 'payment-order-drafts-main'],
  ['payable-checks', 'payable-check-main'],
  ['payment-order-prepares', 'payment-instruction-prepare-main'],
  ['payment-execution-prepares', 'payment-execution-prepare-list'],
  ['ap-drafts', 'account-payable-draft-main'],
  ['payment-risk-reviews', 'payment-risk-reviews-source'],
  ['payment-risk-reviews', 'payment-risk-reviews-main'],
  ['payment-voucher-drafts', 'payment-voucher-drafts-source'],
  ['payment-voucher-drafts', 'payment-voucher-drafts-main'],
]

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

function exists(file) {
  return fs.existsSync(file)
}

const failures = []
const rows = requiredTables.map(([pageId, tableId]) => {
  const dir = path.join(evidenceRoot, pageId, tableId)
  const evidenceFile = path.join(dir, 'layout-evidence.json')
  const evidence = exists(evidenceFile) ? readJson(evidenceFile) : null
  const screenshots = ['left.png', 'middle.png', 'right.png'].map((file) => path.join(dir, file))

  if (!evidence) failures.push(`${pageId}/${tableId}: missing layout-evidence.json`)
  for (const screenshot of screenshots) {
    if (!exists(screenshot)) failures.push(`${pageId}/${tableId}: missing ${path.basename(screenshot)}`)
  }
  if (evidence) {
    if (evidence.version !== VERSION) failures.push(`${pageId}/${tableId}: evidence version mismatch`)
    if (evidence.passed !== true) failures.push(`${pageId}/${tableId}: evidence did not pass`)
    if (evidence.scrollOwnerCount !== 1) failures.push(`${pageId}/${tableId}: scroll owner count is not 1`)
    if (evidence.scroll?.horizontalScrollbarVisible !== true) failures.push(`${pageId}/${tableId}: horizontal scrollbar is not visible`)
    if (evidence.operationHeaderCoordinateStable !== true) failures.push(`${pageId}/${tableId}: operation header is not stable`)
    if (evidence.operationCellCoordinateStable !== true) failures.push(`${pageId}/${tableId}: operation cell is not stable`)
    if (evidence.lastBusinessColumnVisible !== true) failures.push(`${pageId}/${tableId}: right edge is not reachable`)
  }

  return {
    pageId,
    tableId,
    evidencePresent: Boolean(evidence),
    screenshotsPresent: screenshots.every(exists),
    passed: Boolean(evidence?.passed),
    headerDelta: evidence?.operationHeaderCoordinateDelta ?? null,
    maxScrollLeft: evidence?.scroll?.maxScrollLeft ?? null,
  }
})

const summary = {
  version: VERSION,
  evidenceRoot: 'test-results/pce-table-layout-fix',
  requiredTableCount: requiredTables.length,
  checkedTableCount: rows.length,
  passedTableCount: rows.filter((item) => item.passed).length,
  failureCount: failures.length,
  rows,
  failures,
}

console.log(JSON.stringify(summary, null, 2))

if (failures.length > 0) {
  console.error(`${VERSION} finance table layout evidence gate failed.`)
  process.exit(1)
}

console.log(`${VERSION} finance table layout evidence gate passed.`)

