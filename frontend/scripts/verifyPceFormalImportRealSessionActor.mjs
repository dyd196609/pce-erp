import { spawnSync } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { resolvePcePythonRuntime } from './pcePythonExecutable.mjs'

const root = path.resolve(import.meta.dirname, '..', '..')
const python = resolvePcePythonRuntime(root)
const result = spawnSync(python.executable, [path.join(root, 'backend', 'scripts', 'verify_wave1_real_session_actor.py')], {
  cwd: root,
  env: { ...python.env, PYTHONDONTWRITEBYTECODE: '1' },
  encoding: 'utf8',
  stdio: 'inherit',
})
if (result.error) throw result.error
process.exit(result.status ?? 1)
