import path from 'node:path'
import os from 'node:os'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { createHash, randomUUID } from 'node:crypto'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const frontendRoot = path.resolve(__dirname, '..')
export const sourceRoot = path.resolve(frontendRoot, '..')
export const projectRoot = path.resolve(sourceRoot, '..')
export const viteWatchRoot = frontendRoot
const isWindows = process.platform === 'win32'
const playwrightCli = path.join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js')
const viteCommand = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const cleanupWatchdogCommand = path.join(frontendRoot, 'scripts', 'pcePlaywrightCleanupWatchdog.mjs')
const ownerMarkerName = '.pce-playwright-run-owner.json'
const requiredHost = '127.0.0.1'
const requiredPort = 5173

export function isPathWithin(candidate, parent) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate))
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative))
}

export function validateRunId(runId) {
  if (!/^[a-z0-9][a-z0-9-]{11,80}$/i.test(String(runId || ''))) {
    throw new Error('RUN_ID_ISOLATION failed: missing or invalid run-id.')
  }
  return String(runId)
}

export function validateIsolationPaths({ tempRoot, profileRoot }) {
  const roots = [projectRoot, sourceRoot, frontendRoot, viteWatchRoot]
  for (const [label, candidate] of [['TEMP', tempRoot], ['PROFILE', profileRoot]]) {
    if (!candidate || roots.some((root) => isPathWithin(candidate, root))) {
      throw new Error(`${label}_OUTSIDE_PROJECT failed: ${candidate || '<missing>'}`)
    }
  }
  return true
}

export function assertPortOwnership(portAvailable) {
  if (!portAvailable) throw new Error('BLOCKED — PORT OWNERSHIP UNKNOWN')
  return true
}

export function assertRunRootAvailable(runRoot, exists = fs.existsSync) {
  if (exists(runRoot)) throw new Error(`RUN_ID_ISOLATION failed: run directory already exists: ${runRoot}`)
  return true
}

export function assertCleanupTargetOwnership({ runRoot, runId, marker }) {
  validateRunId(runId)
  validateIsolationPaths({ tempRoot: runRoot, profileRoot: runRoot })
  if (path.basename(runRoot) !== `pce-pw-${runId}` || marker?.runId !== runId || marker?.runRoot !== path.resolve(runRoot)) {
    throw new Error(`CLEANUP_TARGET_OWNERSHIP failed: ${runRoot}`)
  }
  return true
}

function candidateTempBases(env = process.env) {
  const explicit = String(env.PCE_PLAYWRIGHT_TEMP_BASE || '').trim()
  if (explicit) return { explicit: true, values: [explicit] }
  return {
    explicit: false,
    values: [
      env.TEMP,
      env.TMP,
      os.tmpdir(),
      env.LOCALAPPDATA ? path.join(env.LOCALAPPDATA, 'Temp') : '',
      env.SystemRoot ? path.join(env.SystemRoot, 'Temp') : '',
    ].filter(Boolean),
  }
}

export function selectSafeTempBase({ env = process.env, canUse = () => true } = {}) {
  const candidates = candidateTempBases(env)
  const seen = new Set()
  for (const value of candidates.values) {
    const resolved = path.resolve(value)
    const key = isWindows ? resolved.toLowerCase() : resolved
    if (seen.has(key)) continue
    seen.add(key)
    try {
      validateIsolationPaths({ tempRoot: resolved, profileRoot: resolved })
      if (canUse(resolved)) return resolved
    } catch (error) {
      if (candidates.explicit) throw error
    }
  }
  throw new Error('TEMP_OUTSIDE_PROJECT failed: no writable external temporary base is available.')
}

