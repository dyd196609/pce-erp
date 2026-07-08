// ======================================
// Meta Runtime V16 - Control Center
// 运行时统一控制台
// ======================================

import { getAllERP, getERP } from '../registry/metaRegistry'

// ==========================
// ERP实例池
// ==========================
const runtimeInstances = new Map()

// 注册运行实例
export const registerInstance = (instance) => {
  const id = instance?.id || `inst_${Date.now()}`
  runtimeInstances.set(id, instance)
  return id
}

// 获取实例
export const getInstance = (id) => {
  return runtimeInstances.get(id)
}

// 获取所有运行实例
export const getAllInstances = () => {
  return Array.from(runtimeInstances.values())
}

// ==========================
// 控制操作
// ==========================

// 启动ERP
export const startERP = (id) => {
  const erp = getERP(id)
  if (!erp) return null

  const instance = {
    id,
    meta: erp.meta,
    status: 'DRAFT',
    bpmState: 'DRAFT',
    startedAt: new Date(),
  }

  return registerInstance(instance)
}

// 停止ERP
export const stopERP = (id) => {
  const inst = runtimeInstances.get(id)
  if (!inst) return false

  inst.status = 'STOPPED'
  return true
}

// ==========================
// 控制台数据
// ==========================
export const getControlDashboard = () => {
  return {
    totalERP: getAllERP().length,
    runningInstances: runtimeInstances.size,
    instances: getAllInstances(),
  }
}

import { emitEvent } from '../core/metaEventBus'

export const transitionERP = (id, action) => {
  const inst = runtimeInstances.get(id)
  if (!inst) return

  inst.bpmState = action

  emitEvent('BPM_CHANGE', {
    id,
    state: action,
  })
}
