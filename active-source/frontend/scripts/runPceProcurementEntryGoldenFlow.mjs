import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function run(args) {
  const result = spawnSync(process.execPath, args, {
    cwd: root,
    env: { ...process.env, PCE_GOLDEN_RUNNER_TRACE: '1' },
    stdio: 'inherit',
  })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

run(['scripts/verifyPceProcurementEntryGoldenFlow.mjs'])
run([
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/procurementEntryGoldenFlow.spec.js',
])
