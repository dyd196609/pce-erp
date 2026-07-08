export function executeFlow({ flow, row, user }) {
  const stateField = flow.statusField || 'status'
  const currentState = row[stateField]

  const currentNode = findNode(flow, currentState)
  if (!currentNode) {
    console.warn('[flow] node not found:', currentState)
    return row
  }

  const edges = findEdges(flow, currentNode.id)

  // 找可执行路径
  const nextEdge = edges.find((edge) => {
    return checkCondition(edge.condition, row)
  })

  if (!nextEdge) {
    console.warn('[flow] no valid transition')
    return row
  }

  const nextNode = findNodeById(flow, nextEdge.to)
  if (!nextNode) {
    console.warn('[flow] next node not found')
    return row
  }

  // 执行状态流转
  row[stateField] = nextNode.id

  console.log('[flow] transition:', currentState, '→', nextNode.id)

  return row
}

// --------------------
// 查节点
// --------------------
function findNode(flow, state) {
  return flow.nodes.find((n) => n.id === state)
}

// --------------------
// 根据ID查节点
// --------------------
function findNodeById(flow, id) {
  return flow.nodes.find((n) => n.id === id)
}

// --------------------
// 查边
// --------------------
function findEdges(flow, fromId) {
  return flow.edges.filter((e) => e.from === fromId)
}

// --------------------
// 条件判断
// --------------------
function checkCondition(condition, row) {
  if (!condition) return true

  const val = row[condition.field]

  switch (condition.op) {
    case '>':
      return val > condition.value
    case '<':
      return val < condition.value
    case '>=':
      return val >= condition.value
    case '<=':
      return val <= condition.value
    case '==':
      return val == condition.value
    case '!=':
      return val != condition.value
    default:
      return false
  }
}
