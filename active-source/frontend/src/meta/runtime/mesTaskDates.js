// Project only the authoritative task date contract; never infer dates from status.
export function taskDateDisplay(facts, taskId, { showReview = false } = {}) {
  const value = item => typeof item === 'string' && item.trim() ? item : null
  const valid = facts?.contractVersion === 'PCE-MES-TASK-DATE-FACTS-V1'
    && taskId != null && String(facts.taskId) === String(taskId)
  if (!valid) return { valid: false, rows: [], timezone: null }
  const planValid = facts.planSource === 'task.source_snapshot.operation'
  const rows = [
    { key: 'plannedStart', label: '计划开始', value: planValid && value(facts.plannedStartAt) || '当前服务未提供计划开始时间' },
    { key: 'plannedCompletion', label: '计划完成', value: planValid && value(facts.plannedCompletionAt) || '当前服务未提供计划完成时间' },
    { key: 'actualStart', label: '实际开工', value: value(facts.actualStartAtLabel) || '尚无实际开工时间事实' },
    { key: 'startRecorded', label: '开工记录时间', value: value(facts.startRecordedAtLabel) || '尚无开工记录时间事实' },
  ]
  if (showReview) rows.push({ key: 'reviewEffective', label: '独审生效时间', value: value(facts.completionReviewEffectiveAtLabel) || '尚无独审生效时间事实' })
  rows.push({ key: 'physicalCompletion', label: '现场实际完成', value: facts.physicalCompletionTimeSupported === false
    ? '尚无现场实际完成时间（当前服务未采集）'
    : facts.physicalCompletionTimeSupported === true && value(facts.physicalCompletionAt) || '当前服务未提供现场实际完成时间' })
  return { valid: true, rows, timezone: value(facts.businessTimezone) }
}
