/**
 * ============================
 * Meta Runtime V12 - Tenant System
 * SaaS 多租户核心
 * ============================
 */

const currentTenant = {
  id: 'tenant_001',
  name: 'Demo Company',
}

/**
 * 获取当前租户
 */
export const getTenant = () => currentTenant

/**
 * 设置租户
 */
export const setTenant = (tenant) => {
  currentTenant.id = tenant.id
  currentTenant.name = tenant.name
}

/**
 * 给API自动注入租户ID
 */
export const withTenant = (payload) => {
  return {
    ...payload,
    tenant_id: currentTenant.id,
  }
}
