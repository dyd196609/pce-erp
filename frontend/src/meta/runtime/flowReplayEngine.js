// =============================
// V27 Flow Replay Engine（流程回溯）
// =============================

import { getAuditLogs } from './auditEngine.js'

/**
 * 根据订单ID重建流程路径
 */
export function buildFlowTrace(orderId) {
  const logs = getAuditLogs()
    .filter((l) => l.orderId === orderId)
    .sort((a, b) => new Date(a.time) - new Date(b.time))

  const trace = []

  for (let i = 0; i < logs.length; i++) {
    const curr = logs[i]
    const next = logs[i + 1]

    trace.push({
      from: curr.from,
      to: curr.to,
      action: curr.action,
      user: curr.user,
      role: curr.role,
      time: curr.time,
      duration: next ? new Date(next.time) - new Date(curr.time) : null,
    })
  }

  return trace
}

/**
 * 获取当前流程状态链
 */
export function getCurrentFlowState(orderId) {
  const trace = buildFlowTrace(orderId)

  if (trace.length === 0) {
    return {
      status: 'no-flow',
      nodes: [],
    }
  }

  return {
    status: 'active',
    nodes: trace.map((t) => t.to),
  }
}
