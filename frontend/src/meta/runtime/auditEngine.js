// =============================
// V26 Audit Engine（增强版）
// =============================

const auditLogs = []

export function writeAuditLog(log) {
  auditLogs.push({
    id: 'log_' + Date.now(),
    time: new Date().toISOString(),
    orderId: log.orderId || null,
    ...log,
  })

  console.log('[AUDIT]', log)
}

/**
 * 按单据获取审批轨迹
 */
export function getAuditLogsByOrder(orderId) {
  return auditLogs.filter((log) => log.orderId === orderId)
}

/**
 * 全量日志（调试用）
 */
export function getAuditLogs() {
  return auditLogs
}
