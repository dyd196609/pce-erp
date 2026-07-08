/**
 * ============================
 * Meta OS Kernel V20
 * 企业操作系统内核
 * ============================
 */

import { runPlatformV13 } from './metaKernelV13'
import { onEvent } from '../core/metaEventBus'

/**
 * OS调度器
 */
export const schedule = async (task) => {
  return runPlatformV13(task)
}

/**
 * 系统级事件处理
 */
export const bootOS = () => {
  onEvent('ERP_CREATED', (data) => {
    console.log('OS: ERP created', data)
  })

  onEvent('BPM_CHANGE', (data) => {
    console.log('OS: BPM changed', data)
  })
}

/**
 * 系统状态
 */
export const getSystemState = () => {
  return {
    status: 'RUNNING',
    uptime: Date.now(),
  }
}
