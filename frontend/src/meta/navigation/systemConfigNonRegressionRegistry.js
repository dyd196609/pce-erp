export const SYSTEM_CONFIG_EXPECTED_MODULE_SET = Object.freeze([
  Object.freeze({ key: 'role-permission', label: '角色权限', route: '/admin/role-permission' }),
  Object.freeze({ key: 'menu-config', label: '菜单配置', route: '/admin/config/menu' }),
  Object.freeze({ key: 'process-template', label: '流程模板', route: '/admin/process-template' }),
  Object.freeze({ key: 'tenant-setting', label: '租户参数', route: '/admin/tenant-setting' }),
])

export const SYSTEM_CONFIG_CURRENT_MODULE_SET = Object.freeze([
  ...SYSTEM_CONFIG_EXPECTED_MODULE_SET,
  Object.freeze({ key: 'enterprise-foundation', label: '企业基础资料', route: '/foundation' }),
])

export function assertSystemConfigNonRegression(current = SYSTEM_CONFIG_CURRENT_MODULE_SET) {
  const currentKeys = new Set(current.map(item => item.key))
  const missing = SYSTEM_CONFIG_EXPECTED_MODULE_SET.filter(item => !currentKeys.has(item.key))
  if (missing.length) throw new Error(`系统配置模块回归：${missing.map(item => item.label).join('、')}`)
  return true
}
