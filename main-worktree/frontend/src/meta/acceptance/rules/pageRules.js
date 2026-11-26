export function outcome(passed, evidence, reason = '') {
  if (passed === null || passed === undefined) {
    return { result: 'UNKNOWN', evidence, reason: reason || '缺少可判定证据' }
  }
  return { result: passed ? 'PASS' : 'FAIL', evidence, reason: passed ? '' : reason }
}

function rule(id, name, evaluate) {
  return Object.freeze({ id, name, family: 'PAGE', evaluate })
}

export const pageRules = Object.freeze([
  rule('PAGE-001', '页面可打开', evidence => outcome(
    evidence.page?.opened,
    `url=${evidence.page?.url || ''}`,
    '页面未成功打开',
  )),
  rule('PAGE-002', '页面标题正确', evidence => outcome(
    evidence.page?.title === evidence.page?.expectedTitle,
    `expected=${evidence.page?.expectedTitle}; actual=${evidence.page?.title}`,
    '页面业务标题不一致',
  )),
  rule('PAGE-003', '业务版本可见', evidence => outcome(
    Boolean(evidence.page?.version),
    `version=${evidence.page?.version || ''}`,
    '页面未显示业务版本',
  )),
  rule('PAGE-004', '模块身份正确', evidence => outcome(
    evidence.page?.moduleCode === evidence.page?.expectedModuleCode,
    `expected=${evidence.page?.expectedModuleCode}; actual=${evidence.page?.moduleCode}`,
    '页面模块身份不一致',
  )),
  rule('PAGE-005', '无控制台错误', evidence => {
    const errors = evidence.page?.consoleErrors
    if (!Array.isArray(errors)) return outcome(null, '', '未采集控制台证据')
    if (errors.length === 0) return outcome(true, 'errors=[]')
    const failures = evidence.page?.resourceFailures || []
    const anonymousProbeOnly = errors.every(message => (
      message.includes('Failed to load resource')
      && message.includes('401')
    )) && failures.length > 0 && failures.every(item => (
      item.status === 401 && !item.url.includes('/api/finance/bank-send-')
    ))
    return outcome(
      anonymousProbeOnly ? true : false,
      `errors=${JSON.stringify(errors)}; resourceFailures=${JSON.stringify(failures)}`,
      '页面产生控制台错误',
    )
  }),
])
