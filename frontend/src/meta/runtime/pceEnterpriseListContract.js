import { computed, reactive, ref, getCurrentInstance, onBeforeUnmount, watch } from 'vue'
import {useRoute} from 'vue-router'
import {workPresentation,presentationRoutePath} from './workPresentationContext.js'
import { normalizeListFilterSchema } from './listFilterRuntime.js'

const resolveRuntimeOption = (option, fallback) => (
  typeof option === 'function' ? option() : (option ?? fallback)
)

export const PCE_ENTERPRISE_LIST_CONTRACT_VERSION = 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1'
export const PCE_LIST_DISPLAY_GOVERNANCE_VERSION = 'V1.14.2.8.4.27.2.2'
export const PCE_LIST_REFRESH_CONTRACT_VERSION = 'LIST-REFRESH-CONTRACT-001'

export const PCE_TECHNICAL_LIST_FIELDS = Object.freeze([
  'objectId',
  'sourceRelations',
  'gateId',
  'api',
  'apiUrl',
  'runtimeDiagnostics',
  'json',
  'statusCode',
])

export function isPceTechnicalListField(field = '') {
  const normalized = String(field).replace(/[^a-z0-9]/gi, '').toLowerCase()
  return PCE_TECHNICAL_LIST_FIELDS.some(item => (
    String(item).replace(/[^a-z0-9]/gi, '').toLowerCase() === normalized
  ))
}

export function summarizePceSourceRelation(value, count = 0) {
  const sourceCount = Number(count || 0)
  if (sourceCount > 1) return `来源数量：${sourceCount}`
  if (value || sourceCount === 1) return '已关联Gate'
  return '未关联Gate'
}

export function isPceLongListText(value, threshold = 18) {
  return String(value ?? '').length > threshold
}

export const PCE_ENTERPRISE_FILTER_TYPES = Object.freeze([
  'text',
  'select',
  'remote-select',
  'date',
  'daterange',
  'number',
  'numberRange',
  'boolean',
])

export const PCE_ENTERPRISE_LIST_CAPABILITIES = Object.freeze({
  search: true,
  advancedFilter: true,
  sort: true,
  export: true,
  selection: true,
  horizontalScroll: true,
  fixedHeader: true,
  internalVerticalScroll: true,
  pagination: true,
  frozenLeft: Object.freeze(['selection', 'index', 'primaryNo']),
  frozenRight: Object.freeze(['actionColumn']),
  actionColumn: true,
  defaultActionColumn: true,
  unifiedFilterSchema: true,
  listContainerRuntime: true,
})

export const PCE_ENTERPRISE_LIST_SHELL_KEY = Symbol('pce-enterprise-list-shell')

export const PCE_ENTERPRISE_LIST_SHELL_DEFAULTS = Object.freeze({
  viewportMaxHeight: 440,
  defaultPageSize: 20,
  pageSizes: Object.freeze([10, 20, 50, 100]),
})

export function resolvePceEnterprisePageJump(value, totalPages, currentPage) {
  const text = String(value ?? '').trim()
  const page = Number(text)
  return /^[0-9]+$/.test(text) && Number.isSafeInteger(page)
    && page >= 1 && page <= totalPages && page !== currentPage ? page : null
}

export function paginatePceEnterpriseRows(rows = [], page = 1, pageSize = 20) {
  const safeRows = Array.isArray(rows) ? rows : []
  const safePageSize = Math.max(1, Math.trunc(Number(pageSize)) || 20)
  const totalPages = Math.max(1, Math.ceil(safeRows.length / safePageSize))
  const currentPage = Math.min(Math.max(1, Math.trunc(Number(page)) || 1), totalPages)
  const start = (currentPage - 1) * safePageSize
  return {
    rows: safeRows.slice(start, start + safePageSize),
    total: safeRows.length,
    currentPage,
    pageSize: safePageSize,
    totalPages,
  }
}

export const PCE_ENTERPRISE_LIST_FACT_SURFACES = Object.freeze({
  api: true,
  page: true,
  diagnostic: true,
  strictFacts: true,
})

export function createPceEnterpriseListContract(input = {}) {
  const contract = {
    contractVersion: PCE_ENTERPRISE_LIST_CONTRACT_VERSION,
    pageCode: String(input.pageCode || ''),
    pageType: input.pageType || 'list',
    title: String(input.title || ''),
    moduleCode: String(input.moduleCode || ''),
    capabilities: {
      ...PCE_ENTERPRISE_LIST_CAPABILITIES,
      ...(input.capabilities || {}),
    },
    facts: { ...PCE_ENTERPRISE_LIST_FACT_SURFACES },
    status: {
      technicalCodeHidden: true,
      businessLabelRequired: true,
    },
    display: {
      governanceVersion: PCE_LIST_DISPLAY_GOVERNANCE_VERSION,
      businessSummaryOnly: true,
      technicalFieldsHidden: true,
      rowDensity: 'compact',
      longTextMode: 'ellipsis-tooltip-detail',
      diagnosticDefaultCollapsed: true,
    },
    safety: {
      dangerActionBlocked: true,
    },
  }
  return assertPceEnterpriseListContract(contract)
}

