import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  buildMasterDataStatisticsRuntime,
  COUNT_SOURCE_CONTRACT,
} from '../src/meta/runtime/masterDataStatisticsRuntime.js'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..', '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const payload = {
  factLoadFacts: { factLoadStatus: 'success' },
  runtimeCode: 'MasterDataStatisticsRuntime',
  runtimeVersion: 'V1.14.2.8.4.27.2.29',
  materialCount: 80,
  supplierCount: 100,
  supplierMaterialRelationCount: 12,
  supplierPriceCount: 9,
  countSources: { ...COUNT_SOURCE_CONTRACT },
  businessProgressWriteCount: 0,
}
const runtime = buildMasterDataStatisticsRuntime(payload)
assert.deepEqual(
  [runtime.materialCount, runtime.supplierCount, runtime.supplierMaterialRelationCount, runtime.supplierPriceCount],
  [80, 100, 12, 9],
)
assert.equal(runtime.businessProgressWriteCount, 0)

const page = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const backend = read('backend/masterdata/master_data_statistics_runtime.py')
const governance = read('docs/governance/页面汇总统计数据来源规范.md')
assert.match(page, /data-statistics-source="MasterDataStatisticsRuntime"/)
for (const field of Object.keys(COUNT_SOURCE_CONTRACT)) {
  assert.match(page, new RegExp(`field: '${field}'`))
  assert.match(backend, new RegExp(`${field}`))
}
const summaryBlock = page.match(/const summaryCards[\s\S]*?const sampleDataCards/)?.[0] || ''
assert.doesNotMatch(summaryBlock, /state\.value/)
assert.doesNotMatch(summaryBlock, /\.length/)
assert.match(governance, /MASTER-DATA-STATISTICS-SOURCE-001/)
assert.match(governance, /MASTER-DATA-COUNT-CONSISTENCY-001/)

console.log('MASTER-DATA-STATISTICS-SOURCE-001 PASS')
console.log('MASTER-DATA-COUNT-CONSISTENCY-001 PASS')
console.log('Foundation Page Runtime PASS')
console.log('Database Changed NO')
console.log('Business Write Count PASS (0)')
