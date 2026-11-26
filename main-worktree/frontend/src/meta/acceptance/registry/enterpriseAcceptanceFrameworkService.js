import { createRun, execute } from '../runner/enterprisePageAcceptanceRunner.js'
import {
  getEnterpriseAcceptanceModuleRegistration,
  validateEnterpriseAcceptanceRegistration,
} from './enterpriseAcceptanceRegistry.js'
import { activateAcceptanceFramework } from './enterpriseAcceptanceActivator.js'

export const ENTERPRISE_ACCEPTANCE_FRAMEWORK_SERVICE_VERSION = 'V1.14.2.8.4.24'

const normalizeModuleCode = input => String(typeof input === 'string' ? input : input?.moduleCode || '').trim().toUpperCase()

export function validateModuleRegistration(input) {
  const directRegistration = input?.registration || (input?.moduleName ? input : null)
  const registration = directRegistration || getEnterpriseAcceptanceModuleRegistration(normalizeModuleCode(input))
  return validateEnterpriseAcceptanceRegistration(registration)
}

export function getModuleAcceptanceProfile(input) {
  const moduleCode = normalizeModuleCode(input)
  const registration = getEnterpriseAcceptanceModuleRegistration(moduleCode)
  const validation = validateEnterpriseAcceptanceRegistration(registration)
  if (!validation.valid) return Object.freeze({ module: moduleCode, moduleCode, ready: false, validation })
  return Object.freeze({
    module: moduleCode,
    moduleCode,
    moduleName: registration.moduleName,
    ready: true,
    objects: registration.objects.length,
    templates: registration.templates.length,
    rules: registration.rules.length,
    collectors: registration.evidenceCollectors.length,
    objectCodes: registration.objects,
    objectRegistrations: registration.objectRegistrations || Object.freeze([]),
    acceptanceProfiles: registration.objectRegistrations || Object.freeze([]),
    ruleProfiles: registration.ruleProfiles || Object.freeze([]),
    templateCodes: registration.templates,
    ruleSetCodes: registration.rules,
    collectorCodes: registration.evidenceCollectors,
    collectorAliases: registration.collectorAliases || Object.freeze({}),
    pages: registration.pages,
    runner: registration.runner,
    archive: registration.archive,
    readOnly: true,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export function activateModule(input) {
  const moduleCode = normalizeModuleCode(input)
  const activation = activateAcceptanceFramework({ moduleCode }, input?.registration ? { registration: input.registration } : {})
  return Object.freeze({
    success: activation.activated,
    moduleCode,
    activationStatus: activation.activationStatus,
    profile: activation.activated ? getModuleAcceptanceProfile(moduleCode) : null,
    activation,
    error: activation.error || null,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export function prepareModuleAcceptanceRun({ moduleCode, runInput = {} } = {}) {
  const activated = activateModule({ moduleCode })
  if (!activated.success) return Object.freeze({ success: false, activationStatus: activated.activationStatus, error: activated.error })
  const run = createRun({
    ...runInput,
    moduleCode: normalizeModuleCode(moduleCode),
    readonly: runInput.readonly ?? true,
  })
  run.acceptanceProfile = activated.profile
  run.frameworkActivation = activated.activation
  return Object.freeze({ success: true, activationStatus: 'READY', profile: activated.profile, activation: activated.activation, run })
}

export async function executeModuleAcceptance({ moduleCode, runInput = {}, runnerOptions = {} } = {}) {
  const prepared = prepareModuleAcceptanceRun({ moduleCode, runInput })
  if (!prepared.success) return prepared
  const runnerResult = await execute(prepared.run, runnerOptions)
  return Object.freeze({
    success: runnerResult.success,
    activationStatus: prepared.activationStatus,
    profile: prepared.profile,
    activation: prepared.activation,
    runnerResult,
    businessWriteCount: prepared.run.report?.businessWriteCount ?? 0,
    productionUserDataWritten: prepared.run.report?.productionUserDataWritten ?? false,
  })
}