export function assertPceEnterpriseListContract(contract) {
  const requiredText = ['pageCode', 'pageType', 'title', 'moduleCode']
  for (const field of requiredText) {
    if (!String(contract?.[field] || '').trim()) {
      throw new Error(`PCE enterprise list contract missing ${field}`)
    }
  }
  const requiredCapabilities = [
    'search',
    'advancedFilter',
    'sort',
    'export',
    'selection',
    'horizontalScroll',
    'fixedHeader',
    'internalVerticalScroll',
    'pagination',
    'actionColumn',
  ]
  for (const capability of requiredCapabilities) {
    if (contract.capabilities?.[capability] !== true) {
      throw new Error(`PCE enterprise list capability disabled: ${capability}`)
    }
  }
  for (const surface of Object.keys(PCE_ENTERPRISE_LIST_FACT_SURFACES)) {
    if (contract.facts?.[surface] !== true) {
      throw new Error(`PCE enterprise list fact surface missing: ${surface}`)
    }
  }
  if (
    contract.status?.technicalCodeHidden !== true
    || contract.status?.businessLabelRequired !== true
    || contract.display?.businessSummaryOnly !== true
    || contract.display?.technicalFieldsHidden !== true
    || contract.display?.rowDensity !== 'compact'
    || contract.display?.longTextMode !== 'ellipsis-tooltip-detail'
    || contract.display?.diagnosticDefaultCollapsed !== true
    || contract.safety?.dangerActionBlocked !== true
  ) {
    throw new Error('PCE enterprise list status or safety contract is incomplete')
  }
  return Object.freeze(contract)
}

function isEmpty(value) {
  return value === '' || value === null || value === undefined
}

export function assertPceEnterpriseFilterSchema(schema = []) {
  const normalized = normalizeListFilterSchema(schema)
  for (const field of normalized) {
    if (!String(field?.field || '').trim()) {
      throw new Error('PCE enterprise list filter field is missing')
    }
    if (!PCE_ENTERPRISE_FILTER_TYPES.includes(field.filterType)) {
      throw new Error(`PCE enterprise list filterType invalid: ${field.field}`)
    }
    if (['select', 'remote-select'].includes(field.filterType)
      && (!Array.isArray(field.options) || field.options.length === 0)
      && !field.optionsProvider) {
      throw new Error(`PCE enterprise select options missing: ${field.field}`)
    }
  }
  return normalized
}

export function buildPceEnterpriseFilterApiParams(schema = [], filters = {}) {
  schema = assertPceEnterpriseFilterSchema(schema)
  const params = {}
  for (const field of schema) {
    const value = filters[field.field]
    if (isEmpty(value) || (Array.isArray(value) && value.length === 0)) continue
    if (field.filterType === 'daterange' || field.filterType === 'numberRange') {
      const [from, to] = Array.isArray(value) ? value : []
      if (!isEmpty(from)) params[field.apiFrom || `${field.field}From`] = from
      if (!isEmpty(to)) params[field.apiTo || `${field.field}To`] = to
      continue
    }
    params[field.apiParam || field.field] = value
  }
  return params
}

function resolveFieldValue(row, field, resolver) {
  if (typeof resolver === 'function') return resolver(row, field)
  return row?.[field.sourceKey || field.field]
}

function matchesFilter(actual, expected, field) {
  if (isEmpty(expected) || (Array.isArray(expected) && expected.length === 0)) return true
  if (field.filterType === 'daterange' && Array.isArray(expected)) {
    const value = String(actual || '')
    const normalize = boundary => value.length === 7 ? String(boundary || '').slice(0, 7) : String(boundary || '')
    return (!expected[0] || value >= normalize(expected[0]))
      && (!expected[1] || value <= normalize(expected[1]))
  }
  if (field.filterType === 'numberRange' && Array.isArray(expected)) {
    const value = Number(actual)
    return (!Number.isFinite(Number(expected[0])) || value >= Number(expected[0]))
      && (!Number.isFinite(Number(expected[1])) || value <= Number(expected[1]))
  }
  if (Array.isArray(expected)) {
    if (Array.isArray(actual)) return actual.some(value => expected.some(item => String(value) === String(item)))
    return expected.some(item => String(actual ?? '') === String(item))
  }
  if (Array.isArray(actual)) return actual.some(value => matchesFilter(value, expected, field))
  if (field.filterType === 'text') {
    return String(actual ?? '').toLowerCase().includes(String(expected).toLowerCase())
  }
  if (field.matchMode === 'contains') {
    return String(actual ?? '').toLowerCase().includes(String(expected).toLowerCase())
  }
  if (field.field.endsWith('From')) return String(actual || '') >= String(expected)
  if (field.field.endsWith('To')) return String(actual || '') <= String(expected)
  return String(actual ?? '') === String(expected)
}

