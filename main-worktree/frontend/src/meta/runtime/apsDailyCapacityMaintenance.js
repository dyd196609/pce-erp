/** APS maintenance accepts declared daily facts; it never converts historical hours. */
export function dailyCapacityMaintenancePayload(payload, sourceRow = null) {
  if (sourceRow && (sourceRow.time_basis !== 'day' || Number(sourceRow.time_basis_quantity) !== 1)) {
    throw new Error('已有产能不是数量/天事实，不能直接改成日产能；请根据真实日产能资料新增记录。')
  }
  const result = { ...payload, resource_scope: 'composite', time_basis: 'day', time_basis_quantity: '1', time_unit: 'DAY' }
  for (const key of ['standard_hours', 'setup_hours', 'transfer_hours', 'capacity_per_hour']) delete result[key]
  for (const key of ['quantity', 'preparation_days', 'transfer_days']) {
    if (result[key] === '' || result[key] === undefined) result[key] = null
    if (result[key] !== null) {
      const text = String(result[key])
      if (!/^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) {
        throw new Error('日产能、准备时间和转运时间须填写十进制数字，不支持科学计数法或分隔符。')
      }
      if (text.startsWith('-') && /[1-9]/.test(text)) throw new Error('日产能、准备时间和转运时间不能为负数。')
    }
  }
  return result
}
