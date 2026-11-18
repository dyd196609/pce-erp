import {
  runPaymentVoucherPrepareSimulationResultTestMatrix,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPrepareSimulationResultTestMatrix.js'

const report = runPaymentVoucherPrepareSimulationResultTestMatrix()

console.log('页面修订版本目标：V1.13.67.1')
console.log(`模拟结果测试矩阵版本：${report.matrixVersion}`)
console.log(`结果适配器版本：${report.resultAdapterVersion}`)
console.log(`结果记录契约版本：${report.resultContractVersion}`)
console.log(`结果明细契约版本：${report.resultLineContractVersion}`)
console.log(`结果契约指纹：${report.resultContractFingerprint}`)
console.log(`结果契约锁定指纹：${report.resultContractLockedFingerprint}`)
console.log(`结果字段数：${report.resultFieldCount}`)
console.log(`结果明细字段数：${report.resultLineFieldCount}`)
console.log(`生命周期策略版本：${report.lifecycleVersion}`)
console.log(`生命周期策略指纹：${report.lifecyclePolicyFingerprint}`)
console.log(`生命周期锁定指纹：${report.lifecyclePolicyLockedFingerprint}`)
console.log(`审计契约版本：${report.auditContractVersion}`)
console.log(`审计契约指纹：${report.auditContractFingerprint}`)
console.log(`审计契约锁定指纹：${report.auditContractLockedFingerprint}`)
console.log(`审计字段数：${report.auditFieldCount}`)
console.log(`结果存储命名空间：${report.resultStorageNamespace}`)
console.log(`审计存储命名空间：${report.auditStorageNamespace}`)
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
