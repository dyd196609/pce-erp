export const BUSINESS_ACCEPTANCE_COPY_VERSION = 'V1.14.2.7.2.1'

export const businessAcceptanceSectionTitles = {
  manualNavigation: 'V1.14.2.7.2.1 人工验收导航',
  targetEvidenceSummary: '目标证据状态摘要',
  nextStepRelease: '下一步放行与阻断',
  firstFailure: '第一异常点',
  targetEvidenceTrace: '目标证据来源链',
  missingEvidence: '缺失的关联证据',
  conflictEvidence: '目标关联冲突清单',
  readFailure: '目标证据读取失败明细',
  copyDiagnostic: '复制诊断数据',
  paymentExecutionPrepareList: '付款执行准备列表',
}

export const businessAcceptanceFieldLabels = {
  targetObjectNo: '目标对象编号',
  targetEvidenceStatus: '目标证据状态',
  executionStatus: '当前执行状态',
  resultSource: '结果来源',
  nextStepAllowed: '是否允许进入下一步',
  nextStepBlockReason: '下一步阻断原因',
  firstFailure: '第一异常点',
  failureType: '异常类型',
  failureReason: '异常原因',
  responsibility: '建议检查方向',
  blocking: '是否阻断下一步',
}

export const businessAcceptanceEmptyTexts = {
  noMissingEvidence: '当前没有缺失的关联证据',
  noConflictEvidence: '当前没有目标关联冲突',
  noReadFailure: '当前没有目标证据读取失败',
  noTraceItems: '当前没有可显示的目标证据来源链',
  noFailure: '未发现异常',
  noTargetObject: '未发现目标对象',
}

export const businessAcceptanceScrollCopy = {
  left: '向左',
  right: '向右',
  instruction: '拖动滑块查看右侧内容',
  noScrollNeeded: '当前区域不需要横向滚动',
}

export const businessAcceptanceNavigationItems = [
  {
    key: 'targetEvidenceSummary',
    title: businessAcceptanceSectionTitles.targetEvidenceSummary,
    targetId: 'target-evidence-summary-section',
    searchText: businessAcceptanceSectionTitles.targetEvidenceSummary,
  },
  {
    key: 'nextStepRelease',
    title: businessAcceptanceSectionTitles.nextStepRelease,
    targetId: 'next-step-release-section',
    searchText: businessAcceptanceSectionTitles.nextStepRelease,
  },
  {
    key: 'firstFailure',
    title: businessAcceptanceSectionTitles.firstFailure,
    targetId: 'target-evidence-first-failure-section',
    searchText: businessAcceptanceSectionTitles.firstFailure,
  },
  {
    key: 'targetEvidenceTrace',
    title: businessAcceptanceSectionTitles.targetEvidenceTrace,
    targetId: 'target-evidence-trace-section',
    searchText: businessAcceptanceSectionTitles.targetEvidenceTrace,
  },
  {
    key: 'missingEvidence',
    title: businessAcceptanceSectionTitles.missingEvidence,
    targetId: 'missing-evidence-section',
    searchText: businessAcceptanceSectionTitles.missingEvidence,
  },
  {
    key: 'conflictEvidence',
    title: businessAcceptanceSectionTitles.conflictEvidence,
    targetId: 'conflict-evidence-section',
    searchText: businessAcceptanceSectionTitles.conflictEvidence,
  },
  {
    key: 'readFailure',
    title: businessAcceptanceSectionTitles.readFailure,
    targetId: 'read-failure-section',
    searchText: businessAcceptanceSectionTitles.readFailure,
  },
  {
    key: 'copyDiagnostic',
    title: businessAcceptanceSectionTitles.copyDiagnostic,
    targetId: 'technical-diagnostics-section',
    searchText: businessAcceptanceSectionTitles.copyDiagnostic,
  },
]

export function buildPageAcceptanceChecklist({
  fullUrl = '',
  version = BUSINESS_ACCEPTANCE_COPY_VERSION,
  pageTitle = '',
  sourceObjectNo = '',
  targetObjectNo = '',
  targetEvidenceStatus = '',
  nextStepAllowed = '',
  nextStepBlockReason = '',
} = {}) {
  const lines = [
    `版本：${version}`,
    `页面：${fullUrl}`,
    `页面标题：${pageTitle}`,
    `当前业务对象编号：${sourceObjectNo || '-'}`,
    `当前目标对象编号：${targetObjectNo || '-'}`,
    `目标证据状态：${targetEvidenceStatus || '-'}`,
    `是否允许进入下一步：${nextStepAllowed || '-'}`,
    `下一步阻断原因：${nextStepBlockReason || '-'}`,
    '',
    '页面可验收区域清单：',
  ]
  businessAcceptanceNavigationItems.forEach((item, index) => {
    lines.push(`${index + 1}. 区域标题：${item.title}`)
    lines.push(`   Ctrl+F：${item.searchText}`)
    lines.push(`   页面锚点：${item.targetId}`)
  })
  return lines.join('\n')
}

