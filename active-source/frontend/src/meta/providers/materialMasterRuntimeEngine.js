export const MATERIAL_RUNTIME_STATUS = Object.freeze({
  IDLE: 'IDLE',
  LOADED: 'LOADED',
  AUTH_REQUIRED: 'AUTH_REQUIRED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  NETWORK_ERROR: 'NETWORK_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  DATA_ERROR: 'DATA_ERROR',
  DEMO_ISOLATED: 'DEMO_ISOLATED',
})

export class MaterialMasterRuntimeError extends Error {
  constructor(code, message, details = {}) {
    super(message)
    this.name = 'MaterialMasterRuntimeError'
    this.code = code
    this.details = details
  }
}

function failureCode(status, fallbackCode = '') {
  if (status === 401) return MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED
  if (status === 403) return MATERIAL_RUNTIME_STATUS.PERMISSION_DENIED
  if (status >= 500) return MATERIAL_RUNTIME_STATUS.SERVER_ERROR
  if (!status || fallbackCode === 'NETWORK_READ_FAILED') return MATERIAL_RUNTIME_STATUS.NETWORK_ERROR
  return MATERIAL_RUNTIME_STATUS.DATA_ERROR
}

export function materialFactsPayload(response) {
  let payload = response
  for (let depth = 0; depth < 4; depth += 1) {
    const status = Number(payload?.meta?.status || payload?.status || 0)
    if (payload?.success === false) {
      const code = failureCode(status, payload?.error?.code || payload?.errorCode)
      throw new MaterialMasterRuntimeError(
        code,
        payload?.error?.message || payload?.errorMessage || `MaterialMaster request failed (${code})`,
        { httpStatus: status },
      )
    }
    if (payload?.factLoadFacts || Array.isArray(payload?.rows)) break
    if (!payload || typeof payload !== 'object' || !payload.data || typeof payload.data !== 'object') break
    payload = payload.data
  }

  if (payload?.factLoadFacts?.factLoadStatus !== 'success' || !Array.isArray(payload?.rows)) {
    throw new MaterialMasterRuntimeError(
      MATERIAL_RUNTIME_STATUS.DATA_ERROR,
      'MaterialMaster response violates the runtime fact contract',
    )
  }
  return payload
}

export function normalizeMaterialMasterModel(model = {}) {
  const materialCode = model.materialCode || model.code || ''
  const materialName = model.materialName || model.name || ''
  return {
    ...model,
    id: model.id,
    code: materialCode,
    name: materialName,
    specification: model.specification || '',
    unit: model.unit || '',
    category: model.category || '',
    materialType: model.materialType || model.type || '',
    status: model.status || model.businessStatus || 'enabled',
    materialCode,
    materialName,
    materialSourceTrace: model.materialSourceTrace || {
      source: 'MaterialMaster',
      database: 'material',
      maintenanceEntry: '企业基础数据 → 物料数据',
    },
  }
}

function contextKey(context = {}) {
  return [context.mode || 'enterprise', context.tenantId || '', context.principalId || ''].join(':')
}

export function createMaterialMasterRuntimeEngine({ fetchFacts }) {
  let models = []
  let activeContextKey = ''
  let generation = 0
  let inFlight = null
  let status = MATERIAL_RUNTIME_STATUS.IDLE

  function copyModels() {
    return models.map((model) => ({
      ...model,
      materialSourceTrace: { ...model.materialSourceTrace },
    }))
  }

  function switchContext(context = {}) {
    const nextKey = contextKey(context)
    if (nextKey === activeContextKey) return
    activeContextKey = nextKey
    generation += 1
    models = []
    inFlight = null
    status = MATERIAL_RUNTIME_STATUS.IDLE
  }

  function clear(context = {}) {
    switchContext(context)
    generation += 1
    models = []
    inFlight = null
    status = MATERIAL_RUNTIME_STATUS.IDLE
  }

  async function load({ force = false, context = {} } = {}) {
    switchContext(context)
    if (context.authenticated === false) {
      models = []
      status = MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED
      return copyModels()
    }
    if (context.mode === 'demo') {
      models = []
      status = MATERIAL_RUNTIME_STATUS.DEMO_ISOLATED
      return copyModels()
    }
    if (!force && status === MATERIAL_RUNTIME_STATUS.LOADED) return copyModels()
    if (inFlight?.contextKey === activeContextKey) return inFlight.promise

    const requestGeneration = generation
    const requestContextKey = activeContextKey
    const promise = Promise.resolve()
      .then(() => fetchFacts())
      .then(materialFactsPayload)
      .then((payload) => {
        const normalized = payload.rows.map(normalizeMaterialMasterModel)
        if (requestGeneration === generation && requestContextKey === activeContextKey) {
          models = normalized
          status = MATERIAL_RUNTIME_STATUS.LOADED
        }
        return requestGeneration === generation ? copyModels() : []
      })
      .catch((error) => {
        const normalizedError = error instanceof MaterialMasterRuntimeError
          ? error
          : new MaterialMasterRuntimeError(
            error?.response ? failureCode(Number(error.response.status || 0)) : MATERIAL_RUNTIME_STATUS.NETWORK_ERROR,
            error?.message || 'MaterialMaster network request failed',
          )
        if (requestGeneration === generation) status = normalizedError.code
        throw normalizedError
      })
      .finally(() => {
        if (inFlight?.promise === promise) inFlight = null
      })
    inFlight = { contextKey: requestContextKey, promise }
    return promise
  }

  return {
    load,
    clear,
    models: copyModels,
    state: () => ({ status, contextKey: activeContextKey, count: models.length }),
  }
}
