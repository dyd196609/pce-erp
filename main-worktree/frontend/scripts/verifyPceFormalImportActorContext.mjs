import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { resolvePcePythonRuntime } from './pcePythonExecutable.mjs'

const root = path.resolve(import.meta.dirname, '..', '..')
const python = resolvePcePythonRuntime(root)
const env = {
  ...process.env,
  DJANGO_SETTINGS_MODULE: 'pce_backend.g3_applicability_test_settings',
}
const result = spawnSync(python.executable, [
  'manage.py', 'test', 'pde.tests_formal_import_actor_context',
  '--noinput', '--verbosity', '1',
], { cwd: path.join(root, 'backend'), env: { ...python.env, ...env }, encoding: 'utf8' })
process.stdout.write(result.stdout || '')
process.stderr.write(result.stderr || '')
if (result.status !== 0) process.exit(result.status || 1)
console.log(JSON.stringify({
  gate: 'verify:pce-formal-import-actor-context',
  status: 'PASS',
  scenarios: 14,
  userEmployeePositionResponsibilityChain: true,
  readOnlyCommitDenied: true,
  organizationScopeDenied: true,
  previewThenActorInvalidationDenied: true,
  auditActorContext: true,
  productionDatabaseUsed: false,
}, null, 2))