function csvCell(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

export function usePceEnterpriseListRuntime(options) {
  const rows = options.rows
  const filterSchema = assertPceEnterpriseFilterSchema(options.filterSchema || [])
  const quickSearch = ref('')
  const appliedSearch = ref('')
  const advancedVisible = ref(false)
  const selectedRows = ref([])
  const sortState = reactive({ prop: '', order: '' })
  const tableRef = ref(null)
  const filters = reactive(Object.fromEntries(filterSchema.map(field => [
    field.field,
    ['daterange', 'numberRange'].includes(field.filterType) ? [] : '',
  ])))
  const owner=workPresentation.epoch(),route=getCurrentInstance()?useRoute():null
  const contextKey=route?`filters:${presentationRoutePath(route.fullPath)}:${options.pageCode}`:null
  const currentContextKey=()=>options.presentationScope?`filters:${presentationRoutePath(options.presentationScope())}:${options.pageCode}`:contextKey
  const saved=contextKey?workPresentation.read(contextKey):null
  if(saved){quickSearch.value=saved.quickSearch;appliedSearch.value=saved.appliedSearch;advancedVisible.value=saved.advancedVisible;Object.assign(sortState,saved.sortState);for(const key of Object.keys(filters))if(key in saved.filters)filters[key]=saved.filters[key]}
  const savePresentation=()=>{const key=currentContextKey();if(key)workPresentation.save(key,{quickSearch:quickSearch.value,appliedSearch:appliedSearch.value,advancedVisible:advancedVisible.value,sortState:{...sortState},filters:{...filters}},owner)}
  if(contextKey)onBeforeUnmount(savePresentation)
  if(contextKey&&typeof window!=='undefined'){
    const saveOnPageHide=()=>{if(workPresentation.persistent(currentContextKey()))savePresentation()}
    window.addEventListener('pagehide',saveOnPageHide);window.addEventListener('beforeunload',saveOnPageHide)
    onBeforeUnmount(()=>{window.removeEventListener('pagehide',saveOnPageHide);window.removeEventListener('beforeunload',saveOnPageHide)})
  }
  const restorePresentation=()=>{
    const key=currentContextKey();if(!workPresentation.persistent(key))return
    const value=workPresentation.read(key);if(!value)return
    quickSearch.value=value.quickSearch??'';appliedSearch.value=value.appliedSearch??'';advancedVisible.value=value.advancedVisible??false
    Object.assign(sortState,value.sortState||{prop:'',order:''});for(const field of Object.keys(filters))if(field in (value.filters||{}))filters[field]=value.filters[field]
  }
  if(options.presentationScope)watch(currentContextKey,restorePresentation,{flush:'post'})
  if(contextKey && typeof window!=='undefined'){
    const resetIdentityPresentation=()=>{clearFilters();clearSort();selectedRows.value=[];advancedVisible.value=false}
    window.addEventListener('pce:authentication-changed',resetIdentityPresentation)
    onBeforeUnmount(()=>window.removeEventListener('pce:authentication-changed',resetIdentityPresentation))
  }
  const activeFilterCount = computed(() => Object.values(filters).filter(
    value => !isEmpty(value) && (!Array.isArray(value) || value.length > 0),
  ).length)
  const sortText = computed(() => (
    sortState.prop
      ? `${sortState.prop} ${sortState.order === 'descending' ? '降序' : '升序'}`
      : '默认业务顺序'
  ))
  const filteredRows = computed(() => {
    const keyword = appliedSearch.value.trim().toLowerCase()
    let result = (rows.value || []).filter(row => {
      if (keyword) {
        const searchable = resolveRuntimeOption(options.searchFields, []).map(field => (
          typeof field === 'function' ? field(row) : row?.[field]
        ))
        if (!searchable.some(value => String(value || '').toLowerCase().includes(keyword))) {
          return false
        }
      }
      return filterSchema.every(field => matchesFilter(
        resolveFieldValue(row, field, options.filterValueResolver),
        filters[field.field],
        field,
      ))
    })
    if (sortState.prop && sortState.order) {
      const direction = sortState.order === 'descending' ? -1 : 1
      result = [...result].sort((left, right) => (
        String(left?.[sortState.prop] ?? '').localeCompare(
          String(right?.[sortState.prop] ?? ''),
          'zh-CN',
          { numeric: true },
        ) * direction
      ))
    }
    return result
  })

  function applySearch() {
    appliedSearch.value = quickSearch.value
  }

  function updateFilter(field, value) {
    if (Object.hasOwn(filters, field)) filters[field] = value ?? ''
  }

  function clearFilters() {
    quickSearch.value = ''
    appliedSearch.value = ''
    for (const field of filterSchema) {
      filters[field.field] = ['daterange', 'numberRange'].includes(field.filterType) ? [] : ''
    }
  }

  function handleSort({ prop, order } = {}) {
    sortState.prop = prop || ''
    sortState.order = order || ''
  }

  function clearSort() {
    handleSort()
    tableRef.value?.clearSort?.()
  }

  function handleSelectionChange(selection) {
    selectedRows.value = selection || []
  }

  function clearSelection() {
    selectedRows.value = []
    tableRef.value?.clearSelection?.()
  }

  function exportCurrent() {
    const columns = resolveRuntimeOption(options.exportColumns, [])
    options.onExportStage?.({ stage: 'runtime-received', rowCount: filteredRows.value.length, columnCount: columns.length })
    const lines = [
      columns.map(column => column.label),
      ...filteredRows.value.map(row => columns.map(column => (
        typeof column.value === 'function'
          ? column.value(row)
          : row?.[column.field]
      ))),
    ]
    const csv = lines.map(line => line.map(csvCell).join(',')).join('\n')
    options.onExportStage?.({ stage: 'csv-prepared', rowCount: filteredRows.value.length, columnCount: columns.length })
    const url = URL.createObjectURL(
      new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }),
    )
    options.onExportStage?.({ stage: 'blob-url-created', rowCount: filteredRows.value.length, columnCount: columns.length })
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = resolveRuntimeOption(
      options.exportFileName,
      `${options.pageCode || 'pce-list'}.csv`,
    )
    anchor.hidden = true
    document.body.appendChild(anchor)
    anchor.click()
    options.onExportStage?.({ stage: 'download-click-dispatched', rowCount: filteredRows.value.length, columnCount: columns.length })
    window.setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(url)
    }, 0)
    return { csv, rowCount: filteredRows.value.length, columnCount: columns.length, fileName: anchor.download }
  }

  return {
    quickSearch,
    appliedSearch,
    advancedVisible,
    selectedRows,
    sortState,
    tableRef,
    filters,
    activeFilterCount,
    sortText,
    filteredRows,
    normalizedFilterSchema: filterSchema,
    apiFilterParams: computed(() => buildPceEnterpriseFilterApiParams(filterSchema, filters)),
    applySearch,
    updateFilter,
    clearFilters,
    handleSort,
    clearSort,
    handleSelectionChange,
    clearSelection,
    exportCurrent,
    savePresentation,
    restorePresentation,
  }
}

