import {
  validateProcessActionRuntimeContract,
  validateProcessContextContract,
  validateProcessHandoffContract,
  validateProcessNodeRuntimeContract,
  validateProcessStateTransitionContract,
} from '../contract/index.js'

export const PROCESS_ACCEPTANCE_FRAMEWORK_VERSION = 'PCE-PROCESS-ACCEPTANCE-FRAMEWORK-V1.1'

export const PROCESS_RUNTIME_RULES = Object.freeze({
  RULE_001: 'BUTTON_MUST_HAVE_ACTION_CONTRACT',
  RULE_002: 'OBJECT_MUST_HAVE_STATE_MODEL',
  RULE_003: 'NODE_MUST_HAVE_INPUT_OUTPUT',
  RULE_004: 'PROCESS_MUST_HAVE_HANDOFF',
  RULE_005: 'REMEDIATION_MUST_HAVE_REGRESSION',
  PROCESS_006: 'END_TO_END_BUSINESS_WALKTHROUGH_REQUIRED',
})

const pass = (family, ruleId, evidence) => Object.freeze({ family, ruleId, result: 'PASS', evidence })
const fail = (family, ruleId, evidence) => Object.freeze({ family, ruleId, result: 'FAIL', evidence })

function contractChecks(family, ruleId, items, validator, identity) {
  if (!Array.isArray(items) || items.length === 0) return [fail(family, ruleId, `${family.toUpperCase()}_CONTRACTS_REQUIRED`)]
  return items.map(item => {
    const validation = validator(item)
    return validation.valid
      ? pass(family, ruleId, identity(item))
      : fail(family, ruleId, `${identity(item) || 'unknown'}:${validation.errors.join(',')}`)
  })
}

function pageChecks(definition) {
  const pages = definition.pages || []
  if (!pages.length) return [fail('page', 'RULE-001', 'PAGE_CONTRACTS_REQUIRED')]
  return pages.flatMap(page => {
    const checks = []
    const node = (definition.nodes || []).find(item => item.nodeCode === page.nodeCode)
    if (!page.pageCode || !node) checks.push(fail('page', 'RULE-003', `${page.pageCode || 'unknown'}:NODE_BINDING_REQUIRED`))
    else checks.push(pass('page', 'RULE-003', `${page.pageCode}->${node.nodeCode}`))
    if (!Array.isArray(page.buttonBindings) || page.buttonBindings.length === 0) {
      checks.push(fail('page', 'RULE-001', `${page.pageCode || 'unknown'}:BUTTON_BINDINGS_REQUIRED`))
    } else {
      for (const binding of page.buttonBindings) {
        const action = (definition.actions || []).find(item => item.actionCode === binding.actionCode)
        checks.push(action && action.buttonCode === binding.buttonCode && action.nodeCode === page.nodeCode
          ? pass('page', 'RULE-001', `${binding.buttonCode}->${binding.actionCode}`)
          : fail('page', 'RULE-001', `${binding.buttonCode || 'unknown'}:ACTION_CONTRACT_MISSING`))
      }
    }
    return checks
  })
}

function runtimeChecks(definition) {
  const checks = []
  const actionCodes = new Set((definition.actions || []).map(item => item.actionCode))
  const stateModels = new Set((definition.stateModels || []).map(item => item.modelCode))
  const handoffCodes = new Set((definition.handoffs || []).map(item => item.handoffCode))
  for (const node of definition.nodes || []) {
    const missingActions = node.actions.filter(code => !actionCodes.has(code))
    checks.push(missingActions.length === 0
      ? pass('runtime', 'RULE-001', `${node.nodeCode}:ACTIONS_BOUND`)
      : fail('runtime', 'RULE-001', `${node.nodeCode}:MISSING:${missingActions.join(',')}`))
    checks.push(stateModels.has(node.stateModel)
      ? pass('runtime', 'RULE-002', `${node.nodeCode}->${node.stateModel}`)
      : fail('runtime', 'RULE-002', `${node.nodeCode}:STATE_MODEL_MISSING`))
    if (node.nextNode !== null) {
      const handoff = (definition.handoffs || []).find(item => item.fromNode === node.nodeCode && item.toNode === node.nextNode)
      checks.push(handoff && handoffCodes.has(handoff.handoffCode)
        ? pass('runtime', 'RULE-004', `${node.nodeCode}->${node.nextNode}`)
        : fail('runtime', 'RULE-004', `${node.nodeCode}:HANDOFF_MISSING`))
    }
  }
  return checks.length ? checks : [fail('runtime', 'RULE-003', 'RUNTIME_NODES_REQUIRED')]
}

function actionChecks(definition) {
  const checks = contractChecks('action', 'RULE-001', definition.actions, validateProcessActionRuntimeContract, item => item.actionCode)
  const nodes = new Map((definition.nodes || []).map(item => [item.nodeCode, item]))
  const models = new Map((definition.stateModels || []).map(item => [item.modelCode, item]))
  for (const action of definition.actions || []) {
    const node = nodes.get(action.nodeCode)
    const model = models.get(action.stateModel)
    const transition = model?.transitions.find(item => item.actionCode === action.actionCode
      && action.allowedFromStates.includes(item.from) && item.to === action.resultState)
    checks.push(node?.actions.includes(action.actionCode)
      && node.stateModel === action.stateModel
      && model?.objectType === action.objectType
      && transition
      ? pass('action', 'RULE-002', `${action.actionCode}:${action.allowedFromStates.join(',')}->${action.resultState}`)
      : fail('action', 'RULE-002', `${action.actionCode || 'unknown'}:STATE_TRANSITION_MISSING`))
  }
  return checks
}

