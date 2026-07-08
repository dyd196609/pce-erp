/**
 * ============================
 * Meta Runtime V12 - Permission Engine
 * RBAC + ABAC
 * ============================
 */

const user = {
  id: 1,
  role: 'admin',
  dept: 'purchase',
}

/**
 * RBAC
 */
const roleMap = {
  admin: ['*'],
  manager: ['purchase:*'],
  user: ['purchase:view'],
}

/**
 * 是否有权限
 */
export const hasPermission = (perm) => {
  const perms = roleMap[user.role] || []

  return perms.includes('*') || perms.includes(perm)
}

/**
 * ABAC（属性权限）
 */
export const canAccessData = (row) => {
  if (user.role === 'admin') return true

  return row.dept === user.dept
}

/**
 * 字段级权限
 */
export const canViewField = (field) => {
  if (!field.permission) return true

  return hasPermission(field.permission)
}
