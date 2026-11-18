import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { resolvePcePythonRuntime } from './pcePythonExecutable.mjs'

const root = path.resolve(import.meta.dirname, '..', '..')
const python = resolvePcePythonRuntime(root)
const result = spawnSync(python.executable, ['scripts/verify_wave1_import_template_localization.py'], {
  cwd: path.join(root, 'backend'),
  env: python.env,
  encoding: 'utf8',
})
process.stdout.write(result.stdout || '')
process.stderr.write(result.stderr || '')
if (result.status !== 0) process.exit(result.status || 1)
