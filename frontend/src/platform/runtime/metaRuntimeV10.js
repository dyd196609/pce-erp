import { runWorkflow } from '@/meta/runtime/workflowEngine'
import { getRuntimeMeta } from '../meta/metaVersionManager'
import { createInstance } from '../bpm/bpmMonitor'

/**
 * ============================
 * Meta Runtime V10（闭环）
 * ============================
 */

export const executeActionV10 = async (context) => {
  const { action, row, metaId } = context

  const meta = getRuntimeMeta(metaId)

  // =====================
  // 1. BPM启动
  // =====================
  if (meta?.workflow?.enabled) {
    const instance = createInstance(metaId, row)

    await runWorkflow(action.action, row)

    instance.status = 'DONE'

    return instance
  }

  // =====================
  // 2. CRUD fallback
  // =====================
  return handleCrud(action.action, row)
}

function handleCrud(action, row) {
  switch (action) {
    case 'view':
      return row
    case 'edit':
      return row
    case 'submit':
      row.status = 'PENDING'
      return row
    case 'approve':
      row.status = 'APPROVED'
      return row
    case 'reject':
      row.status = 'REJECTED'
      return row
    case 'close':
      row.status = 'CLOSED'
      return row
  }
}
