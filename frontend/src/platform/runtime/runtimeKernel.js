// runtimeKernel.js（V23唯一执行内核）

// V23统一：不再依赖 workflowBindingEngine
// runWorkflow 已废弃

export const runtimeKernel = async ({ action, row, meta }) => {
  if (!action) return

  const actionName = action.action || action

  // 1. BPM优先
  if (meta?.workflow?.transitions) {
    return await runWorkflow(actionName, row, meta)
  }

  // 2. 普通动作
  return await executeLocalAction(actionName, row, meta)
}

// 本地动作执行器（以后扩展）
const executeLocalAction = async (actionName, row, meta) => {
  switch (actionName) {
    case 'view':
      console.log('VIEW:', row)
      return row

    case 'edit':
      console.log('EDIT:', row)
      return row

    case 'delete':
      console.log('DELETE:', row)
      return true

    default:
      console.warn('Unknown action:', actionName)
  }
}
