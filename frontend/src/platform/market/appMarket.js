/**
 * ============================
 * Meta Runtime V13 - App Market
 * ============================
 */

const apps = new Map()

/**
 * 发布应用
 */
export const publishApp = (app) => {
  const id = 'app_' + Date.now()

  apps.set(id, {
    ...app,
    id,
    status: 'PUBLISHED',
  })

  return id
}

/**
 * 安装应用
 */
export const installApp = (tenantId, appId) => {
  const app = apps.get(appId)

  if (!app) return null

  return {
    tenantId,
    appId,
    installedAt: Date.now(),
  }
}

/**
 * 获取市场应用
 */
export const getApps = () => {
  return Array.from(apps.values())
}
