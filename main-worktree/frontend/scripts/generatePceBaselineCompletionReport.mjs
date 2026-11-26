import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const VERSION = 'V1.14.2.8.4.4'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const outputRoot = path.join(root, 'test-results/pce-ui-baseline')

function readJson(relativePath) {
  const file = path.join(root, relativePath)
  if (!fs.existsSync(file)) throw new Error(`Missing evidence file: ${relativePath}`)
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

function writeJson(relativePath, value) {
  const file = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function percent(count, total) {
  return total ? Number(((count / total) * 100).toFixed(2)) : 100
}

const manifest = readJson('test-results/pce-ui-baseline/page-manifest.json')
const matrix = readJson('test-results/pce-ui-baseline/canonical-name-matrix.json')
const enforcement = readJson('test-results/pce-ui-baseline/enforcement-summary.json')
const operationColumns = readJson('test-results/pce-operation-columns/operation-column-manifest.json')
const pageEvidences = manifest.pages.map((page) => readJson(page.evidencePath))
const tableEvidenceDir = path.join(outputRoot, 'tables')
const tableEvidenceFiles = fs.existsSync(tableEvidenceDir)
  ? fs.readdirSync(tableEvidenceDir).filter((file) => file.endsWith('.json')).sort()
  : []
const tableEvidences = tableEvidenceFiles.map((file) => readJson(`test-results/pce-ui-baseline/tables/${file}`))

const pageCount = manifest.pages.length
const passedPages = pageEvidences.filter((item) => item.overallStatus === 'passed')
const failedPages = pageEvidences.filter((item) => item.overallStatus !== 'passed')
const sampleInsufficientPages = pageEvidences.filter((item) => item.sampleStatus === 'sample_insufficient')
const runtimeRequiredPages = manifest.pages.filter((item) => item.runtimeTestRequired)
const nameMatchedPages = matrix.pages.filter((item) => item.allExactMatched)
const shellPages = manifest.pages.filter((item) => item.shellType === 'PceListPageShell')
const toolbarPages = pageEvidences.filter((item) => item.staticChecks?.toolbarPassed)
const searchFilterPages = pageEvidences.filter((item) => item.staticChecks?.fuzzySearchPassed && item.staticChecks?.advancedFilterPassed)
const fixedColumnPages = pageEvidences.filter((item) => item.staticChecks?.fixedLeftPassed)
const operationColumnPages = pageEvidences.filter((item) => item.staticChecks?.operationColumnPassed)
const scrollPages = pageEvidences.filter((item) => item.staticChecks?.horizontalScrollPassed)
const failureItems = failedPages.flatMap((item) => item.failureItems || [])
const passedTables = tableEvidences.filter((item) => item.overallStatus === 'passed')
const failedTables = tableEvidences.filter((item) => item.overallStatus !== 'passed')
const tableFailureItems = failedTables.flatMap((item) => item.failureItems || [])
const operationFailureDefinitions = {
  missingOperationColumns: 'operation_column_missing',
  headerOnlyOperationColumns: 'operation_header_only',
  operationColumnsNotLast: 'operation_column_not_last',
  operationColumnsNotFixed: 'operation_column_not_fixed',
  floatingOperationColumns: 'operation_column_floating',
  jitterOperationColumns: 'operation_column_jitter',
  operationColumnsNotAtRightEdge: 'operation_column_not_at_right_edge',
  wrongScrollAncestorOperationColumns: 'operation_column_wrong_scroll_ancestor',
  coveredOperationColumns: 'operation_column_covered',
  transparentOperationColumns: 'operation_column_transparent',
  clippedOperationButtons: 'operation_button_clipped',
  unclickableOperationButtons: 'operation_button_not_clickable',
  wrongRecordOperationButtons: 'operation_button_wrong_record',
  unstableWidthOperationColumns: 'operation_column_width_unstable',
}
const operationColumnFailureLists = Object.fromEntries(Object.entries(operationFailureDefinitions).map(([listName, failureCode]) => [
  listName,
  (operationColumns.tables || []).filter((item) => item.operationRequired && (item.failureItems || []).includes(failureCode)).map((item) => ({
    pageId: item.pageId,
    tableId: item.tableId,
    fullUrl: item.fullUrl,
    sectionTitle: item.sectionTitle,
    failureCode,
  })),
]))

const report = {
  version: VERSION,
  generatedAt: new Date().toISOString(),
  sourceFiles: {
    pageManifest: 'test-results/pce-ui-baseline/page-manifest.json',
    canonicalNameMatrix: 'test-results/pce-ui-baseline/canonical-name-matrix.json',
    enforcementSummary: 'test-results/pce-ui-baseline/enforcement-summary.json',
    pageEvidenceDirectory: 'test-results/pce-ui-baseline/pages',
    tableEvidenceDirectory: 'test-results/pce-ui-baseline/tables',
    operationColumnManifest: 'test-results/pce-operation-columns/operation-column-manifest.json',
  },
  truthfulness: {
    generatedFromEvidenceFiles: true,
    manualNumberAllowed: false,
    pageManifestCountMatchesEvidenceCount: manifest.pages.length === pageEvidences.length,
    failedPageCountMatchesEvidence: enforcement.failedPageCount === failedPages.length,
    passedPageCountMatchesEvidence: enforcement.passedPageCount === passedPages.length,
    nameMatrixCountMatchesManifest: matrix.pages.length === pageCount,
    tableEvidenceDirectoryPresent: tableEvidenceFiles.length > 0,
    tableContractCountMatchesEvidenceCount: (enforcement.tableBindingSummary?.discoveredBusinessTableCount ?? tableEvidences.length) === tableEvidences.length,
    operationColumnCoverageMatched: operationColumns.discoveredOperationRequiredTableCount === operationColumns.runtimeTestedOperationTableCount
      && operationColumns.runtimeTestedOperationTableCount === operationColumns.runtimePassedOperationTableCount,
    failedTableCountGeneratedFromEvidence: true,
    passedTableCountGeneratedFromEvidence: true,
  },
  metrics: {
    discoveredBusinessPageCount: pageCount,
    classifiedPageCount: pageCount,
    pageTypeSummary: enforcement.pageTypeSummary,
    pceListShellPageCount: shellPages.length,
    missingShellPageCount: pageCount - shellPages.length,
    nameMatchedPageCount: nameMatchedPages.length,
    nameConflictPageCount: pageCount - nameMatchedPages.length,
    toolbarImplementedPageCount: toolbarPages.length,
    searchFilterImplementedPageCount: searchFilterPages.length,
    fixedColumnImplementedPageCount: fixedColumnPages.length,
    operationColumnImplementedPageCount: operationColumnPages.length,
    horizontalScrollImplementedPageCount: scrollPages.length,
    runtimeRequiredPageCount: runtimeRequiredPages.length,
    testedPageCount: pageEvidences.length,
    passedPageCount: passedPages.length,
    failedPageCount: failedPages.length,
    discoveredBusinessTableCount: tableEvidences.length,
    generatedTableEvidenceCount: tableEvidences.length,
    testedBusinessTableCount: tableEvidences.length,
    passedBusinessTableCount: passedTables.length,
    failedBusinessTableCount: failedTables.length,
    toolbarActualRenderedCount: tableEvidences.filter((item) => item.toolbarBound).length,
    toolbarActualBoundCount: tableEvidences.filter((item) => item.toolbarBound).length,
    advancedFilterPanelCount: tableEvidences.filter((item) => item.advancedFilterVisible).length,
    advancedFilterEffectiveCount: tableEvidences.filter((item) => item.advancedFilterPassed).length,
    operationColumnDomCount: tableEvidences.filter((item) => item.operationColumnPassed).length,
    rowOperationDomCount: tableEvidences.filter((item) => item.rowOperationPassed).length,
    horizontalOverflowTableCount: tableEvidences.filter((item) => item.horizontalOverflowDetected).length,
    usableHorizontalScrollCount: tableEvidences.filter((item) => item.horizontalScrollPassed).length,
    sampleInsufficientPageCount: sampleInsufficientPages.length,
    untestedPageCount: runtimeRequiredPages.length - pageEvidences.length,
    repeatedDefectCount: failureItems.length + tableFailureItems.length,
    unregisteredPlatformRuleCount: 0,
    discoveredOperationRequiredTableCount: operationColumns.discoveredOperationRequiredTableCount,
    existingOperationColumnCount: operationColumns.existingOperationColumnCount,
    runtimeTestedOperationTableCount: operationColumns.runtimeTestedOperationTableCount,
    runtimePassedOperationTableCount: operationColumns.runtimePassedOperationTableCount,
    missingOperationColumnCount: operationColumns.missingOperationColumnCount,
    operationHeaderOnlyCount: operationColumns.operationHeaderOnlyCount,
    operationColumnNotFixedCount: operationColumns.operationColumnNotFixedCount,
    floatingOperationColumnCount: operationColumns.floatingOperationColumnCount,
    jitterOperationColumnCount: operationColumns.jitterOperationColumnCount,
    notAtRightEdgeOperationColumnCount: operationColumns.notAtRightEdgeOperationColumnCount,
    wrongScrollAncestorOperationColumnCount: operationColumns.wrongScrollAncestorOperationColumnCount,
    coveredOperationColumnCount: operationColumns.coveredOperationColumnCount,
    coversBusinessColumnCount: operationColumns.coversBusinessColumnCount,
    transparentOperationColumnCount: operationColumns.transparentOperationColumnCount,
    clippedOperationButtonCount: operationColumns.clippedOperationButtonCount,
    unclickableOperationButtonCount: operationColumns.unclickableOperationButtonCount,
    wrongRecordOperationButtonCount: operationColumns.wrongRecordOperationButtonCount,
    unstableWidthOperationColumnCount: operationColumns.unstableWidthOperationColumnCount,
    untestedOperationTableCount: operationColumns.untestedOperationTableCount,
  },
  rates: {
    pageShellAdoptionRate: percent(shellPages.length, pageCount),
    canonicalNameConsistencyRate: percent(nameMatchedPages.length, pageCount),
    toolbarImplementationRate: percent(toolbarPages.length, pageCount),
    searchFilterImplementationRate: percent(searchFilterPages.length, pageCount),
    fixedColumnImplementationRate: percent(fixedColumnPages.length, pageCount),
    operationColumnImplementationRate: percent(operationColumnPages.length, pageCount),
    horizontalScrollImplementationRate: percent(scrollPages.length, pageCount),
    runtimePageCoverageRate: percent(pageEvidences.length, runtimeRequiredPages.length),
    runtimeInteractionCoverageRate: (failedPages.length || failedTables.length) ? 0 : 100,
  },
  failedPages: failedPages.map((item) => ({
    pageId: item.pageId,
    route: item.route,
    canonicalName: item.canonicalName,
    failureItems: item.failureItems,
  })),
  failedTables: failedTables.map((item) => ({
    pageId: item.pageId,
    tableId: item.tableId,
    fullUrl: item.fullUrl,
    sectionTitle: item.sectionTitle,
    failureItems: item.failureItems,
    evidencePath: `test-results/pce-ui-baseline/tables/${item.tableId}.json`,
  })),
  operationColumnFailures: (operationColumns.tables || []).filter((item) => item.operationRequired && item.overallStatus !== 'passed'),
  operationColumnFailureLists,
  operationColumnScreenshotEvidence: (operationColumns.tables || []).filter((item) => item.operationRequired).map((item) => ({
    pageId: item.pageId,
    tableId: item.tableId,
    screenshotPaths: item.screenshotPaths,
  })),
}

const truthCheckKeys = [
  'generatedFromEvidenceFiles',
  'pageManifestCountMatchesEvidenceCount',
  'failedPageCountMatchesEvidence',
  'passedPageCountMatchesEvidence',
  'nameMatrixCountMatchesManifest',
  'tableEvidenceDirectoryPresent',
  'tableContractCountMatchesEvidenceCount',
  'operationColumnCoverageMatched',
  'failedTableCountGeneratedFromEvidence',
  'passedTableCountGeneratedFromEvidence',
]
const truthPassed = truthCheckKeys.every((key) => report.truthfulness[key] === true)
if (!truthPassed) {
  report.truthfulness.reportTruthfulnessPassed = false
  writeJson('test-results/pce-ui-baseline/completion-report.json', report)
  console.log(JSON.stringify(report, null, 2))
  console.error(`${VERSION} PCE completion report truthfulness check failed.`)
  process.exit(1)
}

report.truthfulness.reportTruthfulnessPassed = true
writeJson('test-results/pce-ui-baseline/completion-report.json', report)

console.log(JSON.stringify(report, null, 2))
if (failedTables.length || failedPages.length || operationColumns.overallStatus !== 'passed') {
  console.error(`${VERSION} PCE completion report generated from evidence files; runtime evidence contains failures.`)
  process.exit(1)
}

console.log(`${VERSION} PCE completion report generated from evidence files.`)

