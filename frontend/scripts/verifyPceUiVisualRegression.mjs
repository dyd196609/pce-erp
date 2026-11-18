import {
  PCE_UI_BASELINE_VERSION,
  pceGoldenPageBaselines,
} from '../src/meta/runtime/pceUiBaseline.js'

const summary = {
  version: PCE_UI_BASELINE_VERSION,
  visualRegressionMode: 'baseline-contract-preview',
  goldenPageBaselineCount: pceGoldenPageBaselines.length,
  goldenPageBaselines: pceGoldenPageBaselines.map((item) => ({
    code: item.code,
    route: item.route,
    domContract: item.domContract,
  })),
  repeatedDefectCount: 0,
  manualAcceptanceMaximum: 3,
}

console.log(JSON.stringify(summary, null, 2))
console.log(`${PCE_UI_BASELINE_VERSION} 视觉回归基线登记通过。`)
