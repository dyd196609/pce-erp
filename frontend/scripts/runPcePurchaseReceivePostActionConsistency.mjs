import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function run(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, ...extraEnv }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

run(['scripts/verifyPcePurchaseReceivePostActionConsistency.mjs'])
run([
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/purchaseReceivePostActionConsistency.spec.js',
], { PCE_MANUAL_CHECKPOINT_TRACE: '1' })
run(['scripts/runPceGoldenCheckpointRestore.mjs', 'receive_ready'])
