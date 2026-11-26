import assert from 'node:assert/strict'
import test from 'node:test'
import { dailyCapacityMaintenancePayload } from '../../src/meta/runtime/apsDailyCapacityMaintenance.js'

test('真实日产能数量和天数保持精度，提交相同产品类型、工序、工作中心及单位', () => {
  const facts = {
    product_type_id: 4, operation_id: 9, work_center_id: 3, uom_id: 2,
    quantity: '999999999999.999999', preparation_days: '0.1250', transfer_days: '2.5000',
    effective_from: '2026-10-13', reason: '业务人员确认日产能',
  }
  const result = dailyCapacityMaintenancePayload(facts)
  for (const field of Object.keys(facts)) assert.equal(result[field], facts[field])
  assert.equal(result.time_basis, 'day')
  assert.equal(result.time_basis_quantity, '1')
  assert.equal(result.time_unit, 'DAY')
})

test('缺失准备或转运时间不冒充零天，真实零天仍保留', () => {
  const unknown = dailyCapacityMaintenancePayload({ quantity: '', preparation_days: '', transfer_days: undefined })
  assert.equal(unknown.quantity, null)
  assert.equal(unknown.preparation_days, null)
  assert.equal(unknown.transfer_days, null)
  const confirmed = dailyCapacityMaintenancePayload({ quantity: '99', preparation_days: 0, transfer_days: '0.0000' })
  assert.equal(confirmed.preparation_days, 0)
  assert.equal(confirmed.transfer_days, '0.0000')
})

test('历史小时或多天产能不能仅通过变更时间标签转换成日产能', () => {
  const entered = { quantity: '99', preparation_days: '1', transfer_days: '1' }
  for (const historical of [
    { time_basis: 'hour', time_basis_quantity: '1' },
    { time_basis: 'day', time_basis_quantity: '7' },
    { time_basis: 'not_maintained', time_basis_quantity: null },
  ]) assert.throws(() => dailyCapacityMaintenancePayload(entered, historical), /不能直接改成日产能/)
  assert.equal(dailyCapacityMaintenancePayload(entered, { time_basis: 'day', time_basis_quantity: '1.0000' }).quantity, '99')
})

test('共用表单中的遗留小时字段不会进入日产能保存请求，也不会被重算为天数', () => {
  const raw = { quantity: '99', standard_hours: '8', setup_hours: '24', transfer_hours: '48', capacity_per_hour: '10' }
  const result = dailyCapacityMaintenancePayload(raw)
  assert.equal(result.quantity, '99')
  assert.equal(result.preparation_days, null)
  assert.equal(result.transfer_days, null)
  for (const key of ['standard_hours', 'setup_hours', 'transfer_hours', 'capacity_per_hour']) assert.ok(!(key in result))
  assert.equal(raw.setup_hours, '24')
})

test('天数禁止负值或非数值输入，十进制的小数仍原样提交', () => {
  for (const value of ['-0.25', 'NaN', 'Infinity', '1,000', '1e6']) {
    assert.throws(() => dailyCapacityMaintenancePayload({ quantity: '99', preparation_days: value }))
  }
  const result = dailyCapacityMaintenancePayload({ quantity: '99.000001', preparation_days: '.25', transfer_days: '0.0001' })
  assert.equal(result.quantity, '99.000001')
  assert.equal(result.preparation_days, '.25')
  assert.equal(result.transfer_days, '0.0001')
})
