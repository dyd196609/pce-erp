import { spawnSync } from 'node:child_process'

const VERSION = 'V1.14.2.8.4.7.50.1'
const commands = [
  ['npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', 'payment_order_prepare_validated_ready']],
  ['node', ['scripts/verifyPaymentOrderPrepareV501Guards.mjs']],
  ['npx.cmd', ['playwright', 'test', 'tests/ui-baseline/paymentOrderPrepareV501.spec.js', '--config=playwright.v501.config.js']],
  ['npm.cmd', ['run', 'build']],
  ['node', ['scripts/finalizePaymentOrderPrepareV501.mjs']],
  ['npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', 'payment_order_prepare_standard_list_ready']],
  ['npm.cmd', ['run', 'archive:pce-checkpoint', '--', 'payment_order_prepare_standard_list_ready']],
]
for (const [command, args] of commands) {
  console.log(`[${VERSION}] ${command} ${args.join(' ')}`)
  let result = spawnSync(command, args, { cwd: process.cwd(), stdio: 'inherit', shell: process.platform === 'win32' })
  if (result.status !== 0 && command === 'npm.cmd' && args[0] === 'run' && args[1] === 'build') {
    console.log(`[${VERSION}] transient build gate process failure; retrying npm.cmd run build once`)
    result = spawnSync(command, args, { cwd: process.cwd(), stdio: 'inherit', shell: process.platform === 'win32' })
  }
  if (result.status !== 0) process.exit(result.status ?? 1)
}
