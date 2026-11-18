import { listBusinessProcessSteps } from './businessProcessRegistry.js'

export const BUSINESS_PAGE_SECTION_REGISTRY_VERSION = 'V1.14.0'

function businessSection(pageStepId, sectionId, sectionTitle, sequence, extra = {}) {
  return {
    pageStepId,
    sectionId,
    sectionTitle,
    sectionPurpose: extra.sectionPurpose || sectionTitle,
    sequence,
    previousSectionId: extra.previousSectionId || null,
    nextSectionId: extra.nextSectionId || null,
    prerequisiteCodes: extra.prerequisiteCodes || [],
    completionConditions: extra.completionConditions || [],
    outputFields: extra.outputFields || [],
    visibleWhen: extra.visibleWhen || 'always',
    lockedWhen: extra.lockedWhen || null,
    lockedReason: extra.lockedReason || '',
    isBusinessOperationSection: extra.isBusinessOperationSection !== false,
    isTechnicalSection: Boolean(extra.isTechnicalSection),
    introducedInVersion: BUSINESS_PAGE_SECTION_REGISTRY_VERSION,
  }
}

function defaultSectionsForStep(step) {
  const base = [
    businessSection(step.stepId, `${step.stepId}-context`, '流程上下文', 1, {
      sectionPurpose: '说明所属模块、业务流程、当前步骤、来源步骤和下一步骤。',
      outputFields: ['moduleName', 'processName', 'stepName', 'previousStepId', 'defaultNextStepId'],
    }),
    businessSection(step.stepId, `${step.stepId}-guide`, '本页操作说明', 2, {
      previousSectionId: `${step.stepId}-context`,
      sectionPurpose: '说明本页业务目的、前提、操作顺序、输出结果和阻断原因。',
      outputFields: ['operationPurpose', 'operationSequence', 'nextStepDescription'],
    }),
  ]
  const allowed = (step.allowedSections || []).filter((sectionId) => sectionId !== 'technical-diagnostics')
  allowed.forEach((sectionId, index) => {
    base.push(businessSection(step.stepId, sectionId, sectionId, index + 3, {
      previousSectionId: index === 0 ? `${step.stepId}-guide` : allowed[index - 1],
      nextSectionId: allowed[index + 1] || `${step.stepId}-technical-diagnostics`,
      sectionPurpose: `当前步骤 ${step.stepName} 的业务操作区域。`,
      completionConditions: step.completionStatusValues,
      outputFields: step.outputDocumentTypes,
    }))
  })
  base.push(businessSection(step.stepId, `${step.stepId}-technical-diagnostics`, '技术诊断与开发验证', allowed.length + 3, {
    previousSectionId: allowed[allowed.length - 1] || `${step.stepId}-guide`,
    sectionPurpose: '仅用于开发诊断、复制诊断数据、测试矩阵和历史版本说明。',
    visibleWhen: 'collapsed_by_default',
    isBusinessOperationSection: false,
    isTechnicalSection: true,
  }))
  return base
}

export const businessPageSections = listBusinessProcessSteps().flatMap(defaultSectionsForStep)

export function listBusinessPageSections() {
  return businessPageSections
}

export function listBusinessPageSectionsByStep(stepId) {
  return businessPageSections.filter((item) => item.pageStepId === stepId)
}

export function listBusinessOperationSectionsByStep(stepId) {
  return listBusinessPageSectionsByStep(stepId).filter((item) => item.isBusinessOperationSection)
}

export function listTechnicalSectionsByStep(stepId) {
  return listBusinessPageSectionsByStep(stepId).filter((item) => item.isTechnicalSection)
}
