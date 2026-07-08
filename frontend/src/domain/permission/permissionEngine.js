// =====================================
// 权限引擎 V1（企业级三层权限）
// =====================================

// 模拟用户权限（未来接后端）
const currentUser = {
  role: 'manager',
  dept: 'purchase',
  id: 1001,
}

// =========================
// 1. 字段级权限
// =========================
export const canViewField = (field) => {
  if (!field.permission) return true
  return checkPermission(field.permission)
}

export const canEditField = (field) => {
  if (!field.editPermission) return false
  return checkPermission(field.editPermission)
}

// =========================
// 2. 按钮级权限
// =========================
export const canExecuteAction = (action) => {
  if (!action.permission) return true
  return checkPermission(action.permission)
}

// =========================
// 3. 数据级权限（行权限）
// =========================
export const canViewRow = (row) => {
  // 示例：只能看本部门
  if (row.dept && row.dept !== currentUser.dept) {
    return false
  }

  return true
}

// =========================
// 核心权限判断
// =========================
const checkPermission = (perm) => {
  const rolePermissions = {
    admin: ['*'],
    manager: ['purchase:view', 'purchase:edit', 'purchase:approve'],
    user: ['purchase:view'],
  }

  const perms = rolePermissions[currentUser.role] || []

  return perms.includes('*') || perms.includes(perm)
}

// =========================
// 批量过滤数据（行级权限）
// =========================
export const filterRows = (rows) => {
  return rows.filter(canViewRow)
}

// =========================
// 字段过滤（字段级权限）
// =========================
export const filterFields = (fields) => {
  return fields.filter(canViewField)
}
