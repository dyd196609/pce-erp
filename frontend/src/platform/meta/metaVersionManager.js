/**
 * ============================
 * Meta Version Manager V10
 * ============================
 */

const metaStore = new Map()

/**
 * 创建版本
 */
export const createMetaVersion = (metaId, meta) => {
  const version = getLatestVersion(metaId) + 1

  const record = {
    metaId,
    version,
    status: 'DRAFT',
    meta,
    createdAt: Date.now(),
  }

  const list = metaStore.get(metaId) || []
  list.push(record)

  metaStore.set(metaId, list)

  return record
}

/**
 * 获取最新版本
 */
export const getLatestVersion = (metaId) => {
  const list = metaStore.get(metaId) || []

  if (list.length === 0) return 0

  return Math.max(...list.map((v) => v.version))
}

/**
 * 发布版本（核心）
 */
export const publishMeta = (metaId, version) => {
  const list = metaStore.get(metaId) || []

  list.forEach((v) => {
    if (v.version === version) {
      v.status = 'PUBLISHED'
      v.publishedAt = Date.now()
    }
  })

  metaStore.set(metaId, list)
}

/**
 * 获取已发布版本
 */
export const getPublishedMeta = (metaId) => {
  const list = metaStore.get(metaId) || []

  return list.find((v) => v.status === 'PUBLISHED')
}

/**
 * 获取运行时Meta
 */
export const getRuntimeMeta = (metaId) => {
  return getPublishedMeta(metaId)?.meta
}
