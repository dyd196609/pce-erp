import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES } from './formalPriceApprovalEndToEndSafetyDrillStageModel.js'

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_MATRIX_VERSION = 'V1.14.2.8.6.15'

export function buildFormalPriceApprovalEndToEndSafetyDrillMatrix(stageResults = {}) {
  const rows = Object.freeze(FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STAGES.map((stage) => {
    const supplied = stageResults[stage.stageCode]
    return Object.freeze({
      stageCode: stage.stageCode,
      order: stage.order,
      result: supplied === 'PASS' || supplied === 'FAIL' ? supplied : 'MISSING',
      executionAllowed: false,
    })
  }))
  return Object.freeze({
    rows,
    stageCount: rows.length,
    passedCount: rows.filter((row) => row.result === 'PASS').length,
    failedCount: rows.filter((row) => row.result === 'FAIL').length,
    missingCount: rows.filter((row) => row.result === 'MISSING').length,
    complete: rows.every((row) => row.result === 'PASS'),
    drillIsExecution: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
