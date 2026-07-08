/**
 * ============================
 * Meta Runtime V11 - Platform Kernel
 * 企业级生产内核
 * ============================
 */

import { executeActionV10 } from '@/platform/runtime/metaRuntimeV10'
import { getRuntimeMeta } from '@/platform/meta/metaVersionManager'
import { createInstance } from '@/platform/bpm/bpmMonitor'

/**
 * ============================
 * 全局平台入口（唯一入口）
 * ============================
 */
export const runPlatform = async ({ metaId, action, row, user, env = 'prod' }) => {
  // =========================
  // 1. 获取运行时Meta（版本控制）
  // =========================
  const meta = getRuntimeMeta(metaId)

  if (!meta) {
    throw new Error('Meta not found')
  }

  // =========================
  // 2. 构建运行时上下文
  // =========================
  const context = {
    meta,
    row,
    user,
    env,
    workflowState: row.workflow_status || 'DRAFT',
  }

  // =========================
  // 3. BPM实例创建（生产级）
  // =========================
  const instance = createInstance(metaId, row)

  // =========================
  // 4. 执行V10逻辑
  // =========================
  const result = await executeActionV10({
    action,
    row,
    metaId,
    context,
  })

  // =========================
  // 5. 更新实例状态
  // =========================
  instance.status = 'RUNNING'
  instance.lastAction = action.action

  return {
    instance,
    result,
  }
}
