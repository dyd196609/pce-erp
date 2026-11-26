import { evaluatePaymentVoucherPrepareAcceptanceData } from './paymentVoucherPrepareAcceptanceEvaluator.js'

export const PAYMENT_VOUCHER_PREPARE_PAGE_ACCEPTANCE_RUNTIME_VERSION = 'V1.14.2.7.1'

export const PAYMENT_VOUCHER_PREPARE_ALLOWED_BUTTON_TEXTS = [
  '返回付款执行准备',
  '企业结算边界',
  '复制诊断数据',
]

export const PAYMENT_VOUCHER_PREPARE_FORBIDDEN_BUTTON_KEYWORDS = [
  '执行预检查',
  '重新预检查',
  '保存预检查结果',
  '启动状态机',
  '执行模拟',
  '创建模拟结果',
  '生成付款凭证准备',
  '生成付款凭证',
  '核销',
  '写总账',
  '过账',
  '真实付款',
  '导出',
]

function collectTextByAcceptanceId(documentRef) {
  const domText = {}
  if (!documentRef?.querySelectorAll) return domText
  documentRef.querySelectorAll('[data-acceptance-id]').forEach((node) => {
    const key = node.getAttribute('data-acceptance-id')
    if (key) domText[key] = String(node.textContent || '').replace(/\s+/g, ' ').trim()
  })
  return domText
}

function collectButtonTexts(documentRef) {
  if (!documentRef?.querySelectorAll) return []
  return Array.from(documentRef.querySelectorAll('button,a'))
    .map((node) => String(node.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
}

export function evaluatePaymentVoucherPrepareButtonWhitelist(buttonTexts = []) {
  const forbiddenButtons = buttonTexts.filter((text) => (
    PAYMENT_VOUCHER_PREPARE_FORBIDDEN_BUTTON_KEYWORDS.some((keyword) => text.includes(keyword))
  ))
  const allowedButtons = buttonTexts.filter((text) => (
    PAYMENT_VOUCHER_PREPARE_ALLOWED_BUTTON_TEXTS.some((allowedText) => text.includes(allowedText))
  ))
  return {
    allowedButtonTexts: PAYMENT_VOUCHER_PREPARE_ALLOWED_BUTTON_TEXTS,
    forbiddenButtonKeywords: PAYMENT_VOUCHER_PREPARE_FORBIDDEN_BUTTON_KEYWORDS,
    buttonTexts,
    allowedButtonCount: allowedButtons.length,
    forbiddenButtonCount: forbiddenButtons.length,
    forbiddenButtons,
    whitelistStatus: forbiddenButtons.length === 0 ? 'passed' : 'failed',
  }
}

export function collectPaymentVoucherPreparePageAcceptanceRuntime(documentRef = globalThis.document) {
  const domText = collectTextByAcceptanceId(documentRef)
  const buttonTexts = collectButtonTexts(documentRef)
  const buttons = evaluatePaymentVoucherPrepareButtonWhitelist(buttonTexts)
  return {
    runtimeVersion: PAYMENT_VOUCHER_PREPARE_PAGE_ACCEPTANCE_RUNTIME_VERSION,
    runtimeEvaluated: Boolean(documentRef?.querySelectorAll),
    domText,
    buttons,
  }
}

export function evaluatePaymentVoucherPreparePageRuntimeAcceptance(data = {}, documentRef = globalThis.document) {
  const runtime = collectPaymentVoucherPreparePageAcceptanceRuntime(documentRef)
  return {
    ...runtime,
    acceptanceResult: evaluatePaymentVoucherPrepareAcceptanceData({
      ...data,
      domText: {
        ...(data.domText || {}),
        ...runtime.domText,
      },
      buttons: {
        ...(data.buttons || {}),
        ...runtime.buttons,
      },
    }),
  }
}
