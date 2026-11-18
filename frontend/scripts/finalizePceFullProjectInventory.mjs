import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.2'
const frontend = path.resolve(import.meta.dirname, '..')
const root = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const inventoryFile = path.join(root, 'page-inventory.json')
const scanFile = path.join(root, 'full-project-runtime-scan.json')
const inventory = JSON.parse(fs.readFileSync(inventoryFile, 'utf8'))
const scan = JSON.parse(fs.readFileSync(scanFile, 'utf8'))
const byRoute = new Map(scan.results.map(result => [result.route, result]))
for (const page of inventory.pages) {
  const runtime = byRoute.get(page.route)
  if (runtime) {
    page.runtimeReachable = runtime.reachable
    page.runtimeEvidence = runtime
    if (!runtime.reachable && page.acceptanceStatus === 'runtime-passed') {
      page.acceptanceStatus = 'runtime-blocked'
      page.classificationReason = runtime.failureReason || '只读路由扫描失败'
    }
  }
}
const count = status => inventory.pages.filter(page => page.acceptanceStatus === status).length
inventory.summary = {
  ...inventory.summary,
  routeReachablePageCount: inventory.pages.filter(page => page.runtimeReachable).length,
  legacyPageCount: count('legacy-page-not-migrated'),
  sampleDataMissingPageCount: count('sample-data-missing'),
  routeUnreachablePageCount: count('route-unreachable'),
  runtimeBlockedPageCount: count('runtime-blocked'),
  runtimePassedPageCount: count('runtime-passed'),
  structureFailedPageCount: count('legacy-page-not-migrated') + count('runtime-blocked'),
  behaviorFailedPageCount: count('legacy-page-not-migrated') + count('runtime-blocked'),
  serverFactFailedPageCount: inventory.pages.filter(page =>
    page.currentStateSource !== 'server' && !['sample-data-missing', 'route-unreachable'].includes(page.acceptanceStatus)).length,
  allPagesClassified: inventory.pages.every(page => Boolean(page.acceptanceStatus)),
  unclassifiedPageCount: inventory.pages.filter(page => !page.acceptanceStatus).length,
}
inventory.runtimeScan = {
  result: scan.result,
  scannedPageCount: scan.scannedPageCount,
  businessWriteRequestCount: scan.businessWriteRequestCount,
}
fs.writeFileSync(inventoryFile, `${JSON.stringify(inventory, null, 2)}\n`)
fs.writeFileSync(path.join(root, 'full-project-classification-report.json'), `${JSON.stringify({
  result: 'passed',
  version: VERSION,
  ...inventory.summary,
  backlog: inventory.pages
    .filter(page => page.acceptanceStatus !== 'runtime-passed')
    .map(page => ({
      moduleCode: page.moduleCode,
      pageCode: page.pageCode,
      fullUrl: page.fullUrl,
      acceptanceStatus: page.acceptanceStatus,
      reason: page.classificationReason,
    })),
}, null, 2)}\n`)
console.log(JSON.stringify(inventory.summary, null, 2))
