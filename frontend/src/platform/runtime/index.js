// ========================================
// V27-1 runtime 统一入口（唯一对外API）
// ========================================

// workflow 执行引擎
import { runWorkflow } from './workflowEngine'

// 流程回溯
import { buildFlowTrace } from './flowTraceEngine'

// 审批记录
import { writeAuditLog } from './auditEngine'

// 流程执行核心
import { executeFlow } from './flowEngine'

/**
 * 🚀 统一 workflow 入口
 */
export function workflowRuntime() {
  return {
    runWorkflow,
    executeFlow,
    buildFlowTrace,
    writeAuditLog,
  }
}

/**
 * 🚀 直接导出（兼容旧代码）
 */
export { runWorkflow, executeFlow, buildFlowTrace, writeAuditLog }
