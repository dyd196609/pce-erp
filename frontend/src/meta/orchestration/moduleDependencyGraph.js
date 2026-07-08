export const moduleRelationships = [
  { from: 'purchase', to: 'finance', event: 'purchase.approved', trigger: 'finance.createPayable' },
  { from: 'crm', to: 'purchase', event: 'crm.dealClosed', trigger: 'purchase.createOrder' },
  { from: 'inventory', to: 'purchase', event: 'inventory.lowStock', trigger: 'purchase.triggerReorder' },
  { from: 'scm', to: 'purchase', event: 'scm.delay', trigger: 'purchase.adjustPlan' },
]

export function buildDependencyGraph() {
  const nodes = Array.from(new Set(moduleRelationships.flatMap((item) => [item.from, item.to])))
    .map((id) => ({ id, label: id }))

  return {
    nodes,
    edges: moduleRelationships.map((item) => ({
      id: `${item.from}->${item.to}:${item.event}`,
      from: item.from,
      to: item.to,
      event: item.event,
      trigger: item.trigger,
    })),
  }
}

export function detectCircularTriggers(relationships = moduleRelationships) {
  const graph = relationships.reduce((next, item) => {
    next[item.from] = [...(next[item.from] || []), item.to]
    return next
  }, {})
  const cycles = []
  const visiting = new Set()
  const visited = new Set()

  function visit(node, path = []) {
    if (visiting.has(node)) {
      cycles.push([...path, node])
      return
    }
    if (visited.has(node)) return

    visiting.add(node)
    ;(graph[node] || []).forEach((target) => visit(target, [...path, node]))
    visiting.delete(node)
    visited.add(node)
  }

  Object.keys(graph).forEach((node) => visit(node))
  return cycles
}

export function getDependencySummary() {
  const graph = buildDependencyGraph()
  return {
    ...graph,
    circularTriggers: detectCircularTriggers(),
    healthy: detectCircularTriggers().length === 0,
  }
}
