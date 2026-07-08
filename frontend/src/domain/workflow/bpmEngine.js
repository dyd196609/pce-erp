// =====================================
// BPM Engine V2（企业级完整版）
// 并行 + 会签 + 审批流
// =====================================

import { calculateOrderRisk, calculateSupplierRisk } from '../purchase/riskEngine'

// =========================
// 执行入口
// =========================
import { getActiveVersion } from './workflowVersionManager'

// =========================
// V5：运行流程（绑定版本）
// =========================
export const runWorkflow = (workflow, context) => {

  const activeVersion = getActiveVersion(workflow.module)

  const definition = activeVersion?.definition || workflow

  const state = {
    nodeMap: buildNodeMap(definition.nodes),
    edges: definition.edges || [],
    context,
    currentNodes: [findStartNode(definition.nodes)],
    history: [],
    version: activeVersion?.version || 1
  }

  while (state.currentNodes.length > 0) {
    const nodeId = state.currentNodes.shift()
    const node = state.nodeMap[nodeId]

    if (!node) continue

    executeNode(node, state)
  }

  return state.history
}
// =========================
// 节点执行
// =========================
const executeNode = (node, state) => {
  state.history.push({
    nodeId: node.id,
    type: node.type,
    label: node.label
  })

  switch (node.type) {

    // =========================
    // 开始节点
    // =========================
    case 'start':
      moveToNext(node, state)
      break

    // =========================
    // 审批节点（支持会签）
    // =========================
    case 'approve':
      handleApprove(node, state)
      break

    // =========================
    // 并行网关（分裂）
    // =========================
    case 'parallelGateway':
      handleParallel(node, state)
      break

    // =========================
    // 汇聚节点（Join）
    // =========================
    case 'join':
      handleJoin(node, state)
      break

    // =========================
    // 自动任务
    // =========================
    case 'service':
      handleService(node, state)
      break

    // =========================
    // 结束节点
    // =========================
    case 'end':
      state.currentNodes = []
      break
  }
}

---

# 🧩 四、并行处理（核心升级）

const handleParallel = (node, state) => {
  const outs = findOutgoing(node.id, state.edges)

  // 并行展开所有分支
  state.currentNodes.push(...outs.map(o => o.to))
}

// =========================
// Join（汇聚节点）
// =========================
const handleJoin = (node, state) => {

  const incoming = findIncoming(node.id, state.edges)

  const allDone = incoming.every(e =>
    state.completedNodes.has(e.from)
  )

  if (!allDone) {
    // 未完成 → 等待
    state.waitingNodes.set(node.id, true)
    return
  }

  moveToNext(node, state)
}

---

# 🧩 五、审批节点（V2：会签/或签）

const handleApprove = (node, state) => {

  const risk = state.context.risk_score || 0

  // =========================
  // 会签逻辑（AND审批）
  // =========================
  if (node.mode === 'and') {
    const approvals = state.context.approvals || []

    if (!approvals.includes(node.id)) {
      approvals.push(node.id)
      state.context.approvals = approvals
    }

    const required = node.requiredApprovers || 1

    if (approvals.length < required) {
      return // 等待更多审批
    }
  }

  // =========================
  // 风险控制
  // =========================
  if (risk >= 80) {
    state.context.status = 'REJECTED'
    return
  }

  if (risk >= 60) {
    state.context.status = 'REVIEW'
  } else {
    state.context.status = 'APPROVED'
  }

  state.completedNodes.add(node.id)
  moveToNext(node, state)
}

---

# 🧩 六、自动任务节点

const handleService = (node, state) => {

  if (node.action === 'calcRisk') {
    state.context.supplier_risk = calculateSupplierRisk(state.context)
    state.context.order_risk = calculateOrderRisk(state.context)

    state.context.risk_score =
      Math.round((state.context.supplier_risk + state.context.order_risk) / 2)
  }

  moveToNext(node, state)
}

---

# 🧩 七、工具函数（完整）

const moveToNext = (node, state) => {
  const outs = findOutgoing(node.id, state.edges)

  for (const e of outs) {
    state.currentNodes.push(e.to)
  }
}

const findOutgoing = (id, edges) =>
  edges.filter(e => e.from === id)

const findIncoming = (id, edges) =>
  edges.filter(e => e.to === id)

const buildNodeMap = (nodes) => {
  const map = {}
  nodes.forEach(n => map[n.id] = n)
  return map
}

const findStartNode = (nodes) =>
  nodes.find(n => n.type === 'start')?.id