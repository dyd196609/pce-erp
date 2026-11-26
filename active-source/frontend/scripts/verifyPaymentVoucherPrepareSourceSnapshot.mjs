import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceSnapshot.js'
import {
  runPaymentVoucherPrepareSourceSnapshotTestMatrix,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSourceSnapshotTestMatrix.js'

const report = runPaymentVoucherPrepareSourceSnapshotTestMatrix()

console.log(`页面版本目标：${report.matrixVersion}`)
console.log(`快照适配器版本：${PAYMENT_VOUCHER_PREPARE_SOURCE_ADAPTER_VERSION}`)
console.log(`快照契约版本：${report.snapshotContractVersion}`)
console.log(`快照契约指纹：${report.snapshotContractFingerprint}`)
console.log(`快照契约锁定指纹：${report.snapshotContractLockedFingerprint}`)
console.log(`快照字段数：${report.snapshotFieldCount}`)
console.log(`来源数据指纹版本：${report.fingerprintVersion}`)
console.log(`来源变更检测器版本：${report.changeDetectorVersion}`)
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

