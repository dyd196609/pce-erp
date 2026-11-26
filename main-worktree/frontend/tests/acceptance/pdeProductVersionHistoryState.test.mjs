import assert from 'node:assert/strict'
import { createLatestRequestGate } from '../../src/meta/pages/productVersionHistoryState.js'

const gate = createLatestRequestGate()
const first = gate.begin()
const second = gate.begin()

assert.equal(gate.isCurrent(first), false, '旧的版本详情请求不得覆盖后发选择')
assert.equal(gate.isCurrent(second), true, '最终选择对应的请求必须保持有效')

const third = gate.begin()
assert.equal(gate.isCurrent(second), false, '切换订单后上一订单请求必须立即失效')
assert.equal(gate.isCurrent(third), true, '新订单请求必须成为唯一可应用请求')

console.log('PDE product-version latest-request gate: PASS')
