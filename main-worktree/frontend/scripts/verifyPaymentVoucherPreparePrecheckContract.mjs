import {
  runPaymentVoucherPreparePrecheckGovernanceVerification,
} from '../src/meta/finance/payment-voucher-prepare-simulation/paymentVoucherPreparePrecheckBaselines.js'

const report = runPaymentVoucherPreparePrecheckGovernanceVerification()

console.log(`规则集版本：${report.ruleSetVersion}`)
console.log(`规则集指纹：${report.ruleSetFingerprint}`)
console.log(`规则集锁定指纹：${report.ruleSetLockedFingerprint}`)
console.log(`规则数：${report.ruleCount}`)
console.log(`规则编码是否唯一：${report.ruleCodesUnique}`)
console.log(`规则顺序是否稳定：${report.ruleSequenceStable}`)
console.log(`输入契约版本：${report.inputContractVersion}`)
console.log(`输入契约指纹：${report.inputContractFingerprint}`)
console.log(`输入契约锁定指纹：${report.inputContractLockedFingerprint}`)
console.log(`输入字段数：${report.inputContractFieldCount}`)
console.log(`字段名是否唯一：${report.inputFieldNamesUnique}`)
console.log(`类型是否合法：${report.inputTypesValid}`)
console.log(`枚举是否合法：${report.inputEnumsValid}`)
console.log(`回归基线版本：${report.baselineVersion}`)
console.log(`回归基线指纹：${report.baselineFingerprint}`)
console.log(`回归基线锁定指纹：${report.baselineLockedFingerprint}`)
console.log(`基线数：${report.baselineCount}`)
console.log(`通过基线数：${report.passedBaselineCount}`)
console.log(`失败基线数：${report.failedBaselineCount}`)
console.log(`规则向量长度：${report.ruleVectorLength}`)
console.log(`规则顺序是否变化：${report.ruleOrderChanged}`)
console.log(`整体结果：${report.overallStatus}`)

if (report.overallStatus !== 'passed') {
  console.log('治理验证失败，请检查规则集、输入契约或回归基线锁定值。')
  process.exitCode = 1
} else {
  console.log('付款凭证准备预检查版本治理验证通过。')
  process.exitCode = 0
}
