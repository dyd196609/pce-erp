import { enforcePolicies } from '../governance/policyEnforcementEngine.js'
import { optimizeWorkflow } from '../governance/workflowOptimizationAI.js'

function getWorkflow(context = {}) {
  return context.workflow || context.schema?.workflow || {
    stateField: 'workflow_state',
    states: ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED'],
    transitions: [
      { from: 'DRAFT', to: 'SUBMITTED' },
      { from: 'SUBMITTED', to: 'APPROVED' },
      { from: 'APPROVED', to: 'CLOSED' },
    ],
  }
}

function getStateField(workflow = {}) {
  return workflow.stateField || workflow.statusField || 'workflow_state'
}

export function progressWorkflowAutomatically(context = {}) {
  const workflow = getWorkflow(context)
  const field = getStateField(workflow)
  const record = { ...(context.record || {}) }
  const initialState = record[field] || workflow.states?.[0] || 'DRAFT'
  const transitions = workflow.transitions || []
  const executedTransitions = []
  let currentState = initialState

  for (let index = 0; index < transitions.length; index += 1) {
    const transition = transitions.find((item) => item.from === currentState)
    if (!transition) break

    executedTransitions.push({
      from: transition.from,
      to: transition.to,
      actor: 'SYSTEM_AUTOPILOT',
      approval: 'AUTO',
    })
    currentState = transition.to
  }

  record[field] = currentState

  return {
    mode: 'V30_AUTOMATIC_WORKFLOW_PROGRESSION',
    initialState,
    currentState,
    finalState: currentState,
    executedTransitions,
    record,
  }
}

export function automateStateTransitions(context = {}) {
  const progression = context.progression || progressWorkflowAutomatically(context)

  return {
    mode: 'V30_STATE_TRANSITION_AUTOMATION',
    transitionCount: progression.executedTransitions.length,
    statePath: [
      progression.initialState,
      ...progression.executedTransitions.map((transition) => transition.to),
    ],
    noHumanApprovalRequired: true,
  }
}

export function runFullWorkflow(context = {}) {
  const policies = enforcePolicies(context)
  const policyException = policies.businessRules.level === 'BLOCKED'
  const optimization = optimizeWorkflow(context)
  const progression = policyException
    ? {
        mode: 'V30_AUTOMATIC_WORKFLOW_PROGRESSION',
        initialState: context.record?.workflow_state || 'DRAFT',
        currentState: context.record?.workflow_state || 'DRAFT',
        finalState: context.record?.workflow_state || 'DRAFT',
        executedTransitions: [],
        record: context.record || {},
      }
    : progressWorkflowAutomatically(context)
  const transitions = automateStateTransitions({
    ...context,
    progression,
  })

  return {
    mode: 'V30_SELF_RUNNING_WORKFLOW_ENGINE',
    selfRunningWorkflow: policyException ? 'POLICY_EXCEPTION' : 'ACTIVE',
    humanApproval: policyException ? 'POLICY_EXCEPTION_ONLY' : 'NOT_REQUIRED',
    policies,
    optimization,
    progression,
    transitions,
    metrics: {
      automationDepth: transitions.transitionCount,
      workflowAutopilotRate: policyException ? 0 : 1,
      expectedCycleTimeReduction: optimization.path.expectedCycleTimeReduction,
    },
  }
}
