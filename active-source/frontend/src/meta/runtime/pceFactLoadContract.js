export const PCE_FACT_LOAD_CONTRACT_VERSION =
  'PCE-FACT-LOAD-CONTRACT-V1.0'

export const PCE_FACT_LOAD_STATUSES = Object.freeze([
  'success',
  'loaded',
  'read_failed',
  'empty_valid',
])

export const PCE_FACT_LOAD_CONTEXT_UNAVAILABLE =
  'server-context-unavailable'

export const PCE_FACT_LOAD_ERROR_REQUIRED_FIELDS = Object.freeze([
  'factLoadStatus',
  'apiUrl',
  'httpStatus',
  'errorCode',
  'errorMessage',
  'loadedAt',
  'tenantId',
  'batchId',
])

const statusSet = new Set(PCE_FACT_LOAD_STATUSES)
let lastServerFactContext = Object.freeze({
  tenantId: PCE_FACT_LOAD_CONTEXT_UNAVAILABLE,
  batchId: PCE_FACT_LOAD_CONTEXT_UNAVAILABLE,
})

export class PceFactLoadError extends Error {
  constructor(message, factLoadFacts) {
    super(message)
    this.name = 'PceFactLoadError'
    this.factLoadFacts = Object.freeze({ ...factLoadFacts })
  }
}

function now() {
  return new Date().toISOString()
}

function nonEmptyText(value, fallback) {
  const normalized = String(value ?? '').trim()
  return normalized || fallback
}

function normalizedHttpStatus(value) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 && parsed <= 599
    ? parsed
    : 0
}

export function rememberPceServerFactContext(facts = {}) {
  const tenantId = nonEmptyText(
    facts.tenantId,
    lastServerFactContext.tenantId,
  )
  const batchId = nonEmptyText(
    facts.batchId,
    lastServerFactContext.batchId,
  )
  lastServerFactContext = Object.freeze({ tenantId, batchId })
  return lastServerFactContext
}

export function currentPceServerFactContext() {
  return lastServerFactContext
}

function resolveFailureContext({ tenantId, batchId } = {}) {
  return {
    tenantId: nonEmptyText(
      tenantId,
      lastServerFactContext.tenantId,
    ),
    batchId: nonEmptyText(
      batchId,
      lastServerFactContext.batchId,
    ),
  }
}

export function createReadFailedFactLoad({
  apiUrl = 'unavailable-api-url',
  httpStatus = 0,
  errorCode = 'FACT_READ_FAILED',
  errorMessage = '服务端事实读取失败',
  tenantId,
  batchId,
  loadedAt = now(),
} = {}) {
  const serverContext = resolveFailureContext({ tenantId, batchId })
  return Object.freeze({
    factLoadContractVersion: PCE_FACT_LOAD_CONTRACT_VERSION,
    factLoadStatus: 'read_failed',
    apiUrl: nonEmptyText(apiUrl, 'unavailable-api-url'),
    httpStatus: normalizedHttpStatus(httpStatus),
    errorCode: nonEmptyText(errorCode, 'FACT_READ_FAILED'),
    errorMessage: nonEmptyText(errorMessage, '服务端事实读取失败'),
    loadedAt: nonEmptyText(loadedAt, now()),
    tenantId: serverContext.tenantId,
    batchId: serverContext.batchId,
  })
}

function incompleteFactLoadError(
  facts,
  context,
  expectedApiUrl,
  failures,
) {
  const failed = createReadFailedFactLoad({
    apiUrl: facts?.apiUrl || expectedApiUrl,
    httpStatus: facts?.httpStatus,
    errorCode: 'FACT_LOAD_CONTRACT_INCOMPLETE',
    errorMessage:
      `${context}: invalid fields ${failures.join(',')}`,
    loadedAt: facts?.loadedAt,
    tenantId: facts?.tenantId,
    batchId: facts?.batchId,
  })
  return new PceFactLoadError(
    `${context}: fact load contract is incomplete`,
    failed,
  )
}

