import fs from 'node:fs'
import path from 'node:path'
import {
  PCE_ADVANCED_FILTER_CONTRACT_VERSION,
  PCE_FILTER_DISPLAY_MAP,
  isPceBusinessDictionaryField,
  isPceEnumField,
} from '../src/meta/runtime/pceAdvancedFilterContract.js'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import {
  findPceBusinessModuleById,
} from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { findPageAcceptanceContract } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const VERSION = 'V1.14.2.8.4.7.52.1'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-filter-contract-v521')
const allowedTypes = new Set(['select', 'numberRange', 'dateRange', 'text'])
const forbiddenEnums = ['draft', 'reviewed', 'passed', 'blocked']
const failures = []
const assertions = []

function guard(name, passed, expected, actual, page = null) {
  const row = {
    version: VERSION,
    contractVersion: PCE_ADVANCED_FILTER_CONTRACT_VERSION,
    guard: name,
    pageCode: page?.pageStepId || 'global',
    canonicalName: page?.canonicalName || '高级筛选统一治理',
    fullUrl: page?.fullUrl || '',
    regionTitle: '高级筛选',
    relativePosition: '标准列表工具栏之后',
    fieldName: name,
    expected,
    actual,
    ctrlFKeyword: '展开高级筛选',
    passed: Boolean(passed),
  }
  assertions.push(row)
  if (!passed) failures.push(row)
}

guard(
  'filter_enum_values_not_exposed',
  forbiddenEnums.every(value => PCE_FILTER_DISPLAY_MAP[value] && PCE_FILTER_DISPLAY_MAP[value] !== value),
  'draft/reviewed/passed/blocked 全部映射为中文',
  Object.fromEntries(forbiddenEnums.map(value => [value, PCE_FILTER_DISPLAY_MAP[value]])),
)

for (const page of financeProcessPageRegistry) {
  const moduleRecord = findPceBusinessModuleById(page.pageStepId)
  const acceptance = findPageAcceptanceContract(page.routePath)
  const schema = moduleRecord?.advancedFilterSchema || []
  const acceptanceSchema = acceptance?.listContracts?.[0]?.advancedFilterSchema || []
  const source = fs.readFileSync(path.join(frontend, page.pageComponent), 'utf8')
  const advancedSegments = [...source.matchAll(/data-pce-filter-for=/g)].map(match => {
    const end = source.indexOf('BusinessTableScrollContainer', match.index)
    return source.slice(match.index, end > match.index ? end : match.index + 3000)
  }).join('\n')

  guard(
    'filter_schema_has_display_labels',
    schema.length >= 3 && schema.every(field => (
      field.field
      && /[\u4e00-\u9fff]/.test(field.label)
      && allowedTypes.has(field.type)
      && field.displayMap && typeof field.displayMap === 'object'
      && typeof field.optionsProvider === 'string' && field.optionsProvider.length > 0
    )),
    '每项均含 field/中文 label/type/displayMap/optionsProvider',
    schema,
    page,
  )
  guard(
    'business_dictionary_fields_use_select',
    schema.filter(field => isPceBusinessDictionaryField(field.field)).every(field => field.type === 'select'),
    '供应商、法人、账簿、币种、银行接口、支付路线、签署策略、授权路线、场景类型均为 select',
    schema.filter(field => isPceBusinessDictionaryField(field.field)).map(field => ({ field: field.field, type: field.type })),
    page,
  )
  guard(
    'filter_enum_values_not_exposed',
    schema.filter(field => isPceEnumField(field.field)).every(field => (
      forbiddenEnums.every(value => field.displayMap[value] === PCE_FILTER_DISPLAY_MAP[value])
    )),
    '枚举 displayMap 不暴露英文技术值',
    schema.filter(field => isPceEnumField(field.field)).map(field => ({ field: field.field, displayMap: field.displayMap })),
    page,
  )
  guard(
    'advanced_filter_contract_consistent',
    schema.length === acceptanceSchema.length
      && schema.every((field, index) => (
        acceptanceSchema[index]?.field === field.field
        && acceptanceSchema[index]?.label === field.label
        && acceptanceSchema[index]?.type === field.type
        && acceptanceSchema[index]?.optionsProvider === field.optionsProvider
      )),
    '模块注册表与页面验收注册表字段、标签、类型和选项来源一致',
    { moduleSchema: schema, acceptanceSchema },
    page,
  )

  const rawDictionaryInput = [
    /供应商\s*<el-input/,
    /法人\s*<el-input/,
    /账簿\s*<el-input/,
    /币种\s*<el-input/,
    /银行接口\s*<el-input/,
    /支付路(?:由|线)\s*<el-input/,
    /签署策略\s*<el-input/,
    /授权路线\s*<el-input/,
    /场景类型\s*<el-input/,
  ].some(pattern => pattern.test(advancedSegments))
  guard(
    'business_dictionary_fields_use_select',
    !rawDictionaryInput,
    '正式高级筛选不存在字典字段 el-input',
    rawDictionaryInput ? 'found_dictionary_input' : 'select_only',
    page,
  )
}

const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  contractVersion: PCE_ADVANCED_FILTER_CONTRACT_VERSION,
  strictPageCount: financeProcessPageRegistry.length,
  strictPassedCount: financeProcessPageRegistry.filter(page => (
    !failures.some(row => row.pageCode === page.pageStepId)
  )).length,
  blockerCount: failures.length,
  guards: {
    filter_schema_has_display_labels: !failures.some(row => row.guard === 'filter_schema_has_display_labels'),
    filter_enum_values_not_exposed: !failures.some(row => row.guard === 'filter_enum_values_not_exposed'),
    business_dictionary_fields_use_select: !failures.some(row => row.guard === 'business_dictionary_fields_use_select'),
    advanced_filter_contract_consistent: !failures.some(row => row.guard === 'advanced_filter_contract_consistent'),
  },
  assertions,
  failures,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'filter-contract-guard-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
