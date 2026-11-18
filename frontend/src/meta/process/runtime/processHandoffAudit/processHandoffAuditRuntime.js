const present = value => value !== undefined && value !== null && value !== ''
  && (!Array.isArray(value) || value.length > 0)

function readPath(object, path) {
  return String(path).split('.').reduce((value, key) => value?.[key], object)
}

export function auditProcessHandoff(contract, artifacts = {}) {
  const sourceObject = artifacts.sourceObject
  const context = artifacts.context
  const targetObject = artifacts.targetObject
  const mappedFacts = artifacts.mappedFacts || context || {}
  const checks = Object.freeze({
    sourceObject: Boolean(sourceObject) && (contract.validateSource?.(sourceObject) ?? true),
    contextMapping: Boolean(context) && (contract.validateContext?.(sourceObject, context, targetObject) ?? true),
    targetObject: Boolean(targetObject) && (contract.validateTarget?.(targetObject) ?? true),
    requiredFields: contract.requiredFields.every(field => present(readPath(mappedFacts, field))),
    stateTransition: Boolean(artifacts.stateTransition)
      && (contract.validateStateTransition?.(artifacts.stateTransition, sourceObject, targetObject) ?? true),
    handoffContract: contract.handoffContract.fromNode === contract.sourceNode
      && contract.handoffContract.toNode === contract.targetNode,
  })
  const valid = Object.values(checks).every(Boolean)
  return Object.freeze({ auditCode: contract.auditCode, result: valid ? 'PASS' : 'FAIL', valid, checks })
}

export function auditProcessHandoffChain(entries = []) {
  const audits = Object.freeze(entries.map(entry => auditProcessHandoff(entry.contract, entry.artifacts)))
  const valid = audits.length > 0 && audits.every(item => item.valid)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, auditCount: audits.length, audits })
}

