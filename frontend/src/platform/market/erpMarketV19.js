// ======================================
// Meta Runtime V19 - ERP Market
// 应用商店系统
// ======================================

const apps = new Map()

// 发布ERP应用
export const publishERPApp = (app) => {
  const id = 'app_' + Date.now()

  const appRecord = {
    id,
    name: app.name,
    meta: app.meta,
    bpm: app.bpm,
    price: app.price || 0,
    status: 'PUBLISHED',
  }

  apps.set(id, appRecord)

  return appRecord
}

// 获取应用市场
export const getMarketApps = () => {
  return Array.from(apps.values())
}

// 安装应用
export const installApp = (tenantId, appId) => {
  const app = apps.get(appId)

  if (!app) return null

  return {
    tenantId,
    appId,
    installedAt: Date.now(),
    status: 'ACTIVE',
  }
}

// 下架应用
export const unpublishApp = (appId) => {
  return apps.delete(appId)
}
