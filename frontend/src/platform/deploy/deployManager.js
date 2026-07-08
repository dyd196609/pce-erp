/**
 * ============================
 * Meta Runtime V12 - Deploy System
 * ============================
 */

const apps = new Map()

/**
 * 安装应用
 */
export const installApp = (metaBundle) => {
  const appId = metaBundle.id

  apps.set(appId, {
    ...metaBundle,
    status: 'INSTALLED',
  })

  return appId
}

/**
 * 启动应用
 */
export const startApp = (appId) => {
  const app = apps.get(appId)

  if (!app) return null

  app.status = 'RUNNING'

  return app
}

/**
 * 发布应用（商业能力）
 */
export const publishApp = (appId) => {
  const app = apps.get(appId)

  app.status = 'PUBLISHED'

  return app
}
