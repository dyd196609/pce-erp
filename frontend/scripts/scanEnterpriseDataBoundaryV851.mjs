import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const version = 'V1.14.2.8.4.8.5.1'
const scanRoots = [
  'src/meta/pages',
  'src/meta/runtime',
  'src/meta/master-data',
  'src/meta/process',
  'src/router',
]
const outputDir = path.join(root, 'test-results/enterprise-data-boundary-v851')
const outputFile = path.join(outputDir, 'enterprise_data_boundary_scan_v851.json')
const textExtensions = new Set(['.js', '.mjs', '.vue', '.json', '.ts'])

function walk(relativeRoot) {
  const absoluteRoot = path.join(root, relativeRoot)
  if (!fs.existsSync(absoluteRoot)) return []
  return fs.readdirSync(absoluteRoot, { withFileTypes: true }).flatMap(entry => {
    const relativePath = path.join(relativeRoot, entry.name)
    return entry.isDirectory() ? walk(relativePath) : [relativePath]
  })
}

function sourceEntries() {
  return scanRoots
    .flatMap(walk)
    .filter(file => textExtensions.has(path.extname(file)))
    .map(file => ({
      file: file.replaceAll('\\', '/'),
      source: fs.readFileSync(path.join(root, file), 'utf8'),
    }))
}

function findMatches(entries, pattern) {
  return entries.flatMap(({ file, source }) => (
    source.split(/\r?\n/).flatMap((line, index) => {
      pattern.lastIndex = 0
      return pattern.test(line)
        ? [{ file, line: index + 1, text: line.trim().slice(0, 300) }]
        : []
    })
  ))
}

function unique(values) {
  return [...new Set(values)].sort()
}

const entries = sourceEntries()
const routerSource = entries.find(item => item.file === 'src/router/index.js')?.source || ''
const routeMatches = [...routerSource.matchAll(/path:\s*['"]([^'"]+)['"]/g)].map(match => match[1])
const foundationRoutes = unique(routeMatches.filter(route => (
  route === 'foundation' || route.startsWith('foundation/')
)).map(route => `/${route}`))
const referenceRoutes = unique(routeMatches.filter(route => (
  route === 'reference' || route.startsWith('reference/')
)).map(route => `/${route}`))
const entryPattern = /(?:router-link[^>]+to=|router\.push\(|href:\s*`?#?)[^<\n]*/i
const maintenancePattern = /新增|编辑|删除|维护|保存|导入|启用|停用|resetDemoData|create[A-Z]|update[A-Z]|delete[A-Z]/
const referencePattern = /\/reference|引用源|引用关系|referenceUsage|integrationWith/
const forbiddenPhaseNamePattern = /第一期基础资料/
const businessReferencePattern = /(?:SCM|CRM|WMS|MRP|MPS|APS|MES|QMS|BI|FDM|KPI).*(?:引用|->)|(?:引用|->).*(?:SCM|CRM|WMS|MRP|MPS|APS|MES|QMS|BI|FDM|KPI)/

const scan = {
  version,
  scanPhase: 'pre-development',
  generatedAt: new Date().toISOString(),
  roots: scanRoots,
  fileCount: entries.length,
  foundationPages: foundationRoutes,
  referencePages: referenceRoutes,
  entryNames: findMatches(entries, entryPattern),
  maintenanceEntries: findMatches(entries, maintenancePattern),
  referenceEntries: findMatches(entries, referencePattern),
  businessModuleReferences: findMatches(entries, businessReferencePattern),
  forbiddenPhaseNames: findMatches(entries, forbiddenPhaseNamePattern),
  boundaryBaseline: {
    enterpriseMasterDataCenter: {
      canonicalName: '企业主数据中心',
      englishName: 'Enterprise Master Data Center',
      abbreviation: 'EMD',
      canonicalEntry: '/master-data/organizations',
    },
    referenceCenter: {
      canonicalName: '数据引用中心',
      canonicalEntry: '/reference',
      mode: 'read-only relationship analysis',
    },
    manufacturingCapabilityMap: {
      canonicalEntry: '/manufacturing/modules',
      mode: 'product architecture display',
    },
    processCenter: {
      canonicalEntry: '/process-center',
      mode: 'business process navigation',
    },
  },
  summary: {
    foundationPageCount: foundationRoutes.length,
    referencePageCount: referenceRoutes.length,
    entryNameCount: findMatches(entries, entryPattern).length,
    maintenanceEntryCount: findMatches(entries, maintenancePattern).length,
    referenceEntryCount: findMatches(entries, referencePattern).length,
    businessModuleReferenceCount: findMatches(entries, businessReferencePattern).length,
    forbiddenPhaseNameCount: findMatches(entries, forbiddenPhaseNamePattern).length,
  },
}

fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(outputFile, `${JSON.stringify(scan, null, 2)}\n`)
console.log(JSON.stringify({
  result: 'PASS',
  outputFile,
  summary: scan.summary,
}, null, 2))
