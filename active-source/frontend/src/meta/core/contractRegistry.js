const registry = new Map()

export function registerContract(module, contract) {
  registry.set(module, contract)
}

export function getContract(module) {
  return registry.get(module)
}

export function getAllContracts() {
  return Array.from(registry.entries())
}
