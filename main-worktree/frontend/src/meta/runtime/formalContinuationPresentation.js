export function summarizeFormalValidation(operationState, lines = []) {
  if (operationState === 'running') return { state: 'updating', label: '四行完整校验结果正在更新', resultPositionTotal: 0 }
  if (operationState === 'failed') return { state: 'read_failed', label: '只读响应失败，结果未知', resultPositionTotal: 0 }
  const statuses = lines.map(row => row.fullValidation?.status || 'not_run')
  const resultPositionTotal = lines.reduce((sum, row) => sum + Number(row.fullValidation?.resultPositionCount || 0), 0)
  if (statuses.length && statuses.every(status => status === 'passed')) {
    return { state: 'passed', label: `${statuses.length}/${statuses.length} 行完整校验通过 · 零业务写入`, resultPositionTotal }
  }
  const passed = statuses.filter(status => status === 'passed').length
  const blocked = statuses.filter(status => status === 'blocked' || status === 'not_ready' || status === 'not_run').length
  const failed = statuses.filter(status => status === 'read_failed').length
  return {
    state: failed ? 'read_failed' : blocked ? 'blocked' : 'not_run',
    label: `${passed}/${statuses.length || 0} 行通过；${blocked} 行有阻断；${failed} 行读取失败`,
    resultPositionTotal,
  }
}

export function engineeringInstanceScopeLabel({ sourceScope, selectedInstanceNo, instanceCount, lineCount, factsLoaded }) {
  if (!sourceScope) return selectedInstanceNo || '未建立'
  if (!factsLoaded) return '整单范围 · 实例事实待读取'
  if (!instanceCount) return '整单范围 · 0个实例'
  return `整单范围 · ${instanceCount}/${lineCount}个订单行实例已建立；请选择订单行查看具体实例`
}


