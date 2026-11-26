import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const version = 'V1.14.2.8.4.8.5.2'
const scanRoots = [
  'src/router',
  'src/meta/pages',
  'src/meta/master-data',
  'src/meta/runtime',
  'src/meta/process',
]
const outputDir = path.join(root, 'test-results/enterprise-entry-governance-v852')
const outputFile = path.join(outputDir, 'enterprise_entry_boundary_scan_v852.json')

const routerSource = fs.readFileSync(path.join(root, 'src/router/index.js'), 'utf8')
const routeBlocks = [...routerSource.matchAll(/\{\s*path:\s*['"]([^'"]+)['"]([\s\S]*?)\n\s*\},/g)]

function absoluteRoute(route) {
  if (route.startsWith('/')) return route
  return `/${route.replace(/^\/+/, '')}`
}

function classify(url, block) {
  const sourceMatch = block.match(/import\(['"]@\/([^'"]+)['"]\)/)
  const sourceFile = sourceMatch?.[1] || (
    url.startsWith('/master-data/') ? 'meta/pages/EnterpriseMasterDataPage.vue' : ''
  )
  const isReference = url === '/reference' || url.startsWith('/reference/')
  const isMasterData = url.startsWith('/master-data/')
  const isFoundation = url === '/foundation' || url.startsWith('/foundation/')
  const isCapabilityMap = url === '/manufacturing' || url.startsWith('/manufacturing/')
  const isProcessCenter = url === '/process-center' || url.startsWith('/process-center/')
  const isBusinessPartnerLegacy = [
    '/foundation/business-partners',
    '/foundation/suppliers',
    '/foundation/dealers',
    '/foundation/company-bank-accounts',
  ].includes(url)
  const isOldEntry = isBusinessPartnerLegacy || url === '/manufacturing' || isFoundation
  const module = isMasterData || isFoundation
    ? 'EMD'
    : isReference
      ? 'Reference'
      : isCapabilityMap
        ? 'ManufacturingCapabilityMap'
        : isProcessCenter
          ? 'BusinessProcessCenter'
          : 'BusinessModule'
  const pageName = isMasterData
    ? '企业主数据中心'
    : isFoundation
      ? '企业基础资料'
      : isReference
        ? '数据引用中心'
        : isCapabilityMap
          ? 'PCE制造数字化能力地图'
          : isProcessCenter
            ? '业务流程中心'
            : url.split('/').filter(Boolean).at(-1) || '首页'
  const dataSource = isMasterData
    ? 'server'
    : isFoundation
      ? 'manufacturingFoundationStore'
      : isReference
        ? 'manufacturingReferenceService'
        : isCapabilityMap
          ? 'manufacturingModuleRegistry'
          : isProcessCenter
            ? 'businessProcessRegistry'
            : 'business-module-facts'
  return {
    pageUrl: url,
    pageName,
    module,
    dataSource,
    maintainsData: isMasterData || isFoundation,
    readOnlyReference: isReference,
    oldEntry: isOldEntry,
    sourceFile,
    redirect: block.match(/redirect:\s*['"]([^'"]+)['"]/)?.[1] || null,
  }
}

const pages = routeBlocks.map(match => classify(absoluteRoute(match[1]), match[2]))
const oldEntries = pages.filter(page => page.oldEntry)
const report = {
  version,
  scanPhase: 'pre-development',
  generatedAt: new Date().toISOString(),
  roots: scanRoots,
  pages,
  oldEntries,
  entrySummary: {
    pageCount: pages.length,
    maintenancePageCount: pages.filter(page => page.maintainsData).length,
    referencePageCount: pages.filter(page => page.readOnlyReference).length,
    oldEntryCount: oldEntries.length,
    businessPartnerLegacyCount: oldEntries.filter(page => page.pageUrl.includes('business-partners')
      || page.pageUrl.includes('suppliers')
      || page.pageUrl.includes('dealers')
      || page.pageUrl.includes('company-bank-accounts')).length,
  },
}

fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(outputFile, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ result: 'PASS', outputFile, summary: report.entrySummary }, null, 2))
