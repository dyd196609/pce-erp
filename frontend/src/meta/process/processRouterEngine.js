import { defineProcess } from './processDefinitionEngine.js'
import { validateTransition } from './workflowStateEngine.js'

export function determineNextStep(type = 'purchase', currentState = 'draft') {
  const transition = defineProcess(type).transitions.find((item) => item.from === currentState)
  return transition?.to || null
}

export function routeToNextRole(type = 'purchase', currentState = 'draft') {
  const process = defineProcess(type)
  const nextStep = determineNextStep(type, currentState)

  return {
    type,
    from: currentState,
    nextStep,
    nextRole: nextStep ? process.roles[nextStep] : null,
    routable: Boolean(nextStep),
  }
}

export function routeWorkflow(type = 'purchase', currentState = 'draft', action = '') {
  const validation = validateTransition(type, currentState, action)
  const process = defineProcess(type)

  return {
    ...validation,
    nextStep: validation.valid ? validation.to : null,
    nextRole: validation.valid ? process.roles[validation.to] : null,
    routing: validation.valid ? 'ROUTED' : 'BLOCKED',
  }
}

export function buildProcessRoutingMap(type = 'purchase') {
  const process = defineProcess(type)

  return process.transitions.map((transition) => ({
    ...transition,
    fromRole: process.roles[transition.from],
    toRole: process.roles[transition.to],
  }))
}
