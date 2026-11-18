import { SCM_PURCHASE_LIFECYCLE_MAP, SCM_PURCHASE_LIFECYCLE_MAP_CODE } from '../../domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleMap.js'
import { SCM_PURCHASE_LIFECYCLE_RELATION_RULE_SET_CODE } from '../../domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleRelationRules.js'
import { SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULE_SET_CODE } from '../../domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleForbiddenRules.js'
import { SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS_CODE } from '../../domain/scm/purchaseOrder/freeze/scmPurchaseLifecycleFreezeStatus.js'

export const SCM_PURCHASE_LIFECYCLE_FREEZE_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.11'

export const SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE',
  version: SCM_PURCHASE_LIFECYCLE_FREEZE_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: SCM_PURCHASE_LIFECYCLE_MAP_CODE,
  objects: Object.freeze(SCM_PURCHASE_LIFECYCLE_MAP.nodes.map(item => item.objectCode)),
  upstreamProfiles: Object.freeze([...new Set(SCM_PURCHASE_LIFECYCLE_MAP.nodes.map(item => item.acceptanceProfileCode))]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    SCM_PURCHASE_LIFECYCLE_MAP_CODE,
    SCM_PURCHASE_LIFECYCLE_RELATION_RULE_SET_CODE,
    SCM_PURCHASE_LIFECYCLE_FORBIDDEN_RULE_SET_CODE,
    SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR', 'DATABASE_PROTECTION_COLLECTOR']),
  activationStatus: 'READY',
  activationMode: 'read_only',
  mode: 'read_only',
  frozen: true,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateScmPurchaseLifecycleFreezeAcceptanceProfile(profile = SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.profileCode !== 'SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE') missing.push('profileCode')
  if (profile.objectCode !== 'SCM_PURCHASE_LIFECYCLE_MAP') missing.push('objectCode')
  if (profile.objects?.length !== 11) missing.push('objects')
  if (profile.upstreamProfiles?.length !== 10) missing.push('upstreamProfiles')
  if (profile.rules?.length !== 4) missing.push('rules')
  if (!profile.templates?.length || profile.collectors?.length !== 3) missing.push('acceptanceBindings')
  if (profile.activationStatus !== 'READY') missing.push('activationStatus')
  if (profile.activationMode !== 'read_only' || profile.mode !== 'read_only') missing.push('mode')
  if (profile.frozen !== true) missing.push('frozen')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
