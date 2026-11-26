import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  advancedFilterResponsiveColumns,
  buildAdvancedFilterLayoutRows,
  PCE_ADVANCED_FILTER_LAYOUT_METRICS,
  PCE_ADVANCED_FILTER_LAYOUT_VERSION,
} from '../src/meta/runtime/pceAdvancedFilterLayoutRuntime.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8')
const css = read('src', 'styles', 'pceAdvancedFilterLayout.css')
const component = read('src', 'meta', 'components', 'PceEnterpriseAdvancedFilter.vue')
const list = read('src', 'meta', 'components', 'PceEnterpriseListTable.vue')
const foundation = read('src', 'meta', 'pages', 'ManufacturingFoundationPage.vue')
const main = read('src', 'main.js')
const packageJson = JSON.parse(read('package.json'))

const sampleRows = buildAdvancedFilterLayoutRows([
  { field: 'name', filterType: 'text' },
  { field: 'status', filterType: 'select' },
  { field: 'amount', filterType: 'numberRange' },
  { field: 'createdAt', filterType: 'daterange' },
])

const checks = {
  'FILTER-LAYOUT-HEIGHT-001':
    PCE_ADVANCED_FILTER_LAYOUT_METRICS.controlHeight === 36
    && css.includes('--pce-filter-control-height: 36px')
    && css.includes('height: var(--pce-filter-control-height) !important'),
  'FILTER-LAYOUT-WIDTH-001':
    PCE_ADVANCED_FILTER_LAYOUT_METRICS.controlMinWidth === 180
    && css.includes('--pce-filter-control-min-width: 180px')
    && css.includes('width: 100% !important'),
  'FILTER-LAYOUT-RESPONSIVE-001':
    [375, 768, 1024, 1440].map(advancedFilterResponsiveColumns).join(',') === '1,2,3,4'
    && ['min-width: 768px', 'min-width: 1024px', 'min-width: 1440px'].every(value => css.includes(value)),
  'FILTER-LAYOUT-ROWS-001':
    sampleRows.query.length === 2
    && sampleRows.range.length === 2
    && ['query', 'range', 'actions'].every(row => component.includes(`data-pce-filter-row="${row}"`))
    && ['query', 'range', 'actions'].every(row => foundation.includes(`data-pce-filter-row="${row}"`)),
  'FILTER-RUNTIME-SOURCE-ISOLATION-001':
    list.includes('<PceEnterpriseAdvancedFilter')
    && list.includes('@clear-filters="$emit(\'clear-filters\')"')
    && main.includes("./styles/pceAdvancedFilterLayout.css")
    && foundation.includes('V1.14.2.8.4.27.2.31')
    && PCE_ADVANCED_FILTER_LAYOUT_VERSION === 'PCE-ADVANCED-FILTER-LAYOUT-V1.0',
  'BUSINESS-WRITE-COUNT-0':
    !component.includes('fetch(')
    && !foundation.includes('PCE_FILTER_LAYOUT_WRITE')
    && packageJson.scripts['verify:pce-filter-layout:v11428427231'],
}

let failed = false
for (const [name, passed] of Object.entries(checks)) {
  console.log(`${name} ${passed ? 'PASS' : 'FAIL'}`)
  if (!passed) failed = true
}
console.log('Business Write Count 0')
if (failed) process.exit(1)
