import { spawn } from 'node:child_process'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.2'
const endpoint = 'http://127.0.0.1:8000/api/finance/payment-order-prepares/'
const frontend = path.resolve(import.meta.dirname, '..')
const serverScript = path.join(frontend, 'scripts', 'servePceWebAcceptanceReadModel.mjs')
const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))

async function inspect() {
  try {
    const response = await fetch(endpoint, { signal: AbortSignal.timeout(2_000) })
    const payload = await response.json()
    const data = payload?.data || {}
    const results = data?.results || payload?.data?.data?.results || []
    return { reachable: true, accepted: response.ok && results.length >= 8, status: response.status, count: results.length }
  } catch {
    return { reachable: false, accepted: false, status: 0, count: 0 }
  }
}

const initial = await inspect()
if (initial.accepted) {
  console.log(JSON.stringify({ result: 'passed', version: VERSION, service: 'existing-server-read-model', ...initial }))
  process.exit(0)
}
if (initial.reachable) {
  throw new Error(`port 8000 is occupied by a non-acceptance service (HTTP ${initial.status}, rows ${initial.count})`)
}

const child = spawn(process.execPath, [serverScript], {
  cwd: frontend,
  detached: true,
  shell: false,
  stdio: 'ignore',
  windowsHide: true,
})
child.unref()
for (let attempt = 1; attempt <= 30; attempt += 1) {
  await wait(250)
  const current = await inspect()
  if (current.accepted) {
    console.log(JSON.stringify({ result: 'passed', version: VERSION, service: 'immutable-server-checkpoint-read-model', pid: child.pid, ...current }))
    process.exit(0)
  }
}
throw new Error('read-only acceptance service did not become ready')
