/**
 * ============================
 * Meta Runtime V18 - Permission Engine
 * RBAC + ABAC + DataScope
 * ============================
 */

const user = {
  id: 1,
  role: 'admin',
  dept: 'purchase',
}

// 角色权限
const rolePermission = {
  admin: ['*'],
  manager: ['purchase:*'],
  user: ['purchase:view'],
}

// 判断权限
export const hasPermission = (perm) => {
  const perms = rolePermission[user.role] || []
  return perms.includes('*') || perms.includes(perm)
}

// 行级权限
export const canAccessRow = (row) => {
  if (user.role === 'admin') return true
  return row.dept === user.dept
}

// 字段权限
export const canAccessField = (field) => {
  if (!field.permission) return true
  return hasPermission(field.permission)
}

// 数据范围控制（V18核心）
export const applyDataScope = (data) => {
  if (user.role === 'admin') return data
  return data.filter((d) => d.dept === user.dept)
}
