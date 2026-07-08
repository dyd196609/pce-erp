// =====================================
// BPM Runtime Engine V3（可视化运行层）
// =====================================

// =========================
// 流程实例状态
// =========================
export const createRuntimeInstance = (workflow, context) => {
  return {
    id: generateId(),
    workflow,
    context,
    currentNode: findStart(workflow),
    history: [],
    status: 'RUNNING',
  }
}

// =========================
// 执行一步（关键：用于可视化）
// =========================
export const stepExecute = (instance) => {
  const node = findNode(instance.workflow, instance.currentNode)

  if (!node) return instance

  // 记录执行轨迹
  instance.history.push({
    nodeId: node.id,
    type: node.type,
    label: node.label,
    time: new Date().toISOString(),
  })

  // 执行逻辑
  switch (node.type) {
    case 'start':
      instance.currentNode = getNext(node)
      break

    case 'approve':
      instance.context.status = 'APPROVING'
      instance.currentNode = getNext(node)
      break

    case 'service':
      executeService(node, instance)
      instance.currentNode = getNext(node)
      break

    case 'gateway':
      instance.currentNode = evaluateGateway(node, instance.context)
      break

    case 'end':
      instance.status = 'FINISHED'
      instance.currentNode = null
      break
  }

  return instance
}

// =========================
// 获取当前运行状态（用于UI高亮）
// =========================
export const getRuntimeView = (instance) => {
  return {
    current: instance.currentNode,
    history: instance.history,
    status: instance.status,
  }
}

// =========================
// 工具函数
// =========================

const findStart = (workflow) => workflow.nodes.find((n) => n.type === 'start')?.id

const findNode = (workflow, id) => workflow.nodes.find((n) => n.id === id)

const getNext = (node) => {
  return node.next || null
}

const executeService = (node, instance) => {
  if (node.action === 'calcRisk') {
    instance.context.risk_calculated = true
  }
}

const evaluateGateway = (node, context) => {
  const edges = node.outgoing || []

  for (const e of edges) {
    if (!e.condition) return e.to
    if (new Function('ctx', `return ${e.condition}`)(context)) {
      return e.to
    }
  }

  return null
}

const generateId = () => Math.random().toString(36).substring(2, 10)