function handoffChecks(definition) {
  const checks = contractChecks('handoff', 'RULE-004', definition.handoffs, validateProcessHandoffContract, item => item.handoffCode)
  const nodes = new Map((definition.nodes || []).map(item => [item.nodeCode, item]))
  const handoffSources = new Map((definition.handoffSources || []).map(item => [item.nodeCode, item]))
  const handoffTargets = new Map((definition.handoffTargets || []).map(item => [item.nodeCode, item]))
  const actions = new Map((definition.actions || []).map(item => [item.actionCode, item]))
  for (const handoff of definition.handoffs || []) {
    const source = nodes.get(handoff.fromNode) || handoffSources.get(handoff.fromNode)
    const target = nodes.get(handoff.toNode) || handoffTargets.get(handoff.toNode)
    const action = actions.get(handoff.actionCode)
    const inbound = source?.handoffActionOwner === 'target'
    const linked = source?.nextNode === target?.nodeCode
      && source?.outputObject === handoff.outputObject
      && target?.inputObject === handoff.inputObject
      && (inbound
        ? action?.nodeCode === target?.nodeCode
        : action?.nodeCode === source?.nodeCode && action?.handoffCode === handoff.handoffCode)
    checks.push(linked
      ? pass('handoff', 'RULE-004', `${handoff.fromNode}->${handoff.toNode}`)
      : fail('handoff', 'RULE-004', `${handoff.handoffCode || 'unknown'}:CHAIN_LINK_INVALID`))
  }
  return checks
}

function regressionChecks(definition) {
  const regressions = definition.regressions || []
  if (!regressions.length) return [fail('regression', 'RULE-005', 'REGRESSION_CASES_REQUIRED')]
  return regressions.map(item => item.caseCode && item.result === 'PASS'
    ? pass('regression', 'RULE-005', item.caseCode)
    : fail('regression', 'RULE-005', `${item.caseCode || 'unknown'}:REGRESSION_NOT_PASS`))
}

function process006Checks(definition) {
  const walkthrough = definition.businessWalkthrough
  if (!walkthrough || walkthrough.type !== 'End-to-End Business Walkthrough') {
    return [fail('process006', 'PROCESS-006', 'END_TO_END_BUSINESS_WALKTHROUGH_REQUIRED')]
  }
  const steps = Array.isArray(walkthrough.steps) ? walkthrough.steps : []
  const stepCodes = steps.map(item => item.stepCode)
  const validSteps = steps.length > 0
    && steps.every((item, index) => item.sequence === index + 1 && item.stepCode && item.result === 'PASS' && item.evidence)
    && new Set(stepCodes).size === stepCodes.length
  const passed = walkthrough.executed === true && walkthrough.completed === true
    && walkthrough.result === 'PASS' && walkthrough.sourceNode && walkthrough.targetNode && validSteps
  return [passed
    ? pass('process006', 'PROCESS-006', `${walkthrough.walkthroughCode}:${stepCodes.join('->')}`)
    : fail('process006', 'PROCESS-006', `${walkthrough.walkthroughCode || 'unknown'}:WALKTHROUGH_INCOMPLETE`)]
}

function contextChecks(definition) {
  const checks = contractChecks('context', 'RULE-003', definition.contexts, validateProcessContextContract, item => item.processInstanceId)
  const nodes = new Map((definition.nodes || []).map(item => [item.nodeCode, item]))
  const models = new Map((definition.stateModels || []).map(item => [item.modelCode, item]))
  for (const context of definition.contexts || []) {
    const node = nodes.get(context.nodeCode)
    const model = node ? models.get(node.stateModel) : null
    checks.push(node && model?.objectType === context.objectType && model.states.includes(context.state)
      ? pass('context', 'RULE-002', `${context.processInstanceId}:${context.nodeCode}:${context.state}`)
      : fail('context', 'RULE-002', `${context.processInstanceId || 'unknown'}:RUNTIME_BINDING_INVALID`))
  }
  return checks
}

function section(name, checks) {
  return Object.freeze({
    name,
    result: checks.every(check => check.result === 'PASS') ? 'PASS' : 'FAIL',
    checks: Object.freeze(checks),
  })
}

export function runProcessAcceptance(definition = {}) {
  const sections = Object.freeze({
    page: section('Page', pageChecks(definition)),
    runtime: section('Runtime', runtimeChecks(definition)),
    action: section('Action', actionChecks(definition)),
    state: section('State', contractChecks('state', 'RULE-002', definition.stateModels, validateProcessStateTransitionContract, item => item.modelCode)),
    handoff: section('Handoff', handoffChecks(definition)),
    regression: section('Regression', regressionChecks(definition)),
    process006: section('PROCESS-006', process006Checks(definition)),
  })
  const context = section('Context', contextChecks(definition))
  const node = section('Node', contractChecks('node', 'RULE-003', definition.nodes, validateProcessNodeRuntimeContract, item => item.nodeCode))
  const allSections = [...Object.values(sections), context, node]
  return Object.freeze({
    frameworkVersion: PROCESS_ACCEPTANCE_FRAMEWORK_VERSION,
    result: allSections.every(item => item.result === 'PASS') ? 'PASS' : 'FAIL',
    sections,
    contracts: Object.freeze({ node, context }),
  })
}