export function assertPceFactLoadFacts(
  facts,
  context = 'fact-load',
  expectedApiUrl = '',
) {
  if (!facts || typeof facts !== 'object') {
    throw incompleteFactLoadError(
      facts,
      context,
      expectedApiUrl,
      ['factLoadFacts'],
    )
  }

  const failures = []
  for (const field of PCE_FACT_LOAD_ERROR_REQUIRED_FIELDS) {
    if (!Object.hasOwn(facts, field)) failures.push(field)
  }
  if (
    facts.factLoadContractVersion !== PCE_FACT_LOAD_CONTRACT_VERSION
  ) {
    failures.push('factLoadContractVersion')
  }
  if (!statusSet.has(facts.factLoadStatus)) {
    failures.push('factLoadStatus:value')
  }
  if (
    !Number.isInteger(Number(facts.httpStatus))
    || Number(facts.httpStatus) < 0
    || Number(facts.httpStatus) > 599
  ) {
    failures.push('httpStatus:value')
  }
  for (const field of ['apiUrl', 'loadedAt', 'tenantId', 'batchId']) {
    if (!String(facts[field] ?? '').trim()) failures.push(`${field}:empty`)
  }
  if (facts.factLoadStatus === 'read_failed') {
    for (const field of PCE_FACT_LOAD_ERROR_REQUIRED_FIELDS) {
      if (
        field !== 'httpStatus'
        && !String(facts[field] ?? '').trim()
      ) {
        failures.push(`${field}:empty`)
      }
    }
  }
  if (failures.length) {
    throw incompleteFactLoadError(
      facts,
      context,
      expectedApiUrl,
      [...new Set(failures)],
    )
  }

  const normalized = Object.freeze({
    ...facts,
    httpStatus: Number(facts.httpStatus),
  })
  rememberPceServerFactContext(normalized)
  return normalized
}

export function readPceFactLoadEnvelope(
  envelope,
  expectedApiUrl,
  context = 'fact-load',
) {
  if (envelope?.success === false) {
    const failed = assertPceFactLoadFacts(
      envelope.factLoadFacts,
      context,
      expectedApiUrl,
    )
    throw new PceFactLoadError(failed.errorMessage, failed)
  }

  const payload = envelope?.success === true ? envelope.data : envelope
  const data = payload?.data ?? payload ?? {}
  const factLoadFacts = assertPceFactLoadFacts(
    data.factLoadFacts || data,
    context,
    expectedApiUrl,
  )
  if (
    expectedApiUrl
    && factLoadFacts.apiUrl !== expectedApiUrl
  ) {
    const failed = createReadFailedFactLoad({
      apiUrl: expectedApiUrl,
      httpStatus: factLoadFacts.httpStatus,
      errorCode: 'FACT_API_URL_MISMATCH',
      errorMessage:
        `${context}: expected ${expectedApiUrl}, received ${factLoadFacts.apiUrl}`,
      tenantId: factLoadFacts.tenantId,
      batchId: factLoadFacts.batchId,
    })
    throw new PceFactLoadError(failed.errorMessage, failed)
  }
  return {
    payload,
    data,
    factLoadFacts,
  }
}

export function factLoadFailureFromError(
  error,
  apiUrl,
  previousFactLoadFacts = null,
) {
  if (previousFactLoadFacts) {
    rememberPceServerFactContext(previousFactLoadFacts)
  }
  if (error?.factLoadFacts) {
    try {
      return assertPceFactLoadFacts(
        error.factLoadFacts,
        'fact-load-error',
        apiUrl,
      )
    } catch (contractError) {
      if (contractError?.factLoadFacts) {
        return contractError.factLoadFacts
      }
    }
  }
  return createReadFailedFactLoad({
    apiUrl,
    httpStatus: Number(error?.response?.status || 0),
    errorCode: error?.code || 'FACT_READ_FAILED',
    errorMessage: error?.message || '服务端事实读取失败',
  })
}

export function factLoadResultCount(factLoadFacts, count) {
  if (!factLoadFacts || factLoadFacts.factLoadStatus === 'read_failed') {
    return null
  }
  return Number(count)
}

export function factLoadPassed(factLoadFacts, businessPassed = true) {
  return (
    Boolean(factLoadFacts)
    && factLoadFacts.factLoadStatus !== 'read_failed'
    && businessPassed === true
  )
}
