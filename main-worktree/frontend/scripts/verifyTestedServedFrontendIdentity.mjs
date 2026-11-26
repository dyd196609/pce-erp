import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sha = relative => createHash('sha256').update(readFileSync(path.join(root, relative))).digest('hex')
const expected = {
  routerRegistryHash: sha('src/router/index.js'),
  moduleRegistryHash: sha('src/meta/master-data/foundationEntryUnificationRegistry.js'),
  pageComponentHash: sha('src/meta/components/ProductionFoundationMaintenance.vue'),
}
const endpoint = process.env.PCE_FRONTEND_IDENTITY_ENDPOINT || 'http://localhost:5173/__pce_frontend_identity'
const response = await fetch(endpoint, { headers: { 'cache-control': 'no-cache' } })
assert.equal(response.ok, true, `frontend identity endpoint failed: ${response.status}`)
const served = await response.json()
for (const [key, value] of Object.entries(expected)) assert.equal(served[key], value, `${key} differs between tested source and served runtime`)

console.log(JSON.stringify({
  result: 'passed',
  contract: served.contract,
  endpoint,
  testedEqualsServed: true,
  expected,
  served,
}, null, 2))
