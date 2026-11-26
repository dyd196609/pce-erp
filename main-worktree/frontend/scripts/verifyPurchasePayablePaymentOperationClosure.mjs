import fs from 'node:fs'
import { spawnSync } from 'node:child_process'

const npmCli = process.env.npm_execpath
const npmCommand = npmCli ? process.execPath : (process.platform === 'win32' ? 'npm.cmd' : 'npm')

const commands = [
  ['verify:business-process-navigation', ['run', 'verify:business-process-navigation']],
  ['verify:purchase-payable-payment-flow', ['run', 'verify:purchase-payable-payment-flow']],
  ['verify:purchase-payment-page-layouts', ['run', 'verify:purchase-payment-page-layouts']],
  ['verify:purchase-payment-page-actions', ['run', 'verify:purchase-payment-page-actions']],
  ['verify:business-table-horizontal-scroll', ['run', 'verify:business-table-horizontal-scroll']],
  ['verify:purchase-payable-action-page-observability', ['run', 'verify:purchase-payable-action-page-observability']],
  ['verify:business-action-result-page-isolation', ['run', 'verify:business-action-result-page-isolation']],
  ['verify:purchase-payable-payment-actions', ['run', 'verify:purchase-payable-payment-actions']],
  ['verify:purchase-payable-payment-writeback', ['run', 'verify:purchase-payable-payment-writeback']],
  ['verify:purchase-payable-payment-release', ['run', 'verify:purchase-payable-payment-release']],
  ['verify:purchase-payable-payment-application-closure', ['run', 'verify:purchase-payable-payment-application-closure']],
]

function runCommand(name, args) {
  console.log(`\n[operation-closure] 开始：${name}`)
  const result = spawnSync(npmCommand, npmCli ? [npmCli, ...args] : args, {
    cwd: process.cwd(),
    stdio: 'pipe',
    encoding: 'utf8',
  })
  const passed = result.status === 0
  if (result.stdout) console.log(result.stdout.trim())
  if (result.stderr) console.error(result.stderr.trim())
  if (result.error) console.error(result.error.message)
  console.log(`[operation-closure] 结果：${name} => ${passed ? 'passed' : 'failed'}`)
  return {
    name,
    status: passed ? 'passed' : 'failed',
    exitCode: result.status,
  }
}

const results = []
for (const [name, args] of commands) {
  const result = runCommand(name, args)
  results.push(result)
  if (result.status !== 'passed') break
}

const playwrightPackagePath = 'node_modules/@playwright/test/package.json'
if (results.every((item) => item.status === 'passed')) {
  if (fs.existsSync(playwrightPackagePath)) {
    const result = runCommand('playwright:purchase-payment-layout', [
      'exec',
      '--',
      'playwright',
      'test',
      '-c',
      'playwright.runtime.config.js',
      'tests/business-flow/purchasePayablePaymentLayout.spec.js',
    ])
    results.push(result)
  } else {
    results.push({
      name: 'playwright:purchase-payment-layout',
      status: 'skipped',
      reason: '@playwright/test 未安装，本轮不伪造浏览器验证通过。',
    })
    console.log('\n[operation-closure] 浏览器自动验证：skipped（@playwright/test 未安装）')
  }
}

const finalCommands = [
  ['verify:payment-voucher-release-gate', ['run', 'verify:payment-voucher-release-gate']],
  ['build', ['run', 'build']],
]

if (results.filter((item) => item.status === 'failed').length === 0) {
  for (const [name, args] of finalCommands) {
    const result = runCommand(name, args)
    results.push(result)
    if (result.status !== 'passed') break
  }
}

const failed = results.filter((item) => item.status === 'failed')
console.log('\nV1.14.2.7 采购应付至付款申请闭环、页面诊断与真实浏览器验收汇总')
results.forEach((item) => {
  console.log(`${item.name}: ${item.status}${item.reason ? `（${item.reason}）` : ''}`)
})
console.log(`总体结果：${failed.length === 0 ? 'passed' : 'failed'}`)

if (failed.length > 0) {
  process.exitCode = 1
}

