export const PROCESS_RUNTIME_CONTRACT_VERSION = 'PCE-PROCESS-RUNTIME-CONTRACT-V1.0'

export function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0
}

export function isStringList(value, { allowEmpty = false } = {}) {
  return Array.isArray(value)
    && (allowEmpty || value.length > 0)
    && value.every(isNonEmptyString)
    && new Set(value).size === value.length
}

export function validationResult(contract, errors) {
  return Object.freeze({
    contract,
    valid: errors.length === 0,
    result: errors.length === 0 ? 'PASS' : 'FAIL',
    errors: Object.freeze([...errors]),
  })
}

export function assertValid(result) {
  if (!result.valid) throw new Error(`${result.contract}:${result.errors.join('|')}`)
  return true
}

export function freezeContract(value) {
  return Object.freeze({ ...value })
}

