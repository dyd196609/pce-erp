import { spawnSync } from 'node:child_process'

const VERSION = 'V1.14.2.8.4.7.50.2'
const checkpointIds = [
  'pce_web_acceptance_v1_1_framework_ready',
  'pce_web_acceptance_v1_1_finance_chain_ready',
  'pce_web_acceptance_v1_1_full_project_ready',
]
const commands = [
  ['npm.cmd', ['run', 'gate:pce-web-acceptance:static']],
  ['npm.cmd', ['run', 'gate:pce-web-acceptance:runtime']],
  ['npm.cmd', ['run', 'build']],
  ['node', ['scripts/finalizePceWebAcceptanceScopedV11.mjs']],
  ...checkpointIds.flatMap(checkpointId => [
    ['npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', checkpointId]],
    ['npm.cmd', ['run', 'archive:pce-checkpoint', '--', checkpointId]],
    ['node', ['scripts/verifyPceWebAcceptanceArchive.mjs', checkpointId]],
  ]),
]
for (const [command, args] of commands) {
  console.log(`[${VERSION}] ${command} ${args.join(' ')}`)
  const result = spawnSync(command, args, { cwd: process.cwd(), stdio: 'inherit', shell: process.platform === 'win32' })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
