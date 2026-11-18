import { pageRules } from './rules/pageRules.js'
import { listRules } from './rules/listRules.js'
import { statusRules } from './rules/statusRules.js'
import { factRules } from './rules/factRules.js'
import { actionRules } from './rules/actionRules.js'
import { securityRules } from './rules/securityRules.js'
import { observabilityRules } from './rules/observabilityRules.js'
import { filterRules } from './rules/filterRules.js'

export const PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION = 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0'

export const PCE_PAGE_ACCEPTANCE_RESULT = Object.freeze({
  PASS: 'PASS',
  FAIL: 'FAIL',
  UNKNOWN: 'UNKNOWN',
})

export const PCE_PAGE_ACCEPTANCE_RULES = Object.freeze([
  ...pageRules,
  ...listRules,
  ...statusRules,
  ...factRules,
  ...actionRules,
  ...securityRules,
  ...observabilityRules,
  ...filterRules,
])

export const PCE_PAGE_ACCEPTANCE_TARGETS = Object.freeze([
  {
    page: '/finance/bank-send-prepares',
    hashRoute: '/#/finance/bank-send-prepares',
    pageId: 'bank-send-preparation',
    tableId: 'bank-send-preparations-main',
    scrollId: 'bank-send-preparation-horizontal-scroll',
    title: '银行发送准备',
    moduleCode: 'FIN_BANK_SEND_PREPARATION',
    factKey: 'bankSendPreparationFacts',
    countField: 'bankSendPreparationCount',
    expectedCount: 8,
    expectedStatusLabel: '已准备',
    technicalStatuses: ['preview_only', 'ready_to_send', 'ready_to_dispatch', 'pending_review', 'queued'],
  },
  {
    page: '/finance/bank-send-tasks',
    hashRoute: '/#/finance/bank-send-tasks',
    pageId: 'bank-send-task',
    tableId: 'bank-send-tasks-main',
    scrollId: 'bank-send-task-horizontal-scroll',
    title: '银行发送任务',
    moduleCode: 'FIN_BANK_SEND_TASK',
    factKey: 'bankSendTaskFacts',
    countField: 'taskCount',
    expectedCount: 8,
    expectedStatusLabel: '发送前就绪',
    technicalStatuses: ['ready_to_send', 'ready_to_dispatch', 'pending_review', 'queued'],
  },
  {
    page: '/finance/bank-send-requests',
    hashRoute: '/#/finance/bank-send-requests',
    pageId: 'bank-send-request',
    tableId: 'bank-send-requests-main',
    scrollId: 'bank-send-requests-horizontal-scroll',
    title: '银行发送请求准备',
    moduleCode: 'FIN_BANK_SEND_REQUEST',
    factKey: 'bankSendRequestFacts',
    countField: 'requestCount',
    expectedCount: 8,
    expectedStatusLabel: '发送前待分发',
    technicalStatuses: ['ready_to_send', 'ready_to_dispatch', 'ready_for_execution', 'pending_review', 'queued'],
  },
])

export function createPageAcceptanceReport(page, checks, metadata = {}) {
  const count = result => checks.filter(check => check.result === result).length
  return {
    contractVersion: PCE_PAGE_ACCEPTANCE_CONTRACT_VERSION,
    page,
    totalChecks: checks.length,
    pass: count(PCE_PAGE_ACCEPTANCE_RESULT.PASS),
    fail: count(PCE_PAGE_ACCEPTANCE_RESULT.FAIL),
    unknown: count(PCE_PAGE_ACCEPTANCE_RESULT.UNKNOWN),
    checks,
    ...metadata,
  }
}

export function runPageAcceptanceRules(evidence) {
  return PCE_PAGE_ACCEPTANCE_RULES.map(rule => {
    try {
      return { id: rule.id, name: rule.name, family: rule.family, ...rule.evaluate(evidence) }
    } catch (error) {
      return {
        id: rule.id,
        name: rule.name,
        family: rule.family,
        result: PCE_PAGE_ACCEPTANCE_RESULT.UNKNOWN,
        evidence: '',
        reason: `规则执行异常：${error.message}`,
      }
    }
  })
}

export function classifyUnknownChecks(page, checks, plannedFixVersion = 'V1.14.2.8.4.7.63') {
  return checks
    .filter(check => check.result === PCE_PAGE_ACCEPTANCE_RESULT.UNKNOWN)
    .map(check => ({
      id: check.id,
      reason: check.reason || '缺少可判定证据',
      affectedPage: page,
      plannedFixVersion,
    }))
}
