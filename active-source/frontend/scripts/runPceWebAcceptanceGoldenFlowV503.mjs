import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const VERSION = 'V1.14.2.8.4.7.50.3'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v11-strict-golden-flow')
const steps = [
  ['strict-static', 'npm.cmd run verify:web-acceptance:strict'],
  ['changed-page-gate', 'npm.cmd run gate:web-acceptance:changed'],
  ['full-project-inventory', 'npm.cmd run gate:web-acceptance'],
  ['strict-real-browser', 'npm.cmd run gate:web-acceptance:strict-browser'],
  ['cross-process-recovery', 'npm.cmd run gate:web-acceptance:strict-recovery', { PCE_V503_BASE_URL: 'http://localhost:5183' }],
  ['production-build', 'npm.cmd run build'],
  ['finalize-checkpoint', 'node scripts/finalizePceWebAcceptanceV503.mjs'],
  ['restore-checkpoint', 'npm.cmd run verify:pce-golden-checkpoint-restore -- pce_web_acceptance_v11_strict_pages_ready'],
  ['archive-checkpoint', 'npm.cmd run archive:pce-checkpoint -- pce_web_acceptance_v11_strict_pages_ready'],
  ['verify-archive', 'node scripts/verifyPceWebAcceptanceV503Archive.mjs'],
]
const runnerReport = path.join(resultRoot, 'unified-runner-report.json')
let results = []
let startIndex = 0
if (fs.existsSync(runnerReport)) {
  const previous = JSON.parse(fs.readFileSync(runnerReport, 'utf8'))
  const failedIndex = steps.findIndex(([step]) => step === previous.firstFailedStep)
  if (previous.result === 'failed' && failedIndex > 0
    && previous.steps.slice(0, failedIndex).every(step => step.exitCode === 0)) {
    results = previous.steps.slice(0, failedIndex)
    startIndex = failedIndex
  }
}
for (const [step, commandLine, extraEnv = {}] of steps.slice(startIndex)) {
  const startedAt = new Date().toISOString()
  const execution = spawnSync(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', commandLine], {
    cwd: frontend,
    env: { ...process.env, ...extraEnv },
    encoding: 'utf8',
    stdio: ['inherit', 'pipe', 'pipe'],
    shell: false,
  })
  if (execution.stdout) process.stdout.write(execution.stdout)
  if (execution.stderr) process.stderr.write(execution.stderr)
  const exitCode = execution.status ?? 1
  results.push({
    step,
    command: commandLine,
    executionMode: commandLine.startsWith('npm.cmd') ? 'npm.cmd_via_cmd.exe' : 'node_via_cmd.exe',
    startedAt,
    completedAt: new Date().toISOString(),
    exitCode,
  })
  if (exitCode !== 0) {
    fs.mkdirSync(resultRoot, { recursive: true })
    fs.writeFileSync(runnerReport, `${JSON.stringify({
      result: 'failed', version: VERSION, firstFailedStep: step, exitCode, steps: results,
    }, null, 2)}\n`)
    process.exit(exitCode)
  }
}
fs.writeFileSync(runnerReport, `${JSON.stringify({
  result: 'passed',
  version: VERSION,
  runnerVersion: VERSION,
  stepCount: steps.length,
  firstFailedStep: null,
  exitCode: 0,
  steps: results,
}, null, 2)}\n`)
console.log(JSON.stringify({ result: 'passed', version: VERSION, stepCount: steps.length }, null, 2))
