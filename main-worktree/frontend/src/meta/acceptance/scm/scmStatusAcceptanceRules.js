import { listScmAcceptanceObjects, resolveScmAcceptanceObject } from './scmAcceptanceObjectModel.js'

export const SCM_STATUS_ACCEPTANCE_VERSION = 'V1.14.2.8.4.23'

export const SCM_STATUS_ACCEPTANCE_RULES = Object.freeze(listScmAcceptanceObjects().map(object => Object.freeze({
  objectCode: object.objectCode,
  statusField: object.statusField,
  lifecycle: object.lifecycle,
  allowedTransitions: Object.freeze(object.lifecycle.slice(0, -1).map((from, index) => Object.freeze({ from, to: object.lifecycle[index + 1] }))),
  transitionPolicy: 'adjacent_forward_only',
  reverseTransitionForbidden: true,
})))

export function evaluateScmStatusTransition({ objectCode, fromStatus, toStatus } = {}) {
  const object = resolveScmAcceptanceObject(objectCode)
  if (!object || !fromStatus || !toStatus) return Object.freeze({ result: 'UNKNOWN', reason: 'STATUS_FACT_MISSING_OR_OBJECT_UNKNOWN' })
  const fromIndex = object.lifecycle.indexOf(fromStatus)
  const toIndex = object.lifecycle.indexOf(toStatus)
  if (fromIndex < 0 || toIndex < 0) return Object.freeze({ result: 'UNKNOWN', reason: 'STATUS_NOT_IN_ACCEPTANCE_MODEL' })
  const pass = toIndex === fromIndex + 1
  return Object.freeze({ result: pass ? 'PASS' : 'FAIL', reason: pass ? '' : toIndex <= fromIndex ? 'REVERSE_OR_STAGNANT_TRANSITION_FORBIDDEN' : 'NON_ADJACENT_TRANSITION_FORBIDDEN' })
}

