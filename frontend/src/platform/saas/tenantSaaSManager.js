/**
 * ============================
 * Meta Runtime V13 - SaaS Tenant System
 * 商业级多租户核心
 * ============================
 */

const tenants = new Map()

/**
 * 创建租户（客户注册）
 */
export const createTenant = (data) => {
  const tenant = {
    id: 't_' + Date.now(),
    name: data.name,
    plan: data.plan || 'free',
    db: 'db_' + Date.now(),
    createdAt: Date.now(),
    status: 'ACTIVE',
  }

  tenants.set(tenant.id, tenant)

  return tenant
}

/**
 * 获取租户
 */
export const getTenant = (id) => {
  return tenants.get(id)
}

/**
 * 获取所有租户（运营后台）
 */
export const getAllTenants = () => {
  return Array.from(tenants.values())
}

/**
 * 租户隔离查询
 */
export const withTenantScope = (tenantId, data) => {
  return data.filter((d) => d.tenant_id === tenantId)
}