export function createRuntimeIsolation({ env = process.env, runId = `run-${Date.now().toString(36)}-${randomUUID()}` } = {}) {
  validateRunId(runId)
  let runRoot
  const tempBase = selectSafeTempBase({
    env,
    canUse(candidate) {
      try {
        const base = path.join(candidate, 'Dev-PCE-Playwright')
        fs.mkdirSync(base, { recursive: true })
        runRoot = path.join(base, `pce-pw-${runId}`)
        assertRunRootAvailable(runRoot)
        fs.mkdirSync(runRoot)
        return true
      } catch {
        runRoot = undefined
        return false
      }
    },
  })
  if (!runRoot) throw new Error('TEMP_OUTSIDE_PROJECT failed: external temporary directory could not be created.')
  const profileRoot = runRoot
  validateIsolationPaths({ tempRoot: runRoot, profileRoot })
  const marker = Object.freeze({
    contract: 'PCE-PLAYWRIGHT-RUN-OWNER-V1',
    runId,
    runRoot: path.resolve(runRoot),
    ownerPid: process.pid,
    createdAt: new Date().toISOString(),
  })
  fs.writeFileSync(path.join(runRoot, ownerMarkerName), `${JSON.stringify(marker, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
  const readback = JSON.parse(fs.readFileSync(path.join(runRoot, ownerMarkerName), 'utf8'))
  assertCleanupTargetOwnership({ runRoot, runId, marker: readback })
  return Object.freeze({ runId, tempBase, tempRoot: runRoot, profileRoot, marker: readback })
}

export function updateRuntimeProcessOwnership(isolation, values = {}) {
  const markerPath = path.join(isolation.tempRoot, ownerMarkerName)
  const marker = JSON.parse(fs.readFileSync(markerPath, 'utf8'))
  assertCleanupTargetOwnership({ runRoot: isolation.tempRoot, runId: isolation.runId, marker })
  const nextMarker = {
    ...marker,
    ownerPid: marker.ownerPid || process.pid,
    ...Object.fromEntries(Object.entries(values).filter(([, value]) => Number.isInteger(value) && value > 0)),
  }
  fs.writeFileSync(markerPath, `${JSON.stringify(nextMarker, null, 2)}\n`, 'utf8')
  return nextMarker
}

export function startRuntimeCleanupWatchdog(isolation) {
  if (!isWindows) return null
  const watchdog = spawn(process.execPath, [cleanupWatchdogCommand, isolation.tempRoot, isolation.runId], {
    cwd: frontendRoot,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  })
  watchdog.unref()
  return watchdog
}

export function cleanupRuntimeIsolation(isolation) {
  if (!isolation?.tempRoot) return { passed: true, removed: false }
  const markerPath = path.join(isolation.tempRoot, ownerMarkerName)
  const marker = JSON.parse(fs.readFileSync(markerPath, 'utf8'))
  assertCleanupTargetOwnership({ runRoot: isolation.tempRoot, runId: isolation.runId, marker })
  fs.rmSync(isolation.tempRoot, { recursive: true, force: false })
  if (fs.existsSync(isolation.tempRoot)) throw new Error(`Runtime temp cleanup failed: ${isolation.tempRoot}`)
  return { passed: true, removed: true }
}

export function buildChildEnvironment(isolation, env = process.env) {
  return {
    ...env,
    TEMP: isolation.tempRoot,
    TMP: isolation.tempRoot,
    PCE_PLAYWRIGHT_RUN_ID: isolation.runId,
    PCE_PLAYWRIGHT_TEMP_ROOT: isolation.tempRoot,
    PCE_PLAYWRIGHT_PROFILE_ROOT: isolation.profileRoot,
    PLAYWRIGHT_OUTPUT_DIR: path.join(frontendRoot, 'test-results', 'pce-runtime-acceptance', isolation.runId),
  }
}

export function windowsListeningPids(netstatOutput, host = requiredHost, port = requiredPort) {
  const endpoint = `${host}:${port}`.toLowerCase()
  return String(netstatOutput || '')
    .split(/\r?\n/)
    .map((line) => line.trim().split(/\s+/))
    .filter((parts) => parts.length >= 5 && parts[0].toUpperCase() === 'TCP' && parts[1].toLowerCase() === endpoint && parts[3].toUpperCase() === 'LISTENING')
    .map((parts) => Number(parts[4]))
    .filter((pid) => Number.isInteger(pid) && pid > 0)
}

export async function isPortAvailable(host = requiredHost, port = requiredPort) {
  if (isWindows) {
    const result = spawnSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8', windowsHide: true })
    if (result.error || result.status !== 0) throw result.error || new Error(`netstat failed with exit code ${result.status}`)
    return windowsListeningPids(result.stdout, host, port).length === 0
  }
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.unref()
    probe.once('error', (error) => {
      if (error?.code === 'EADDRINUSE' || error?.code === 'EACCES') resolve(false)
      else reject(error)
    })
    probe.listen({ host, port, exclusive: true }, () => probe.close(() => resolve(true)))
  })
}

function resolveDevServer() {
  const url = new URL(process.env.PCE_DEV_SERVER_URL || `http://${requiredHost}:${requiredPort}`)
  if (url.protocol !== 'http:' || url.hostname !== requiredHost || Number(url.port || 80) !== requiredPort) {
    throw new Error(`VITE_PORT_OWNERSHIP failed: only http://${requiredHost}:${requiredPort} is allowed.`)
  }
  return { url: url.origin, port: requiredPort }
}

export function currentFrontendIdentity() {
  const files = {
    routerRegistryHash: 'src/router/index.js',
    moduleRegistryHash: 'src/meta/master-data/foundationEntryUnificationRegistry.js',
    pageComponentHash: 'src/meta/components/ProductionFoundationMaintenance.vue',
  }
  const hashes = Object.fromEntries(Object.entries(files).map(([key, file]) => [key, createHash('sha256').update(fs.readFileSync(path.join(frontendRoot, file))).digest('hex')]))
  const sourceTreeId = `working-tree:${createHash('sha256').update(Object.values(hashes).join(':')).digest('hex')}`
  return Object.freeze({ contract: 'PCE-FRONTEND-RUNTIME-IDENTITY-V1', sourceTreeId, buildRuntimeId: `pce-foundation-${sourceTreeId.slice(-16)}`, ...hashes })
}

export async function probeViteReadiness(devServerUrl, expectedIdentity = currentFrontendIdentity()) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 1200)
  try {
    const response = await fetch(new URL('/__pce_frontend_identity', devServerUrl), { signal: controller.signal, headers: { Accept: 'application/json' } })
    if (!response.ok) return { ready: false, reason: `identity HTTP ${response.status}` }
    let identity
    try { identity = await response.json() } catch { throw new Error('VITE_RUNTIME_IDENTITY_INVALID: identity endpoint did not return JSON.') }
    const mismatches = Object.keys(expectedIdentity).filter(key => identity?.[key] !== expectedIdentity[key])
    if (mismatches.length) throw new Error(`VITE_RUNTIME_IDENTITY_MISMATCH: ${mismatches.join(', ')}`)
    return { ready: true, identity }
  } catch (error) {
    if (error.message?.startsWith('VITE_RUNTIME_IDENTITY_')) throw error
    return { ready: false, reason: error.message || String(error) }
  } finally {
    clearTimeout(timer)
  }
}

