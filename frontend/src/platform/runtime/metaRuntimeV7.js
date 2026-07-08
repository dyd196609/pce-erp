import { runWorkflow } from '@/meta/runtime/workflowEngine'

/**
 * =========================
 * Meta Runtime V7（核心引擎）
 * =========================
 */

/**
 * 运行时上下文构建
 */
export const createRuntimeContext = (meta, row) => {
  return {
    meta,
    row,

    user: getCurrentUser(),
    role: getCurrentRole(),

    workflowState: row.workflow_status || 'DRAFT',

    permissions: getPermissions(),
  }
}

/**
 * V7统一执行入口
 */
export const executeActionV7 = async (context) => {
  const { action, row, meta, workflowState } = context

  const actionName = action.action || action

  // =========================
  // BPM流程层
  // =========================
  if (meta?.workflow?.enabled) {
    const allowed = meta.workflow.transitions?.[workflowState] || []

    if (allowed.includes(actionName)) {
      await runWorkflow(actionName, row)

      row.workflow_status = mapState(actionName)

      return row
    }
  }

  // =========================
  // CRUD层
  // =========================
  return handleCrud(actionName, row)
}

/**
 * Runtime Actions（动态按钮）
 */
export const getRuntimeActionsV7 = (meta, row, context) => {
  const state = row.workflow_status || 'DRAFT'

  const actions = meta.actions || []

  return actions.filter((act) => {
    // BPM控制
    if (act.bpm && meta.workflow) {
      const allowed = meta.workflow.transitions?.[state] || []
      return allowed.includes(act.action)
    }

    // 权限控制（V7新增）
    if (act.permission) {
      return hasPermission(context.user, act.permission)
    }

    return true
  })
}

/**
 * 字段级权限控制（V7核心）
 */
export const getFieldVisible = (field, context) => {
  if (!field.permission) return true

  return hasPermission(context.user, field.permission)
}

/**
 * 字段是否可编辑
 */
export const getFieldEditable = (field, context) => {
  if (context.workflowState === 'APPROVED') return false

  return !field.readonly
}

/**
 * CRUD处理
 */
function handleCrud(action, row) {
  switch (action) {
    case 'view':
      return row
    case 'edit':
      return row

    case 'create':
      return row

    case 'submit':
      row.workflow_status = 'PENDING'
      return row

    case 'approve':
      row.workflow_status = 'APPROVED'
      return row

    case 'reject':
      row.workflow_status = 'REJECTED'
      return row

    case 'close':
      row.workflow_status = 'CLOSED'
      return row
  }
}

/**
 * 状态映射
 */
function mapState(action) {
  return {
    submit: 'PENDING',
    approve: 'APPROVED',
    reject: 'REJECTED',
    close: 'CLOSED',
  }[action]
}

/**
 * Mock权限系统（V7基础版）
 */
function hasPermission(user, perm) {
  return true // 下一阶段升级真实权限
}

/**
 * mock用户
 */
function getCurrentUser() {
  return { id: 1, name: 'admin' }
}

function getCurrentRole() {
  return 'admin'
}

function getPermissions() {
  return []
}
