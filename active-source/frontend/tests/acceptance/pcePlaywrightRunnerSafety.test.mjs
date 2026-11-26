import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  assertCleanupTargetOwnership,
  assertPortOwnership,
  assertRunRootAvailable,
  buildChildEnvironment,
  cleanupRuntimeIsolation,
  createRuntimeCleanupCoordinator,
  createRuntimeIsolation,
  currentFrontendIdentity,
  frontendRoot,
  projectRoot,
  probeViteReadiness,
  selectSafeTempBase,
  stopOwnedProcess,
  validateIsolationPaths,
  validateRunId,
  warmViteResources,
  waitForViteReadiness,
  windowsListeningPids,
} from '../../scripts/pcePlaywrightRunner.mjs'

const validRunId = 'run-offline-validation-001'
const externalRoot = path.resolve(process.env.PCE_PLAYWRIGHT_TEST_TEMP_BASE || os.tmpdir(), 'pce-runner-safety-tests')
const currentDir = path.dirname(fileURLToPath(import.meta.url))

function waitForLine(child, prefix, timeoutMs = 15_000) {
  return new Promise((resolve, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for ${prefix}. Output: ${output}`)), timeoutMs)
    child.stdout.on('data', (chunk) => {
      output += chunk.toString('utf8')
      const line = output.split(/\r?\n/).find((item) => item.startsWith(prefix))
      if (!line) return
      clearTimeout(timer)
      resolve(JSON.parse(line.slice(prefix.length).trim()))
    })
  })
}

async function runSignalHarness(signal, expectedExitCode) {
  const child = spawn(process.execPath, [path.join(currentDir, 'pcePlaywrightSignalHarness.mjs'), signal], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  const ready = await waitForLine(child, 'HARNESS_READY ')
  const resultPromise = waitForLine(child, 'HARNESS_RESULT ')
  const result = await resultPromise
  const exit = await new Promise((resolve) => child.once('close', (code, exitSignal) => resolve({ code, signal: exitSignal })))
  assert.equal(exit.code, expectedExitCode)
  assert.equal(exit.signal, null)
  assert.equal(result.signal, signal)
  assert.equal(result.exitCode, expectedExitCode)
  assert.equal(result.cleanup.passed, true)
  assert.equal(result.cleanup.browserPid, ready.browserPid)
  assert.equal(result.cleanup.vitePid, ready.vitePid)
  assert.equal(result.cleanup.browserStopped, true)
  assert.equal(result.cleanup.viteStopped, true)
  assert.equal(result.cleanup.portReleased, true)
  assert.equal(result.cleanup.removed, true)
  assert.equal(fs.existsSync(ready.tempRoot), false)
}

async function waitUntil(predicate, timeoutMs = 15_000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (predicate()) return true
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  return predicate()
}

test('normal external TEMP passes path isolation', () => {
  assert.equal(validateIsolationPaths({ tempRoot: externalRoot, profileRoot: path.join(externalRoot, 'profile') }), true)
})

test('TEMP inside frontend is rejected and a safe fallback can be selected', () => {
  assert.throws(() => selectSafeTempBase({ env: { PCE_PLAYWRIGHT_TEMP_BASE: path.join(frontendRoot, '.tmp') } }), /TEMP_OUTSIDE_PROJECT/)
  assert.equal(selectSafeTempBase({ env: { TEMP: frontendRoot, TMP: externalRoot } }), externalRoot)
})

test('profile inside project root is rejected', () => {
  assert.throws(() => validateIsolationPaths({ tempRoot: externalRoot, profileRoot: path.join(projectRoot, 'profile') }), /PROFILE_OUTSIDE_PROJECT/)
})

test('missing run-id is rejected', () => {
  assert.throws(() => validateRunId(''), /RUN_ID_ISOLATION/)
})

test('unknown existing run directory is rejected', () => {
  assert.throws(() => assertRunRootAvailable(path.join(externalRoot, `pce-pw-${validRunId}`), () => true), /already exists/)
})

test('unknown port listener is rejected', () => {
  assert.throws(() => assertPortOwnership(false), /PORT OWNERSHIP UNKNOWN/)
})

test('Windows port audit distinguishes LISTENING from TIME_WAIT', () => {
  const output = [
    'TCP    127.0.0.1:5173    0.0.0.0:0    LISTENING    32100',
    'TCP    127.0.0.1:5173    127.0.0.1:62000    TIME_WAIT    0',
  ].join('\r\n')
  assert.deepEqual(windowsListeningPids(output), [32100])
  assert.deepEqual(windowsListeningPids(output.replace('LISTENING', 'TIME_WAIT')), [])
})

test('child environment round-trips without mutating parent TEMP or TMP', () => {
  const parent = { TEMP: 'parent-temp', TMP: 'parent-tmp', KEEP: 'yes' }
  const isolation = { runId: validRunId, tempRoot: externalRoot, profileRoot: externalRoot }
  const roundTrip = JSON.parse(JSON.stringify(buildChildEnvironment(isolation, parent)))
  assert.equal(parent.TEMP, 'parent-temp')
  assert.equal(parent.TMP, 'parent-tmp')
  assert.equal(roundTrip.TEMP, externalRoot)
  assert.equal(roundTrip.TMP, externalRoot)
  assert.equal(roundTrip.PCE_PLAYWRIGHT_RUN_ID, validRunId)
  assert.match(roundTrip.PLAYWRIGHT_OUTPUT_DIR, new RegExp(`${validRunId}$`))
})

test('resource warmup waits for document and named Vite modules', async () => {
  const requests = []
  const server = (await import('node:http')).createServer((request, response) => {
    requests.push({ url: request.url, accept: request.headers.accept })
    response.writeHead(200, { 'content-type': request.url === '/' ? 'text/html' : 'text/javascript' })
    response.end(request.url === '/' ? '<script type="module" src="/src/main.js"></script>' : 'export default true')
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  try {
    const address = server.address()
    const result = await warmViteResources(`http://127.0.0.1:${address.port}`, ['/src/main.js', '/src/route.js'], 5_000)
    assert.deepEqual(result.warmed, ['/', '/src/main.js', '/src/route.js'])
    assert.match(requests[0].accept, /text\/html/)
    assert.match(requests[1].accept, /text\/javascript/)
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
  }
})

