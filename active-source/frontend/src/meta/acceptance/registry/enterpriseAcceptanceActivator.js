import masterTemplate from '../templates/enterprise_page_master_template.json' with { type: 'json' }
import commonChecklist from '../templates/enterprise_page_common_checklist.json' with { type: 'json' }
import scmTemplateV2 from '../templates/scmBusinessPageAcceptanceTemplateV2.json' with { type: 'json' }
import { registerScmBusinessPageEvidenceCollectors } from '../evidence/scmBusinessPageEvidenceCollectors.js'
import { listEvidenceCollectors } from '../evidence/enterprisePageEvidenceCollectorRegistry.js'
import { listScmAcceptanceObjects } from '../scm/scmAcceptanceObjectModel.js'
import { SCM_STATUS_ACCEPTANCE_RULES } from '../scm/scmStatusAcceptanceRules.js'
import { SCM_TRACE_ACCEPTANCE_RULES } from '../scm/scmTraceAcceptanceRules.js'
import { SCM_ACTION_ACCEPTANCE_RULES } from '../scm/scmActionAcceptanceRules.js'
import { SCM_FINANCIAL_BOUNDARY } from '../scm/scmFinancialBoundaryRules.js'
import {
  getEnterpriseAcceptanceModuleRegistration,
  validateEnterpriseAcceptanceRegistration,
} from './enterpriseAcceptanceRegistry.js'

export const ENTERPRISE_ACCEPTANCE_ACTIVATOR_VERSION = 'V1.14.2.8.4.24'

const TEMPLATE_LOADERS = Object.freeze({
  ENTERPRISE_PAGE_MASTER_TEMPLATE: masterTemplate,
  ENTERPRISE_PAGE_COMMON_CHECKLIST: commonChecklist,
  SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2: scmTemplateV2,
})

const RULE_LOADERS = Object.freeze({
  SCM_OBJECT_RULE: listScmAcceptanceObjects(),
  SCM_STATUS_RULE: SCM_STATUS_ACCEPTANCE_RULES,
  SCM_TRACE_RULE: SCM_TRACE_ACCEPTANCE_RULES,
  SCM_ACTION_RULE: SCM_ACTION_ACCEPTANCE_RULES,
  SCM_FINANCIAL_BOUNDARY_RULE: Object.freeze([SCM_FINANCIAL_BOUNDARY]),
  SCM_CANARY_ISOLATION_RULE: Object.freeze([scmTemplateV2.canaryIsolation]),
  SCM_DATA_PROTECTION_RULE: Object.freeze([scmTemplateV2.releaseRequirements]),
  SCM_RELATIONSHIP_DIRECTION_RULE: Object.freeze(SCM_TRACE_ACCEPTANCE_RULES.map(rule => Object.freeze({ ruleCode: rule.ruleCode, direction: rule.direction, reverseGenerationForbidden: rule.reverseGenerationForbidden }))),
})

const resolveModuleCode = input => typeof input === 'string' ? input : input?.moduleCode

const buildActivationRuleBindings = () => Object.freeze([
  ...scmTemplateV2.checks.map(check => `TEMPLATE:${check.id}`),
  ...listScmAcceptanceObjects().map(object => `OBJECT:${object.objectCode}`),
  ...SCM_TRACE_ACCEPTANCE_RULES.map(rule => `TRACE:${rule.ruleCode}`),
  'ACTION:SCM_ACTION_WHITELIST',
  'FINANCE:SCM_FINANCIAL_BOUNDARY',
  'CANARY:SCM_CANARY_ISOLATION',
])

export function activateAcceptanceFramework(input, options = {}) {
  const moduleCode = String(resolveModuleCode(input) || '').trim().toUpperCase()
  const registration = options.registration || getEnterpriseAcceptanceModuleRegistration(moduleCode)
  if (!registration) return Object.freeze({
    moduleCode,
    activated: false,
    activationStatus: 'BLOCKED',
    error: Object.freeze({ code: 'MODULE_NOT_REGISTERED', message: moduleCode || 'moduleCode' }),
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
  const validation = validateEnterpriseAcceptanceRegistration(registration)
  if (!validation.valid) return Object.freeze({
    moduleCode,
    activated: false,
    activationStatus: 'BLOCKED',
    error: Object.freeze({ code: 'MODULE_REGISTRATION_INCOMPLETE', message: validation.missing.join(',') }),
    validation,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })

  const loadedTemplates = registration.templateStack.map(code => Object.freeze({ code, definition: TEMPLATE_LOADERS[code] })).filter(item => item.definition)
  registerScmBusinessPageEvidenceCollectors()
  const availableCollectors = new Map(listEvidenceCollectors().map(item => [item.collectorCode, item]))
  const loadedCollectors = registration.evidenceCollectors.map(code => availableCollectors.get(code)).filter(Boolean)
  const loadedRuleSets = registration.rules.map(code => Object.freeze({ code, entries: RULE_LOADERS[code] || Object.freeze([]) }))
  const activationRuleBindings = buildActivationRuleBindings()
  const objectProfiles = Object.freeze([...(registration.objectRegistrations || [])])
  const ruleProfiles = Object.freeze([...(registration.ruleProfiles || [])])
  const complete = loadedTemplates.length === registration.templateStack.length
    && loadedCollectors.length === registration.evidenceCollectors.length
    && loadedRuleSets.every(ruleSet => ruleSet.entries.length > 0)

  return Object.freeze({
    moduleCode,
    activated: complete,
    activationStatus: complete ? 'READY' : 'BLOCKED',
    templates: loadedTemplates.length,
    collectors: loadedCollectors.length,
    rules: activationRuleBindings.length,
    registeredTemplates: registration.templates.length,
    registeredRuleSets: registration.rules.length,
    ruleEntryCount: loadedRuleSets.reduce((total, ruleSet) => total + ruleSet.entries.length, 0),
    objects: registration.objects.length,
    objectProfiles,
    acceptanceProfiles: objectProfiles,
    objectProfileCount: objectProfiles.length,
    ruleProfiles,
    ruleProfileCount: ruleProfiles.length,
    templateCodes: Object.freeze(loadedTemplates.map(item => item.code)),
    collectorCodes: Object.freeze(loadedCollectors.map(item => item.collectorCode)),
    ruleSetCodes: Object.freeze(loadedRuleSets.map(item => item.code)),
    collectorAliases: registration.collectorAliases || Object.freeze({}),
    activationRuleBindings,
    runner: registration.runner,
    archive: registration.archive,
    readOnly: true,
    businessActions: Object.freeze([]),
    businessWriteCount: 0,
    productionUserDataWritten: false,
    error: complete ? null : Object.freeze({ code: 'ACTIVATION_COMPONENT_MISSING', message: moduleCode }),
  })
}
