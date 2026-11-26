import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { LATEST_BASE_DATA_IMPORT_CHAIN, LATEST_BASE_DATA_TEMPLATE_AUTHORITY } from '../src/meta/contracts/latestBaseDataTemplateContract.js'
import { orderProductionNonRegressionScope } from '../src/meta/master-data/orderProductionBaseDataTemplateAdoption.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')
const fail = message => { throw new Error(`[base-data-capability-non-regression] ${message}`) }
const toolbar = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.toolbar)
const importExtension = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.importExtension)
const table = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.listRuntime)
const filter = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.advancedFilter)
const shell = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.shell)
const runtime = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.runtimeContract)
const legacy = read(LATEST_BASE_DATA_TEMPLATE_AUTHORITY.rejectedLegacyAuthority)
for (const token of ['list-export-current-result-button', 'list-advanced-filter-toggle']) if (!toolbar.includes(token)) fail(`toolbar capability missing: ${token}`)
for (const token of ['list-download-import-template-button', 'list-import-data-button', 'formal-import-preview-dialog', '工作表：', '可导入（READY）', '新建（CREATE）', '匹配已有（MATCH）', '重放验证', '确认导入']) if (!importExtension.includes(token)) fail(`import extension missing: ${token}`)
for (const token of ['data-pce-fixed-header="true"', 'data-pce-pagination="true"', 'PceEnterpriseAdvancedFilter', '@select="handleSingleRowSelection"', '@select-all="handleHeaderSelection"']) if (!table.includes(token)) fail(`list runtime capability missing: ${token}`)
for (const token of ['business-process-navigation', 'PceBusinessNameConsumer']) if (!shell.includes(token)) fail(`navigation/identity missing: ${token}`)
for (const token of ['PCE_ENTERPRISE_LIST_CAPABILITIES', 'advancedFilter: true', 'export: true']) if (!runtime.includes(token)) fail(`machine capability missing: ${token}`)
for (const token of ['normalizeListFilterSchema', 'normalizedSchema']) {
  if (!filter.includes(token)) fail(`advanced filter schema runtime missing: ${token}`)
}
if (!legacy.includes('已写入 localStorage')) fail('rejected legacy authority evidence changed; authority must be reassessed')
if (LATEST_BASE_DATA_IMPORT_CHAIN.at(-1) !== 'reload-formal-facts') fail('formal import chain does not reload facts')
if (orderProductionNonRegressionScope.productionWritesAuthorized) fail('production writes must remain unauthorized')
console.log('PASS base-data capability non-regression: template/import extension, export, advanced filter, process navigation and formal-write guard are active')