test('default warmup reads the application entry before starting UI timeouts', async () => {
  const requests = []
  const server = (await import('node:http')).createServer((request,response) => {
    requests.push(request.url);response.writeHead(200);response.end('ready')
  })
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
  try {
    const result=await warmViteResources(`http://127.0.0.1:${server.address().port}`)
    assert.deepEqual(result.warmed,['/','/@vite/client','/src/main.js','/src/App.vue','/src/router/index.js'])
    assert.deepEqual(requests,result.warmed)
  } finally {await new Promise(resolve=>server.close(resolve))}
})

test('identity readiness avoids cold HTML and warmup completes one uninterrupted document read', async () => {
  const identity = currentFrontendIdentity()
  const requests = []
  let abortedDocumentReads = 0
  const server = (await import('node:http')).createServer((request, response) => {
    requests.push(request.url)
    if (request.url === '/__pce_frontend_identity') {
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify(identity))
      return
    }
    if (request.url === '/') {
      request.on('aborted', () => { abortedDocumentReads += 1 })
      setTimeout(() => { response.writeHead(200, { 'content-type': 'text/html' }); response.end('<script type="module" src="/src/main.js"></script>') }, 1500)
      return
    }
    response.writeHead(200, { 'content-type': 'text/javascript' })
    response.end('export default true')
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  try {
    const url = `http://127.0.0.1:${server.address().port}`
    assert.equal((await waitForViteReadiness(url, { expectedIdentity: identity })).ready, true)
    assert.deepEqual(requests, ['/__pce_frontend_identity'])
    const warmup = await warmViteResources(url, ['/src/main.js'], 5000)
    assert.deepEqual(warmup.warmed, ['/', '/src/main.js'])
    assert.deepEqual(requests, ['/__pce_frontend_identity', '/', '/src/main.js'])
    assert.equal(abortedDocumentReads, 0)
  } finally { await new Promise(resolve => server.close(resolve)) }
})

test('readiness rejects arbitrary 200 responses, wrong contract and stale source hashes', async () => {
  const identity = currentFrontendIdentity()
  let payload = '<html>some other server</html>'
  let status = 200
  const server = (await import('node:http')).createServer((_request, response) => {
    response.writeHead(status, { 'content-type': 'application/json' })
    response.end(typeof payload === 'string' ? payload : JSON.stringify(payload))
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  try {
    const url = `http://127.0.0.1:${server.address().port}`
    await assert.rejects(probeViteReadiness(url, identity), /VITE_RUNTIME_IDENTITY_INVALID/)
    payload = { ...identity, contract: 'OTHER' }
    await assert.rejects(probeViteReadiness(url, identity), /VITE_RUNTIME_IDENTITY_MISMATCH: contract/)
    payload = { ...identity, routerRegistryHash: 'stale' }
    await assert.rejects(probeViteReadiness(url, identity), /routerRegistryHash/)
    payload = identity
    status = 503
    assert.deepEqual(await probeViteReadiness(url, identity), { ready: false, reason: 'identity HTTP 503' })
  } finally { await new Promise(resolve => server.close(resolve)) }
})

test('a real early Vite child exit preserves its exit code and original stderr', async () => {
  const child = spawn(process.execPath, ['-e', "process.stderr.write('original startup failure\\n'); process.exit(23)"], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true })
  let stderr = ''
  child.stderr.on('data', chunk => { stderr += chunk.toString('utf8') })
  await new Promise(resolve => child.once('close', resolve))
  await assert.rejects(waitForViteReadiness('http://127.0.0.1:5173', { server: child, stderr: () => stderr, probe: () => assert.fail('an exited owned child must not be polled') }), /VITE_PROCESS_EXITED: exit=23, signal=null\noriginal startup failure/)
})

test('cleanup requires the exact run-id marker', () => {
  const runRoot = path.join(externalRoot, `pce-pw-${validRunId}`)
  assert.equal(assertCleanupTargetOwnership({ runRoot, runId: validRunId, marker: { runId: validRunId, runRoot } }), true)
  assert.throws(() => assertCleanupTargetOwnership({ runRoot, runId: validRunId, marker: { runId: 'run-unknown-owner-001', runRoot } }), /CLEANUP_TARGET_OWNERSHIP/)
})

test('exception cleanup simulation removes only the marker-owned run root', () => {
  fs.mkdirSync(externalRoot, { recursive: true })
  const isolation = createRuntimeIsolation({
    env: { PCE_PLAYWRIGHT_TEMP_BASE: externalRoot },
    runId: `run-exception-cleanup-${process.pid}-${Date.now()}`,
  })
  try {
    throw new Error('simulated child failure')
  } catch (error) {
    assert.match(error.message, /simulated child failure/)
  } finally {
    assert.deepEqual(cleanupRuntimeIsolation(isolation), { passed: true, removed: true })
  }
  assert.equal(fs.existsSync(isolation.tempRoot), false)
})

test('owned child-process cleanup waits for verified exit', async () => {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {
    stdio: 'ignore',
    windowsHide: true,
  })
  const result = await stopOwnedProcess(child)
  assert.equal(result.passed, true)
  assert.equal(result.pid, child.pid)
})

test('cleanup coordinator is idempotent and stops browser before Vite', async () => {
  const calls = []
  const isolation = { tempRoot: 'synthetic', runId: validRunId }
  const coordinator = createRuntimeCleanupCoordinator({
    isolation,
    getBrowserProcess: () => ({ pid: 101 }),
    getViteProcess: () => ({ pid: 202 }),
    stopProcess: async (child) => {
      calls.push(`stop:${child.pid}`)
      return { passed: true, pid: child.pid, signal: 'SIGTERM' }
    },
    verifyPortReleased: async () => {
      calls.push('port-readback')
      return true
    },
    removeIsolation: () => {
      calls.push('temp-readback')
      return { passed: true, removed: true }
    },
  })
  const [first, second] = await Promise.all([coordinator.run('normal'), coordinator.run('double')])
  assert.strictEqual(first, second)
  assert.deepEqual(calls, ['stop:101', 'stop:202', 'port-readback', 'temp-readback'])
})

test('cleanup coordinator continues readback after an earlier cleanup failure', async () => {
  const calls = []
  const result = await createRuntimeCleanupCoordinator({
    isolation: { tempRoot: 'synthetic', runId: validRunId },
    getBrowserProcess: () => ({ pid: 303 }),
    stopProcess: async () => {
      calls.push('browser-failed')
      throw new Error('simulated stop failure')
    },
    verifyPortReleased: async () => {
      calls.push('port-readback')
      return true
    },
    removeIsolation: () => {
      calls.push('temp-readback')
      return { passed: true, removed: true }
    },
  }).run('failure-test')
  assert.equal(result.passed, false)
  assert.deepEqual(calls, ['browser-failed', 'browser-failed', 'port-readback', 'temp-readback'])
  assert.match(result.errors.join(' '), /simulated stop failure/)
})

test('real spawned runner cleanup handles SIGINT', async () => {
  await runSignalHarness('SIGINT', 130)
})

test('real spawned runner cleanup handles SIGTERM', async () => {
  await runSignalHarness('SIGTERM', 143)
})

test('detached watchdog cleans real owned children after abrupt owner exit', async () => {
  const child = spawn(process.execPath, [path.join(currentDir, 'pcePlaywrightSignalHarness.mjs'), 'WATCHDOG'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  const ready = await waitForLine(child, 'HARNESS_READY ')
  const exit = await new Promise((resolve) => child.once('close', (code) => resolve(code)))
  assert.equal(exit, 73)
  assert.equal(await waitUntil(() => !fs.existsSync(ready.tempRoot)), true)
  assert.equal(fs.existsSync(ready.tempRoot), false)
})
