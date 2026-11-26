import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const playwrightCli = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js')
const result = spawnSync(process.execPath, [
  playwrightCli,
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/purchaseToFormalPaymentGoldenFlow.spec.js',
], {
  cwd: root,
  env: process.env,
  stdio: 'inherit',
})

process.exit(result.status ?? 1)
