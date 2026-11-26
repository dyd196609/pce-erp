export const REMOTE_SELECT_OPTIONS_PROVIDER_VERSION = 'V1.14.2.8.18.14'

const optionOf = value => Object.freeze(typeof value === 'object'
  ? { value: value.value, label: String(value.label ?? value.value ?? '') }
  : { value, label: String(value) })

export function createRemoteSelectOptionsProvider({
  providerCode,
  limit = 50,
  loadRows = null,
  valueField = '',
  codeField = '',
  nameField = '',
} = {}) {
  if (!providerCode) throw new Error('REMOTE_SELECT_PROVIDER_CODE_REQUIRED')
  let cachedRows = null
  let loadPromise = null

  async function providerRows(fallbackRows = []) {
    if (typeof loadRows !== 'function') return fallbackRows
    if (cachedRows) return cachedRows
    if (!loadPromise) {
      loadPromise = Promise.resolve(loadRows()).then((rows) => {
        if (!Array.isArray(rows)) throw new Error(`REMOTE_SELECT_PROVIDER_ROWS_INVALID:${providerCode}`)
        cachedRows = rows
        return rows
      }).finally(() => { loadPromise = null })
    }
    return loadPromise
  }

  return Object.freeze({ providerCode, sourceMode: 'provider_facts',
    async searchOptions({ query = '', field = {}, rows = [] } = {}) {
      const sourceKey = field.sourceKey || field.field
      const normalizedQuery = String(query).trim().toLowerCase()
      const sourceRows = await providerRows(rows)
      const optionRows = sourceRows.flatMap((row) => {
        if (valueField) {
          const value = row?.[valueField]
          if (value === '' || value == null) return []
          const code = String(row?.[codeField] ?? value)
          const name = String(row?.[nameField] ?? '').trim()
          return [{ value, label: name ? `${code} · ${name}` : code }]
        }
        const values = Array.isArray(row?.[sourceKey]) ? row[sourceKey] : [row?.[sourceKey]]
        return values.filter(value => value !== '' && value != null)
      })
      const unique = new Map(optionRows.map((value) => {
        const option = optionOf(value)
        return [String(option.value), option]
      }))
      const options = [...unique.values()]
      return Object.freeze(options.filter(option => !normalizedQuery
        || option.label.toLowerCase().includes(normalizedQuery)
        || String(option.value).toLowerCase().includes(normalizedQuery)).slice(0, limit))
    },
  })
}

async function loadEnterpriseMasterRows(entityCode) {
  const { enterpriseMasterDataApi } = await import('@/api/enterpriseMasterData.js')
  const response = await enterpriseMasterDataApi.facts(entityCode)
  const payload = response?.data || response || {}
  if (payload?.factLoadFacts?.factLoadStatus !== 'success' || !Array.isArray(payload.rows)) {
    throw new Error(`REMOTE_SELECT_MASTER_RUNTIME_UNAVAILABLE:${entityCode}`)
  }
  return payload.rows
}

export const currentResultRemoteSelectOptionsProvider = createRemoteSelectOptionsProvider({
  providerCode: 'CurrentResultDropdownRuntime',
})

export const supplierMasterRemoteSelectOptionsProvider = createRemoteSelectOptionsProvider({
  providerCode: 'SupplierMasterRuntimeAdapter',
  loadRows: () => loadEnterpriseMasterRows('suppliers'),
  valueField: 'supplierCode',
  codeField: 'supplierCode',
  nameField: 'supplierName',
})

export const materialMasterRemoteSelectOptionsProvider = createRemoteSelectOptionsProvider({
  providerCode: 'MaterialMasterRuntimeAdapter',
  loadRows: () => loadEnterpriseMasterRows('materials'),
  valueField: 'materialCode',
  codeField: 'materialCode',
  nameField: 'materialName',
})
