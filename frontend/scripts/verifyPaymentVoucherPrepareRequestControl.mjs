import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationRequestPackage.js'
import {
  runPaymentVoucherPrepareRequestControlTestMatrix,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareRequestControlTestMatrix.js'

const report = runPaymentVoucherPrepareRequestControlTestMatrix()

console.log(`页面版本目标：${report.matrixVersion}`)
console.log(`请求适配器版本：${PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION}`)
console.log(`请求输入包契约版本：${report.requestPackageContractVersion}`)
console.log(`请求输入包契约指纹：${report.requestPackageContractFingerprint}`)
console.log(`请求输入包契约锁定指纹：${report.requestPackageContractLockedFingerprint}`)
console.log(`请求字段数：${report.requestPackageFieldCount}`)
console.log(`幂等策略版本：${report.idempotencyVersion}`)
console.log(`幂等策略指纹：${report.idempotencyPolicyFingerprint}`)
console.log(`幂等策略锁定指纹：${report.idempotencyPolicyLockedFingerprint}`)
console.log(`并发策略版本：${report.concurrencyVersion}`)
console.log(`并发策略指纹：${report.concurrencyPolicyFingerprint}`)
console.log(`并发策略锁定指纹：${report.concurrencyPolicyLockedFingerprint}`)
console.log(`测试用例数：${report.testCaseCount}`)
console.log(`通过用例数：${report.passedCaseCount}`)
console.log(`失败用例数：${report.failedCaseCount}`)
console.log(`断言数：${report.assertionCount}`)
console.log(`失败断言数：${report.failedAssertionCount}`)
console.log(`副作用检查结果：${report.protection.businessDataWritten ? 'failed' : 'passed'}`)
console.log(`整体结果：${report.overallStatus}`)

if (report.overallStatus !== 'passed') {
  console.log(JSON.stringify(report.failedAssertions, null, 2))
  process.exitCode = 1
}

