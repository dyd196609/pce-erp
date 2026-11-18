import { spawnSync } from 'node:child_process'

const commands = [
  ['verify:payment-voucher-precheck', ['run', 'verify:payment-voucher-precheck']],
  ['verify:payment-voucher-precheck-contract', ['run', 'verify:payment-voucher-precheck-contract']],
  ['verify:payment-voucher-source-snapshot', ['run', 'verify:payment-voucher-source-snapshot']],
  ['verify:payment-voucher-request-control', ['run', 'verify:payment-voucher-request-control']],
  ['verify:payment-voucher-simulation-result', ['run', 'verify:payment-voucher-simulation-result']],
  ['verify:payment-voucher-simulation-guard', ['run', 'verify:payment-voucher-simulation-guard']],
  ['verify:payment-voucher-acceptance-manifest', ['run', 'verify:payment-voucher-acceptance-manifest']],
  ['verify:payment-voucher-page-acceptance', ['run', 'verify:payment-voucher-page-acceptance']],
  ['build', ['run', 'build']],
]

const npmCli = process.env.npm_execpath
const npmCommand = npmCli ? process.execPath : (process.platform === 'win32' ? 'npm.cmd' : 'npm')
const results = []

for (const [name, args] of commands) {
  console.log(`\n[release-gate] 寮€濮嬶細${name}`)
  const result = spawnSync(npmCommand, npmCli ? [npmCli, ...args] : args, {
    cwd: process.cwd(),
    stdio: 'pipe',
    encoding: 'utf8',
  })
  const passed = result.status === 0
  results.push({
    name,
    status: passed ? 'passed' : 'failed',
    exitCode: result.status,
  })
  if (result.stdout) console.log(result.stdout.trim())
  if (result.stderr) console.error(result.stderr.trim())
  if (result.error) console.error(result.error.message)
  console.log(`[release-gate] 缁撴灉锛?{name} => ${passed ? 'passed' : 'failed'}`)
  if (!passed) break
}

const failed = results.filter((item) => item.status !== 'passed')
console.log('\n浠樻鍑瘉鍑嗗 V1.14.2.7.1 鍙戝竷闂搁棬姹囨€?)
results.forEach((item) => {
  console.log(`${item.name}: ${item.status}`)
})
console.log(`鍙戝竷闂搁棬鎬讳綋缁撴灉锛?{failed.length === 0 ? 'passed' : 'failed'}`)

if (failed.length > 0) {
  process.exitCode = 1
}

