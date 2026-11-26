// These existing editors contain only internal commands, with no cross-module
// action. Requiring a fabricated next node would alter their runtime contract.
const internalEditors = Object.freeze({
  'routing-management': '/pde/routings',
  'routing-version-management': '/pde/routing-versions',
})
const editorCommands = ['select-order-standard-routing','save-order-execution-draft','confirm-order-execution','revise-order-execution']
export function hasCompleteActionContract(contract) {
  if (!contract?.currentModule || !Array.isArray(contract.actions) || !Array.isArray(contract.forbiddenActions)) return false
  if (contract.nextModule && typeof contract.nextRoute === 'string') return true
  return contract.nextModule === '' && contract.nextRoute === ''
    && internalEditors[contract.currentModule] === contract.route
    && contract.actions.length === editorCommands.length
    && editorCommands.every(code => contract.actions.some(a => a.actionId === code))
    && contract.actions.every(a => a.actionType === 'command' && a.handlerType === 'emit'
      && a.requiredPermission && a.serverValidator && a.serverEligibilityCheck === true)
}
