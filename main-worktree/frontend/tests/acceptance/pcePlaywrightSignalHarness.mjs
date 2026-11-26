import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import {
  createRuntimeCleanupCoordinator,
  createRuntimeIsolation,
  installSignalCleanupHandlers,
  startRuntimeCleanupWatchdog,
  updateRuntimeProcessOwnership,
} from '../../scripts/pcePlaywrightRunner.mjs'

const isolation = createRuntimeIsolation({
  env: { PCE_PLAYWRIGHT_TEMP_BASE: path.join(process.env.PCE_PLAYWRIGHT_TEST_TEMP_BASE || os.tmpdir(), 'pce-runner-signal-tests') },
  runId: `run-signal-harness-${process.pid}-${Date.now()}`,
})
const browser = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore', windowsHide: true })
const vite = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore', windowsHide: true })
const cleanupCoordinator = createRuntimeCleanupCoordinator({
  isolation,
  getBrowserProcess: () => browser,
  getViteProcess: () => vite,
  verifyPortReleased: async () => true,
})
updateRuntimeProcessOwnership(isolation, { browserPid: browser.pid, vitePid: vite.pid })

let signalLifecycle
signalLifecycle = installSignalCleanupHandlers({
  cleanupCoordinator,
  onSignal(result) {
    process.stdout.write(`HARNESS_RESULT ${JSON.stringify({ ...result, tempRoot: isolation.tempRoot })}\n`)
    signalLifecycle.remove()
  },
})

process.stdout.write(`HARNESS_READY ${JSON.stringify({ browserPid: browser.pid, vitePid: vite.pid, tempRoot: isolation.tempRoot })}\n`)
const requestedSignal = process.argv[2]
if (requestedSignal === 'SIGINT' || requestedSignal === 'SIGTERM') {
  // Windows has no POSIX signal delivery for process.kill(SIGINT/SIGTERM): it
  // terminates the process before Node can dispatch its registered listener.
  // Emit the exact Node signal event in this independently spawned harness so
  // the production handler cleans up real owned child processes.
  setTimeout(() => process.emit(requestedSignal), 50)
} else if (requestedSignal === 'WATCHDOG') {
  startRuntimeCleanupWatchdog(isolation)
  setTimeout(() => process.exit(73), 50)
}
