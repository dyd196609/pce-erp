export const FORMAL_PRICE_APPROVAL_DECISION_RULE_VERSION = 'V1.14.2.8.6.22'

export const FORMAL_PRICE_APPROVAL_DECISION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'require_all_nodes_defined', outcomeCode: 'definition_complete', resultCreated: false, businessEffectApplied: false }),
  Object.freeze({ ruleCode: 'require_role_separation', outcomeCode: 'separation_confirmed', resultCreated: false, businessEffectApplied: false }),
  Object.freeze({ ruleCode: 'require_manual_decision', outcomeCode: 'manual_decision_required', resultCreated: false, businessEffectApplied: false }),
])

export const FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL = Object.freeze({
  ruleModelCode: 'SCM_FORMAL_PRICE_APPROVAL_DECISION_RULE',
  version: FORMAL_PRICE_APPROVAL_DECISION_RULE_VERSION,
  rules: FORMAL_PRICE_APPROVAL_DECISION_RULES,
  mode: 'rule_definition_only',
  decisionRuleMeansResult: false,
  approvalDecisionMeansBusinessEffect: false,
  automaticDecision: false,
  resultFactoryConnected: false,
  businessEffectExecutorConnected: false,
})

export function validateFormalPriceApprovalDecisionRuleModel(model = FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL) {
  const valid = model.ruleModelCode === 'SCM_FORMAL_PRICE_APPROVAL_DECISION_RULE'
    && model.rules.length === 3
    && model.rules.every((rule) => rule.resultCreated === false && rule.businessEffectApplied === false)
    && model.mode === 'rule_definition_only'
    && model.decisionRuleMeansResult === false
    && model.approvalDecisionMeansBusinessEffect === false
    && model.automaticDecision === false
    && model.resultFactoryConnected === false
    && model.businessEffectExecutorConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
