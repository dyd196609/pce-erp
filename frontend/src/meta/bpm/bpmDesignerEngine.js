import { buildWorkflowGraph } from './workflowVisualizer.js'

function normalizeNode(node, index = 0) {
  if (typeof node === 'string') {
    return {
      id: node,
      label: node,
      x: 80 + index * 120,
      y: 80,
    }
  }

  return {
    id: node.id,
    label: node.label || node.id,
    x: node.x ?? 80 + index * 120,
    y: node.y ?? 80,
  }
}

function normalizeEdge(edge) {
  return {
    id: edge.id || `${edge.from}->${edge.to}`,
    from: edge.from,
    to: edge.to,
  }
}

export function buildDesignerGraph(schema = {}) {
  const graph = buildWorkflowGraph(schema)

  return {
    nodes: graph.nodes.map(normalizeNode),
    edges: graph.edges.map(normalizeEdge),
  }
}

export function applyGraphToSchema(graph = {}) {
  return {
    states: (graph.nodes || []).map((node) => node.id),
    transitions: (graph.edges || []).map((edge) => ({
      from: edge.from,
      to: edge.to,
    })),
  }
}

export function addState(graph = {}, stateId) {
  const id = String(stateId || '').trim().toUpperCase()
  if (!id) return graph
  if ((graph.nodes || []).some((node) => node.id === id)) return graph

  return {
    ...graph,
    nodes: [
      ...(graph.nodes || []),
      normalizeNode(id, graph.nodes?.length || 0),
    ],
  }
}

export function deleteState(graph = {}, stateId) {
  return {
    ...graph,
    nodes: (graph.nodes || []).filter((node) => node.id !== stateId),
    edges: (graph.edges || []).filter((edge) => edge.from !== stateId && edge.to !== stateId),
  }
}

export function moveState(graph = {}, stateId, position = {}) {
  return {
    ...graph,
    nodes: (graph.nodes || []).map((node) =>
      node.id === stateId
        ? {
            ...node,
            x: position.x ?? node.x,
            y: position.y ?? node.y,
          }
        : node
    ),
  }
}

export function addTransition(graph = {}, from, to) {
  if (!from || !to || from === to) return graph

  const id = `${from}->${to}`
  if ((graph.edges || []).some((edge) => edge.id === id)) return graph

  return {
    ...graph,
    edges: [
      ...(graph.edges || []),
      normalizeEdge({ from, to }),
    ],
  }
}

export function updateTransition(graph = {}, edgeId, patch = {}) {
  return {
    ...graph,
    edges: (graph.edges || []).map((edge) => {
      if (edge.id !== edgeId) return edge

      return normalizeEdge({
        ...edge,
        ...patch,
        id: `${patch.from || edge.from}->${patch.to || edge.to}`,
      })
    }),
  }
}

export function deleteTransition(graph = {}, edgeId) {
  return {
    ...graph,
    edges: (graph.edges || []).filter((edge) => edge.id !== edgeId),
  }
}

