import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listPceBusinessModules } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { getPceBatchCapabilityContract, listPceBatchCapabilityContracts } from '../src/meta/runtime/pceBatchCapabilityRegistry.js'
import { PCE_CHANGE_SCOPE_POLICY_VERSION } from '../src/meta/runtime/pceChangeScopePolicy.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const outputDir = path.join(root, 'test-results/pce-capability')
const currentOutput = path.join(outputDir, 'current-capability-fingerprint.json')
const baselineOutput = path.join(outputDir, 'name-change-before-capability-fingerprint.json')

function readSource(relativePath = '') {
  const full = path.join(root, relativePath)
  return fs.existsSync(full) ? fs.readFileSync(full, 'utf8') : ''
}

function count(source, pattern) {
  return (source.match(pattern) || []).length
}

function includesAny(source, markers = []) {
  return markers.some((marker) => source.includes(marker))
}

function metricBoolean(source, markers = []) {
  return includesAny(source, markers) ? 1 : 0
}

export function buildPcePageCapabilityFingerprint() {
  const modules = listPceBusinessModules().filter((item) => item.pageComponent)
  const pageDescriptors = new Map(modules.map((module) => [module.moduleId, module]))
  for (const contract of listPceBatchCapabilityContracts()) {
    pageDescriptors.set(contract.pageId, {
      ...pageDescriptors.get(contract.pageId),
      ...contract,
      moduleId: contract.pageId,
    })
  }
  const pages = [...pageDescriptors.values()].map((module) => {
    const source = readSource(module.pageComponent)
    const template = source
    const semanticBatchContract = getPceBatchCapabilityContract(module.moduleId)
    const legacyBatchSourceTokenCount = count(source, /batch|Batch|批量/g)
    const batchBusinessActionIds = semanticBatchContract?.actionIds
      .filter((actionId) => source.includes(`'${actionId}'`) || source.includes(`"${actionId}"`)) || []
    const batchBusinessSectionDeclared = !semanticBatchContract
      || semanticBatchContract.actionIds.length === 0
      || source.includes(semanticBatchContract.sectionId)
      || source.includes('`${currentPageId}-batch-actions`')
    const tableCount = count(template, /<el-table(?:\s|>|$)/g)
    const declaredSchemaColumnCount = [...source.matchAll(/columnSchema:\s*\[([\s\S]*?)\]\s*,\s*defaultSort/g)]
      .reduce((total, match) => total + count(match[1], /\{\s*key:\s*['"][^'"]+['"]/g), 0)
    const schemaTableCount = count(source, /createStandardListContract\(\{/g)
    const staticTableColumnCount = count(template, /<el-table-column(?:\s|>|$)/g)
    const tableColumnCount = staticTableColumnCount + declaredSchemaColumnCount
      - (declaredSchemaColumnCount > 0 ? schemaTableCount : 0)
    const operationColumnCount = count(template, /<el-table-column[\s\S]{0,240}(label="[^"]*操作[^"]*"|fixed="right"|class-name="[^"]*action)/g)
    const rowOperationCount = count(template, /<el-button\b|<router-link\b|@click=/g)
    const explicitHorizontalScrollOwnerCount = metricBoolean(source, [
      'BusinessTableScrollContainer',
      'business-table-scroll-',
      'scrollbar-always-on',
      'overflow-x: auto',
      'overflow-x:auto',
      'overflow-x: scroll',
      'overflow-x:scroll',
    ])
    const fuzzySearchCount = count(source, /quickSearch|QuickSearch|quick-search|fuzzySearch|list-fuzzy-search|快速搜索|搜索/g)
    const advancedFilterToggleCount = count(source, /advancedFilterVisible|advanced-visible|list-advanced-filter|高级筛选|filter-grid/g)
    const advancedFilterFieldCount = count(source, /filters\.[A-Za-z0-9_]+|v-model="[^"]*Filter|v-model="filters\.[^"]+"/g)
      + (module.advancedFilterFields?.length || 0)
    const exportCurrentResultCount = count(source, /exportCurrent|exportCurrentRows|exportRows|downloadCsv|导出当前结果|list-export-current-result/g)

    return {
      pageId: module.moduleId,
      route: module.route,
      moduleId: module.moduleId,
      canonicalName: module.canonicalName,
      sourceFile: module.pageComponent,
      fuzzySearchCount,
      advancedFilterToggleCount,
      advancedFilterFieldCount,
      tableCount,
      tableColumnCount,
      operationColumnCount,
      rowOperationCount,
      horizontalScrollOwnerCount: explicitHorizontalScrollOwnerCount || (tableColumnCount >= 8 ? 1 : 0),
      fixedLeftColumnCount: count(template, /fixed="left"/g),
      fixedRightColumnCount: count(template, /fixed="right"/g),
      paginationCount: count(template, /<el-pagination\b|pagination/gi),
      batchActionCount: legacyBatchSourceTokenCount,
      legacyBatchSourceTokenCount,
      batchBusinessActionCount: batchBusinessActionIds.length,
      batchBusinessActionIds,
      batchBusinessSectionId: semanticBatchContract?.sectionId || '',
      batchBusinessSectionDeclared,
      exportCurrentResultCount,
    }
  })

  return {
    version: PCE_CHANGE_SCOPE_POLICY_VERSION,
    fingerprintScannerVersion: 'V1.14.2.8.3.1-scan2',
    generatedAt: new Date().toISOString(),
    baselineType: 'name_change_capability_fingerprint',
    pageCount: pages.length,
    pages,
  }
}

export function writePcePageCapabilityFingerprint() {
  const fingerprint = buildPcePageCapabilityFingerprint()
  fs.mkdirSync(outputDir, { recursive: true })
  fs.writeFileSync(currentOutput, `${JSON.stringify(fingerprint, null, 2)}\n`, 'utf8')
  const shouldSeedBaseline = !fs.existsSync(baselineOutput)
    || JSON.parse(fs.readFileSync(baselineOutput, 'utf8')).fingerprintScannerVersion !== fingerprint.fingerprintScannerVersion
  if (shouldSeedBaseline) {
    fs.writeFileSync(baselineOutput, `${JSON.stringify({
      ...fingerprint,
      baselineSeededFrom: 'current_workspace_after_regression_restore',
      baselineSeedReason: 'Git history has no V1.14.2.8.2 commit; seed current restored capability as future guard baseline.',
    }, null, 2)}\n`, 'utf8')
  }
  return { fingerprint, currentOutput, baselineOutput }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { fingerprint, currentOutput, baselineOutput } = writePcePageCapabilityFingerprint()
  console.log(JSON.stringify({
    version: fingerprint.version,
    pageCount: fingerprint.pageCount,
    currentOutput: path.relative(root, currentOutput).replaceAll('\\', '/'),
    baselineOutput: path.relative(root, baselineOutput).replaceAll('\\', '/'),
  }, null, 2))
}