export async function waitForViteReadiness(devServerUrl, { expectedIdentity = currentFrontendIdentity(), server, startupError = () => null, stderr = () => '', probe = probeViteReadiness, timeoutMs = 45_000 } = {}) {
  const startedAt = Date.now()
  let lastReason = 'identity endpoint has not responded'
  const assertChildRunning = () => {
    const error = startupError()
    if (error) throw new Error(`VITE_PROCESS_START_FAILED: ${error.message}\n${stderr()}`)
    if (server && (server.exitCode !== null || server.signalCode !== null)) throw new Error(`VITE_PROCESS_EXITED: exit=${server.exitCode}, signal=${server.signalCode}\n${stderr()}`)
  }
  while (Date.now() - startedAt < timeoutMs) {
    assertChildRunning()
    const result = await probe(devServerUrl, expectedIdentity)
    assertChildRunning()
    if (result.ready) return result
    lastReason = result.reason
    await new Promise((resolve) => setTimeout(resolve, 600))
  }
  throw new Error(`${devServerUrl} identity did not become ready in time: ${lastReason}`)
}

export const PCE_DEFAULT_WARMUP_RESOURCES = Object.freeze(['/@vite/client', '/src/main.js', '/src/App.vue', '/src/router/index.js'])

export async function warmViteResources(devServerUrl, resourcePaths = PCE_DEFAULT_WARMUP_RESOURCES, timeoutMs = 120_000) {
  const startedAt = Date.now()
  const paths = ['/', ...resourcePaths]
  const warmed = []
  for (const resourcePath of paths) {
    const remaining = timeoutMs - (Date.now() - startedAt)
    if (remaining <= 0) throw new Error(`VITE_RESOURCE_WARMUP_TIMEOUT after ${warmed.join(', ') || '<none>'}`)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), remaining)
    try {
      const url = new URL(resourcePath, devServerUrl)
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: resourcePath === '/' ? 'text/html,application/xhtml+xml' : 'text/javascript,*/*;q=0.1' },
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await response.arrayBuffer()
      warmed.push(url.pathname)
    } catch (error) {
      throw new Error(`VITE_RESOURCE_WARMUP_FAILED ${resourcePath}: ${error.message}`)
    } finally {
      clearTimeout(timer)
    }
  }
  return Object.freeze({ passed: true, warmed, durationMs: Date.now() - startedAt })
}

export function isProcessAlive(pid) {
  if (!pid) return false
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    if (error?.code === 'ESRCH') return false
    throw error
  }
}

function isOwnedChildAlive(child) {
  if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return false
  return isProcessAlive(child.pid)
}

