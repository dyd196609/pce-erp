export function buildWorkflowGraph(schema = {}) {
  const workflow = schema.workflow || schema
  const states = workflow.states || []
  const transitions = workflow.transitions || []

  return {
    nodes: states.map((state) => ({
      id: state,
      label: state,
    })),
    edges: transitions.map((transition) => ({
      id: `${transition.from}->${transition.to}`,
      from: transition.from,
      to: transition.to,
    })),
  }
}

export function markWorkflowGraph(graph, currentState, availableTransitions = []) {
  const availableEdgeIds = new Set(availableTransitions.map((transition) => `${transition.from}->${transition.to}`))
  const nextStateIds = new Set(availableTransitions.map((transition) => transition.to))

  return {
    nodes: graph.nodes.map((node) => ({
      ...node,
      current: node.id === currentState,
      next: nextStateIds.has(node.id),
    })),
    edges: graph.edges.map((edge) => ({
      ...edge,
      available: availableEdgeIds.has(edge.id),
      blocked: !availableEdgeIds.has(edge.id),
    })),
  }
}

