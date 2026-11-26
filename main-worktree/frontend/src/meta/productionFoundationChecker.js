import { runFoundationCheck as runLegacyFoundationCheck } from './manufacturing/manufacturingFoundationChecker.js?legacy'

const LOCAL_FORMAL_FACT_CHECKS = new Set(['work-centers-enabled', 'shifts-exist'])

export function runFoundationCheck() {
  return runLegacyFoundationCheck().map((item) => (
    LOCAL_FORMAL_FACT_CHECKS.has(item.id)
      ? {
          ...item,
          status: 'missing',
          message: 'localStorage样例已退出正式事实，等待服务端正式对象接入。',
          suggestion: '按Phase 3后续阶段通过正式服务端入口建设，不得恢复localStorage正式写入。',
        }
      : item
  ))
}