async function waitForOwnedExit(child, timeoutMs = 5_000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (!isOwnedChildAlive(child)) return true
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  return !isOwnedChildAlive(child)
}

export async function stopOwnedProcess(child, { timeoutMs = 5_000 } = {}) {
  if (!isOwnedChildAlive(child)) return { passed: true, pid: child?.pid || null, signal: 'already-exited' }
  const pid = child.pid
  child.kill('SIGTERM')
  if (await waitForOwnedExit(child, timeoutMs)) return { passed: true, pid, signal: 'SIGTERM' }
  if (isWindows) {
    spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], {
      cwd: frontendRoot,
      encoding: 'utf8',
      stdio: 'ignore',
    })
  } else {
    child.kill('SIGKILL')
  }
  if (await waitForOwnedExit(child, timeoutMs)) return { passed: true, pid, signal: isWindows ? 'taskkill-fallback' : 'SIGKILL' }
  throw new Error(`Runtime process cleanup failed: owned PID ${pid} is still alive.`)
}

export function createRuntimeCleanupCoordinator({
  isolation,
  getBrowserProcess = () => null,
  getViteProcess = () => null,
  stopProcess = stopOwnedProcess,
  verifyPortReleased = () => isPortAvailable(requiredHost, requiredPort),
  removeIsolation = cleanupRuntimeIsolation,
} = {}) {
  let cleanupPromise
  return Object.freeze({
    run(reason = 'normal') {
      if (cleanupPromise) return cleanupPromise
      cleanupPromise = (async () => {
        const errors = []
        let browserCleanup = { passed: true, pid: null, signal: 'not-started' }
        let viteCleanup = { passed: true, pid: null, signal: 'not-started' }
        let portReleased = false
        let tempCleanup = { passed: false, removed: false }

        try {
          browserCleanup = await stopProcess(getBrowserProcess())
        } catch (error) {
          errors.push(`browser: ${error.message}`)
        }
        try {
          viteCleanup = await stopProcess(getViteProcess())
        } catch (error) {
          errors.push(`vite: ${error.message}`)
        }
        try {
          portReleased = await verifyPortReleased()
          if (!portReleased) errors.push(`port: ${requiredHost}:${requiredPort} is still occupied`)
        } catch (error) {
          errors.push(`port: ${error.message}`)
        }
        try {
          tempCleanup = removeIsolation(isolation)
        } catch (error) {
          errors.push(`temp: ${error.message}`)
        }

        return Object.freeze({
          passed: errors.length === 0,
          reason,
          browserStopped: browserCleanup.passed,
          browserPid: browserCleanup.pid,
          browserSignal: browserCleanup.signal,
          viteStopped: viteCleanup.passed,
          vitePid: viteCleanup.pid,
          viteSignal: viteCleanup.signal,
          portReleased,
          removed: tempCleanup.removed,
          errors,
        })
      })()
      return cleanupPromise
    },
  })
}

export function installSignalCleanupHandlers({ cleanupCoordinator, onSignal } = {}) {
  if (!cleanupCoordinator?.run) throw new Error('Signal cleanup requires a cleanup coordinator.')
  let firstSignal = null
  const handlers = new Map()
  for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
    const handler = async () => {
      if (!firstSignal) firstSignal = { signal, exitCode }
      const cleanup = await cleanupCoordinator.run(`signal:${firstSignal.signal}`)
      process.exitCode = firstSignal.exitCode
      onSignal?.({ ...firstSignal, cleanup })
    }
    handlers.set(signal, handler)
    process.on(signal, handler)
  }
  return Object.freeze({
    received() {
      return firstSignal
    },
    remove() {
      for (const [signal, handler] of handlers) process.removeListener(signal, handler)
    },
  })
}

export function spawnCaptured(command, args, options = {}, onSpawn = () => {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      ...options,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    onSpawn(child)
    const stdout = []
    const stderr = []
    child.stdout?.on('data', (chunk) => stdout.push(chunk))
    child.stderr?.on('data', (chunk) => stderr.push(chunk))
    child.once('error', (error) => resolve({ status: null, signal: null, stdout: Buffer.concat(stdout).toString('utf8'), stderr: Buffer.concat(stderr).toString('utf8'), error }))
    child.once('close', (status, signal) => resolve({ status, signal, stdout: Buffer.concat(stdout).toString('utf8'), stderr: Buffer.concat(stderr).toString('utf8') }))
  })
}

