/**
 * ============================
 * Meta Runtime V18 - Release System
 * ============================
 */

const releases = []

// 创建发布
export const createRelease = (meta) => {
  const release = {
    id: 'rel_' + Date.now(),
    meta,
    env: 'dev',
    status: 'DRAFT',
  }

  releases.push(release)
  return release
}

// 发布到生产
export const publishToProd = (releaseId) => {
  const rel = releases.find((r) => r.id === releaseId)
  if (rel) {
    rel.env = 'prod'
    rel.status = 'PUBLISHED'
  }
  return rel
}

// 回滚
export const rollback = (releaseId) => {
  const rel = releases.find((r) => r.id === releaseId)
  if (rel) {
    rel.status = 'ROLLED_BACK'
  }
  return rel
}

// 获取发布列表
export const getReleases = () => releases
