/**
 * ============================
 * BPM Registry V11（生产级）
 * ============================
 */

const instances = new Map()

/**
 * 创建实例
 */
export const createInstance = (metaId, row) => {
  const id = generateId()

  const instance = {
    id,
    metaId,
    row,
    status: 'RUNNING',
    history: [],
    createdAt: Date.now(),
  }

  instances.set(id, instance)

  return instance
}

/**
 * 更新节点
 */
export const updateInstance = (id, patch) => {
  const ins = instances.get(id)

  if (!ins) return null

  Object.assign(ins, patch)

  return ins
}

/**
 * 获取实例
 */
export const getInstance = (id) => {
  return instances.get(id)
}

/**
 * 获取所有实例（监控用）
 */
export const getAllInstances = () => {
  return Array.from(instances.values())
}

/**
 * 生成ID
 */
function generateId() {
  return 'bpm_' + Math.random().toString(36).slice(2, 10)
}
