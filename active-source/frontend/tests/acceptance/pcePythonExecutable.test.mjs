import assert from 'node:assert/strict'
import test from 'node:test'
import path from 'node:path'

import { resolvePcePython, resolvePcePythonRuntime } from '../../scripts/pcePythonExecutable.mjs'

test('explicit PCE_PYTHON override remains authoritative', () => {
  assert.equal(resolvePcePython('D:\\repo', { PCE_PYTHON: 'X:\\python.exe' }), 'X:\\python.exe')
})

test('repository runtime resolves the existing backend virtual environment', () => {
  const repositoryRoot = path.resolve(import.meta.dirname, '..', '..', '..')
  assert.equal(
    resolvePcePython(repositoryRoot, {}),
    path.join(repositoryRoot, 'backend', 'venv', 'Scripts', 'python.exe'),
  )
})

test('runtime uses the venv base executable with its site-packages when the launcher is not portable', () => {
  const repositoryRoot = path.resolve(import.meta.dirname, '..', '..', '..')
  const runtime = resolvePcePythonRuntime(repositoryRoot, {})
  assert.match(runtime.executable, /python\.exe$/i)
  assert.match(runtime.env.PYTHONPATH, /backend[\\/]venv[\\/]Lib[\\/]site-packages/i)
})
