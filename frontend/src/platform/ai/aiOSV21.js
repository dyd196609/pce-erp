// ======================================
// Meta Runtime V21 - AI OS Entry
// 企业自治系统启动器
// ======================================

import { runAutonomousLoop } from './autonomousLoopV21'

export const startAutonomousEnterprise = () => {
  console.log('🚀 AI Enterprise OS V21 Started')

  setInterval(() => {
    runAutonomousLoop()
  }, 5000) // 每5秒自运行一次
}
