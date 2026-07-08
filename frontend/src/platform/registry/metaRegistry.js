// ======================================
// Meta Runtime V15 - Registry Engine
// AI生成ERP统一注册中心
// ======================================

const registry = new Map()

// 注册ERP应用
export const registerERP = (app) => {
  const id = app?.id || `erp_${Date.now()}`

  registry.set(id, {
    id,
    meta: app.meta,
    status: 'ACTIVE',
    createdAt: new Date(),
  })

  return id
}

// 获取ERP
export const getERP = (id) => {
  return registry.get(id)
}

// 获取所有ERP
export const getAllERP = () => {
  return Array.from(registry.values())
}

// 删除ERP
export const removeERP = (id) => {
  return registry.delete(id)
}

// 清空
export const clearERP = () => {
  registry.clear()
}
