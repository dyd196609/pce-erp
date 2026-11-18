// A terminal contract points back to its own identity; this is not a downstream transition.
export function validateActionFlow(contract, registry = []) {
  if (!contract?.currentModule || typeof contract.nextModule !== 'string' || typeof contract.nextRoute !== 'string') return false
  if (contract.terminal === true) return contract.nextModule === contract.currentModule && contract.nextRoute === contract.route
  if (!contract.nextModule || contract.nextModule === contract.currentModule) return false
  const target = registry.find(row => row.currentModule === contract.nextModule)
  return !target || contract.nextRoute === target.route
}
