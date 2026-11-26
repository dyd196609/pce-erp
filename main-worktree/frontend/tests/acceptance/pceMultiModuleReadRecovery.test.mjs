import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const read = path => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('product design distinguishes loading, failure, and successful data states', () => {
  const source = read('src/meta/pages/PdeProductDesignPage.vue')
  assert.match(source, /refreshStatus === 'refreshing' \|\| refreshStatus === 'idle'/)
  assert.match(source, /读取失败，当前数据数量未知/)
  assert.match(source, /v-if="refreshStatus === 'success'" class="card operation-card"/)
  assert.match(source, /refreshStatus === 'success' \? `\$\{strictFacts\.recordCount/)
  assert.match(source, /refreshStatus\.value = 'refreshing'; loadError\.value = ''/)
  assert.match(source, /refreshStatus\.value = 'success'/)
})

test('engineering calculation never renders failure and real empty state together', () => {
  const source = read('src/meta/pages/PdeOrderEngineeringCalculationPage.vue')
  assert.match(source, /v-else-if="!loading && !loadError && !orders\.length"/)
  assert.match(source, /data-state="fact-read-succeeded"/)
  assert.doesNotMatch(source, /这不是读取失败/)
})

test('foundation maintenance blocks lists and writes until facts are loaded', () => {
  const source = read('src/meta/components/ProductionFoundationMaintenance.vue')
  assert.match(source, /读取失败，当前数据数量未知/)
  assert.match(source, /v-else-if="loadStatus === 'loaded' && !providerFailed"/)
  assert.match(source, /正在读取企业基础资料服务端事实/)
})
