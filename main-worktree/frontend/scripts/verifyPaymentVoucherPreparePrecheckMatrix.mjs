import {
  runPaymentVoucherPreparePrecheckTestMatrix,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckTestMatrix.js'

const report = runPaymentVoucherPreparePrecheckTestMatrix()

console.log(`矩阵版本：${report.matrixVersion}`)
console.log(`引擎版本：${report.engineVersion}`)
console.log(`规则集版本：${report.ruleSetVersion}`)
console.log(`输入契约版本：${report.inputContractVersion}`)
console.log(`回归基线版本：${report.regressionBaselineVersion}`)
console.log(`执行方式：${report.executionMode}`)
console.log(`用例总数：${report.testCaseCount}`)
console.log(`通过用例数：${report.passedCaseCount}`)
console.log(`失败用例数：${report.failedCaseCount}`)
console.log(`断言总数：${report.assertionCount}`)
console.log(`失败断言数：${report.failedAssertionCount}`)

if (report.failedAssertionCount > 0) {
  console.log('失败断言：')
  report.failedAssertions.forEach((failure) => {
    console.log(`- ${failure.caseId} ${failure.assertion} 预期=${JSON.stringify(failure.expected)} 实际=${JSON.stringify(failure.actual)}`)
  })
  process.exitCode = 1
} else {
  console.log('付款凭证准备纯函数预检查测试矩阵全部通过。')
  process.exitCode = 0
}
