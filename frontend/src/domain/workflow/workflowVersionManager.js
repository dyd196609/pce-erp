// =====================================
// BPM V5 - 流程版本管理系统
// =====================================

// =========================
// 流程仓库（模拟数据库）
// =========================
const processRegistry = {
  purchaseOrder: [
    {
      version: 1,
      status: 'published',
      definition: null,
    },
  ],
}

// =========================
// 创建新版本（草稿）
// =========================
export const createVersion = (module, definition) => {
  const versions = processRegistry[module] || []

  const newVersion = {
    version: versions.length + 1,
    status: 'draft',
    definition,
  }

  versions.push(newVersion)
  processRegistry[module] = versions

  return newVersion
}

// =========================
// 发布版本（核心）
// =========================
export const publishVersion = (module, version) => {
  const versions = processRegistry[module]

  versions.forEach((v) => {
    if (v.version === version) {
      v.status = 'published'
    }
  })

  // 其他版本降级
  versions.forEach((v) => {
    if (v.version !== version) {
      v.status = 'disabled'
    }
  })

  return versions.find((v) => v.version === version)
}

// =========================
// 获取当前发布版本
// =========================
export const getActiveVersion = (module) => {
  const versions = processRegistry[module] || []
  return versions.find((v) => v.status === 'published')
}

// =========================
// 回滚版本（关键能力）
// =========================
export const rollbackVersion = (module, version) => {
  return publishVersion(module, version)
}

// =========================
// 获取所有版本
// =========================
export const getVersions = (module) => {
  return processRegistry[module] || []
}
