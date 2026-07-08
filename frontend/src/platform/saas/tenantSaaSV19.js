// ======================================
// Meta Runtime V19 - SaaS Tenant System
// 商业级多租户
// ======================================

const tenants = new Map()

// 创建租户（客户）
export const createTenant = (data) => {
  const tenant = {
    id: 't_' + Date.now(),
    name: data.name,
    plan: data.plan || 'free',
    apps: [],
    createdAt: Date.now(),
  }

  tenants.set(tenant.id, tenant)

  return tenant
}

// 获取租户
export const getTenant = (id) => {
  return tenants.get(id)
}

// 安装应用到租户
export const installToTenant = (tenantId, appId) => {
  const tenant = tenants.get(tenantId)

  if (!tenant) return

  tenant.apps.push(appId)

  return tenant
}

// 获取所有租户
export const getAllTenants = () => {
  return Array.from(tenants.values())
}