export async function withPceDevServer(callback) {
  const devServer = resolveDevServer()
  const expectedIdentity = currentFrontendIdentity()
  const isolation = createRuntimeIsolation()
  const childEnv = buildChildEnvironment(isolation)
  let server
  let browserProcess
  let callbackResult
  let primaryError
  let startupError
  const serverStderr = []
  let cleanupResult = { passed: false, removed: false, browserStopped: false, viteStopped: false, portReleased: false }
  const cleanupCoordinator = createRuntimeCleanupCoordinator({
    isolation,
    getBrowserProcess: () => browserProcess,
    getViteProcess: () => server,
    verifyPortReleased: () => isPortAvailable(requiredHost, devServer.port),
  })
  startRuntimeCleanupWatchdog(isolation)
  const signalLifecycle = installSignalCleanupHandlers({ cleanupCoordinator })
  try {
    assertPortOwnership(await isPortAvailable(requiredHost, devServer.port))
    const safetyGates = Object.freeze({
      TEMP_OUTSIDE_PROJECT: true,
      PROFILE_OUTSIDE_PROJECT: true,
      VITE_PORT_OWNERSHIP: true,
      RUN_ID_ISOLATION: true,
      CLEANUP_TARGET_OWNERSHIP: true,
    })
    server = spawn(process.execPath, [viteCommand, '--host', requiredHost, '--port', String(devServer.port), '--strictPort'], {
      cwd: frontendRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      detached: true,
      env: childEnv,
    })
    updateRuntimeProcessOwnership(isolation, { vitePid: server.pid })
    server.once('error', error => { startupError = error })
    server.stdout?.on('data', (chunk) => process.stdout.write(chunk))
    server.stderr?.on('data', (chunk) => { serverStderr.push(chunk); process.stderr.write(chunk) })
    const startedAt = new Date().toISOString()
    process.stdout.write(`PCE_PLAYWRIGHT_RUNTIME_START ${JSON.stringify({ ...isolation, marker: undefined, devServerUrl: devServer.url, vitePid: server.pid, startedAt, safetyGates })}\n`)
    const ready = await waitForViteReadiness(devServer.url, { expectedIdentity, server, startupError: () => startupError, stderr: () => Buffer.concat(serverStderr).toString('utf8') })
    process.stdout.write(`PCE_PLAYWRIGHT_IDENTITY_READY ${JSON.stringify(ready.identity)}\n`)
    callbackResult = await callback({
      isolation,
      childEnv,
      devServerUrl: devServer.url,
      vitePid: server.pid,
      safetyGates,
      startedAt,
      registerOwnedBrowser(child) {
        browserProcess = child
        updateRuntimeProcessOwnership(isolation, { browserPid: child?.pid })
      },
    })
  } catch (error) {
    primaryError = error
  } finally {
    try {
      cleanupResult = await cleanupCoordinator.run(signalLifecycle.received() ? `signal:${signalLifecycle.received().signal}` : 'normal')
      if (!cleanupResult.passed && !primaryError) throw new Error(`Runtime cleanup failed: ${cleanupResult.errors.join('; ')}`)
    } catch (error) {
      cleanupResult = { ...cleanupResult, passed: false, error: error.message }
      if (!primaryError) primaryError = error
    }
    signalLifecycle.remove()
    process.stdout.write(`PCE_PLAYWRIGHT_RUNTIME_END ${JSON.stringify({ runId: isolation.runId, vitePid: server?.pid || null, finishedAt: new Date().toISOString(), cleanup: cleanupResult })}\n`)
  }
  if (primaryError) throw primaryError
  const receivedSignal = signalLifecycle.received()
  if (receivedSignal) {
    callbackResult = callbackResult || {}
    callbackResult.status = receivedSignal.exitCode
    callbackResult.signal = receivedSignal.signal
  }
  callbackResult.pceRuntime = { isolation, cleanup: cleanupResult }
  return callbackResult
}

export async function runPlaywrightWithDevServer(args, { warmupResources = PCE_DEFAULT_WARMUP_RESOURCES } = {}) {
  return withPceDevServer(async ({ childEnv, devServerUrl, registerOwnedBrowser }) => {
    const warmup = await warmViteResources(devServerUrl, warmupResources)
    process.stdout.write(`PCE_PLAYWRIGHT_RESOURCE_READY ${JSON.stringify(warmup)}\n`)
    return spawnCaptured(process.execPath, [playwrightCli, ...args], {
      cwd: frontendRoot,
      windowsHide: true,
      env: { ...childEnv, PCE_BASE_URL: devServerUrl },
    }, registerOwnedBrowser)
  })
}