// 公共列表刷新必须调用注册的数据提供器，并保留筛选、排序和分页大小。
export function createPceListRefreshRuntime({ provider, replaceRows, currentResultCount, totalCount } = {}) {
  if (typeof provider !== 'function' || typeof replaceRows !== 'function') {
    throw new Error('PCE_LIST_REFRESH_PROVIDER_REQUIRED')
  }
  const refreshing = ref(false)
  const refreshError = ref('')
  const lastRefreshedAt = ref('')
  const requestCount = ref(0)

  async function refresh() {
    if (refreshing.value) return null
    refreshing.value = true
    refreshError.value = ''
    try {
      const payload = await provider({ force: true })
      const rows = Array.isArray(payload) ? payload : payload?.rows
      if (!Array.isArray(rows)) throw new Error('服务端未返回有效列表数据')
      replaceRows(rows, payload)
      requestCount.value += 1
      lastRefreshedAt.value = new Date().toISOString()
      return Object.freeze({
        contractVersion: PCE_LIST_REFRESH_CONTRACT_VERSION,
        rows,
        currentResultCount: Number(currentResultCount?.value ?? rows.length),
        totalCount: Number(totalCount?.value ?? rows.length),
        requestCount: requestCount.value,
      })
    } catch (error) {
      refreshError.value = error?.message || '未知错误'
      throw error
    } finally {
      refreshing.value = false
    }
  }

  return Object.freeze({
    contractVersion: PCE_LIST_REFRESH_CONTRACT_VERSION,
    refreshing, refreshError, lastRefreshedAt, requestCount, refresh,
  })
}
