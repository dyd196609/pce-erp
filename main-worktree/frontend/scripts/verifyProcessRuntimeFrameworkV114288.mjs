import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { executeProcessAction } from '../src/meta/process/runtime/processRuntimeEngine.js'
import { runProcessAcceptance } from '../src/meta/process/runtime/processAcceptanceFramework.js'
import { PROCESS_RUNTIME_REFERENCE_DEFINITION } from '../src/meta/process/runtime/processRuntimeReferenceDefinition.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const report = runProcessAcceptance(PROCESS_RUNTIME_REFERENCE_DEFINITION)
const execution = executeProcessAction(
  PROCESS_RUNTIME_REFERENCE_DEFINITION,
  PROCESS_RUNTIME_REFERENCE_DEFINITION.contexts[0],
  'COMPLETE_PREPARATION',
)

const expected = [
  ['Node Contract', report.contracts.node.result],
  ['Action Contract', report.sections.action.result],
  ['State Contract', report.sections.state.result],
  ['Handoff', report.sections.handoff.result],
  ['Context', report.contracts.context.result],
  ['Acceptance', report.result],
  ['Regression', report.sections.regression.result],
]

if (execution.transition.to !== 'prepared' || execution.handoff?.toNode !== 'work-item-review') {
  throw new Error('PROCESS_RUNTIME_CLOSED_LOOP_FAILED')
}

for (const [label, result] of expected) {
  console.log(`${label} ${result}`)
  if (result !== 'PASS') process.exitCode = 1
}

if (!process.exitCode) {
  const viteEntry = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
  const build = spawnSync(process.execPath, [viteEntry, 'build', '.'], {
    cwd: frontendRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  if (build.status !== 0) {
    process.stderr.write(build.stdout || '')
    process.stderr.write(build.stderr || '')
    throw new Error(`PROCESS_RUNTIME_BUILD_FAILED:${build.status}`)
  }
  console.log('Build PASS')
  console.log('PCE_PROCESS_RUNTIME_FRAMEWORK_READY')
}

