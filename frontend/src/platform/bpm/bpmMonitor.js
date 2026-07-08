/**
 * ============================
 * BPM Runtime Monitor V10
 * ============================
 */

const instances = []

/**
 * 创建流程实例
 */
export const createInstance = (processId, row) => {
  const instance = {
    id: generateId(),
    processId,
    row,
    status: 'RUNNING',
    currentNode: 'start',
    history: [],
  }

  instances.push(instance)

  return instance
}

/**
 * 推进节点
 */
export const moveToNext = (instanceId, node) => {
  const ins = instances.find((i) => i.id === instanceId)

  ins.currentNode = node

  ins.history.push({
    node,
    time: Date.now(),
  })

  return ins
}

/**
 * 获取实例状态
 */
export const getInstance = (id) => {
  return instances.find((i) => i.id === id)
}

/**
 * 获取所有实例
 */
export const getAllInstances = () => instances
