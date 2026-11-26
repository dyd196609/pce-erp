// Anonymous GET-only runtime evidence; no browser/session/credential access.
import { readFileSync, writeFileSync, readdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { DatabaseSync } from 'node:sqlite'
const root = 'D:/Dev-PCE/Source'
const out = `${root}/frontend/test-results/pce-order-delivery-planning-do4-r1-runtime-20260913`
const startup = JSON.parse(readFileSync(`${out}/STARTUP_LOADED.json`, 'utf8'))
const run = promisify(execFile)
const tcp = new Set()
let sampling = true
const sampler = (async () => {
  while (sampling) {
    const { stdout } = await run('netstat.exe', ['-ano', '-p', 'tcp'], { windowsHide: true })
    for (const line of stdout.split(/\r?\n/)) if (/:8075\s/.test(line)) tcp.add(line.trim())
    await new Promise(resolve => setTimeout(resolve, 50))
  }
})()
const results = []
for (const route of startup.routes) {
  for (const port of [8075, 5176]) {
    const response = await fetch(`http://127.0.0.1:${port}${route.path}`, {
      method: 'GET', headers: { 'X-Request-Id': 'DO4-R1-READONLY-ROUTE-CHECK' }, signal: AbortSignal.timeout(10000),
    })
    const body = await response.text()
    let denial = null
    if (response.headers.get('content-type')?.includes('application/json')) {
      const json = JSON.parse(body)
      denial = json.detail || json.error?.code || null
    }
    results.push({ path: route.path, port, method: 'GET', status: response.status,
      allow: response.headers.get('allow'), denial, handler: route.handler,
      implementedMethods: route.implementedMethods, bodySha256: createHash('sha256').update(body).digest('hex') })
    await new Promise(resolve => setTimeout(resolve, 60))
  }
}
sampling = false
await sampler
const frontend = []
const files = [
  ['src/api/sales.js', ['sourceAction', 'createSourceDraft', 'source-intake/whole-house/']],
  ['src/meta/pages/WholeHouseOrderPreview.vue', ['保存映射草稿', '确认来源使用资格', '确认映射及商业数量']],
  ['src/meta/pages/SalesOrderPage.vue', ['/planning/requirements', 'WholeHouseOrderPreview']],
  ['src/router/index.js', ['/system-login', 'planning/requirements', 'sales/orders']],
]
for (const [file, markers] of files) {
  const response = await fetch(`http://127.0.0.1:5176/${file}`, { signal: AbortSignal.timeout(10000) })
  const body = await response.text()
  frontend.push({ file, status: response.status, markers: Object.fromEntries(markers.map(marker => [marker, body.includes(marker)])),
    diskSha256: createHash('sha256').update(readFileSync(`${root}/frontend/${file}`)).digest('hex'),
    servedCompiledSha256: createHash('sha256').update(body).digest('hex') })
}
const identityResponse = await fetch('http://127.0.0.1:5176/__pce_frontend_identity')
const identity = identityResponse.headers.get('content-type')?.includes('application/json') ? await identityResponse.json() : null
const db = new DatabaseSync(startup.environment.PCE_DATABASE_PATH, { readOnly: true })
const applied = new Set(db.prepare("SELECT app || '.' || name AS migration FROM django_migrations WHERE app IN ('planning','procurement')").all().map(r => r.migration))
const unapplied = ['planning', 'procurement'].flatMap(app => readdirSync(`${root}/backend/${app}/migrations`)
  .filter(name => /^\d.*\.py$/.test(name)).map(name => `${app}.${name.slice(0, -3)}`).filter(name => !applied.has(name)))
db.close()
const report = { recordedAt: new Date().toISOString(), backendPid: startup.pid, frontendPid: 75460,
  results, tcpEvidence: [...tcp], frontend, frontendIdentity: identity, unappliedMigrations: unapplied,
  businessRequestsSubmitted: 0, loginRequestsSubmitted: 0,
  interpretation: '401 = anonymous authentication boundary, not specific-handler proof alone. Same live PID startup handler/source evidence supplements it. Login GET 405 is expected; POST was not submitted. No source/save/confirm/create POST.' }
writeFileSync(`${out}/RUNTIME_PROBES.json`, JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify(report, null, 2))
