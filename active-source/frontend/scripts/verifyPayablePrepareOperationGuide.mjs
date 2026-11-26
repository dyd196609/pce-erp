import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const pagePath = path.join(frontendRoot, 'src/meta/pages/PayablePreparePage.vue')
const source = fs.readFileSync(pagePath, 'utf8')

const errors = []

function assert(condition, message) {
  if (!condition) errors.push(message)
}

function includesText(text) {
  return source.includes(text)
}

const requiredTexts = [
  '采购应付预备',
  '业务流程导航',
  '返回质量检验入库',
  '查看来源入库流水',
  '进入应付核对',
  '本页操作说明',
  '本页业务目的',
  '操作前提',
  '建议操作顺序',
  '完成后输出',
  '当前阻断原因',
  '操作结果与下一步',
  '技术诊断与开发验证（点击展开）',
  '当前尚未生成采购应付预备',
  '当前无阻断原因，可以按照建议操作顺序继续检查。',
  '当前采购应付预备尚未生成，不能进入应付核对。',
  '当前记录没有可识别的来源入库流水编号。',
  '展开技术诊断',
  '收起技术诊断',
]

requiredTexts.forEach((text) => assert(includesText(text), `页面缺少固定文字：${text}`))

const requiredAcceptanceIds = [
  'page-operation-guide',
  'operation-purpose',
  'operation-prerequisites',
  'operation-sequence',
  'operation-output',
  'operation-block-reasons',
  'operation-result-next-step',
  'technical-diagnostics-toggle',
  'technical-diagnostics-content',
]

requiredAcceptanceIds.forEach((id) => {
  assert(includesText(`data-acceptance-id="${id}"`), `页面缺少稳定定位标识：${id}`)
})

const sequenceBlock = source.match(/data-acceptance-id="operation-sequence"[\s\S]*?<\/article>/)?.[0] || ''
const sequenceItemCount = (sequenceBlock.match(/<li>/g) || []).length
assert(sequenceItemCount === 8, `建议操作顺序应包含 8 个编号步骤，实际为 ${sequenceItemCount}`)

const outputBlock = source.match(/data-acceptance-id="operation-output"[\s\S]*?<\/article>/)?.[0] || ''
assert(outputBlock.includes('采购应付预备编号'), '完成后输出缺少采购应付预备编号')
assert(outputBlock.includes('来源入库流水编号'), '完成后输出缺少来源入库流水编号')
assert(outputBlock.includes('下一步：应付核对'), '完成后输出缺少下一步说明')

const blockReasonBlock = source.match(/data-acceptance-id="operation-block-reasons"[\s\S]*?<\/article>/)?.[0] || ''
assert(blockReasonBlock.includes('当前无阻断原因'), '当前阻断原因缺少无阻断说明')
assert(!/\b(blocked|disabled|invalid|false|source_not_found)\b/.test(blockReasonBlock), '当前阻断原因区域包含未翻译技术状态')

const diagnosticBlock = source.match(/class="technical-diagnostics-gate"[\s\S]*?<\/section>/)?.[0] || ''
assert(diagnosticBlock.includes('v-if="showTechnicalDiagnostics"'), '技术诊断内容未设置默认可收起')
assert(source.includes('const showTechnicalDiagnostics = ref(false)'), '技术诊断默认状态不是收起')
assert(diagnosticBlock.includes('此区域供开发和测试人员使用，普通业务操作人员不需要查看。'), '技术诊断缺少业务人员提示')

assert(source.includes('.page-header') && source.includes('display: none'), '旧页面头部未隐藏')
assert(source.includes('.finance-flow-nav') && source.includes('display: none'), '旧无关流程导航未隐藏')
assert(source.includes('.operation-shell > .plain-flow-guide'), '旧版说明块未设置隐藏规则')

const guideBlock = source.match(/data-acceptance-id="page-operation-guide"[\s\S]*?<h2 class="payable-business-area-title">/)?.[0] || ''
const forbiddenInGuide = ['付款凭证', '正式付款凭证', '核销', '总账', '过账', '银行流水', '付款模拟', '模拟沙箱', '技术测试矩阵']
const forbiddenFound = forbiddenInGuide.filter((text) => guideBlock.includes(text))
assert(forbiddenFound.length === 0, `本页操作说明包含无关模块文字：${forbiddenFound.join('、')}`)

assert(source.includes('latestGeneratedPrepare.value = outcome.payablePrepare || outcome'), '单条真实生成后未回写最近生成结果')
assert(source.includes('latestGeneratedPrepare.value = prepareRows.value[0] || null'), '批量真实生成后未回写最近生成结果')
assert(source.includes('function goCurrentSourceInventory()'), '缺少查看来源入库流水处理函数')
assert(source.includes('function goPayableCheck()'), '缺少进入应付核对处理函数')

if (errors.length) {
  console.error('采购应付预备操作说明校验失败：')
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}

console.log(JSON.stringify({
  page: 'verifyPayablePrepareOperationGuide',
  version: 'V1.14.0.1',
  operationGuideTitle: '本页操作说明',
  fixedSubTitleCount: 5,
  operationSequenceStepCount: sequenceItemCount,
  outputSectionNotEmpty: true,
  blockReasonSectionNotEmpty: true,
  technicalDiagnosticsDefaultCollapsed: true,
  navigationButtons: ['返回质量检验入库', '查看来源入库流水', '进入应付核对'],
  noBusinessDataWriteByVerifier: true,
  protectionFlags: {
    autoCreatePayablePrepare: false,
    fakeSuccessResult: false,
    modifyPurchaseOrder: false,
    modifyReceipt: false,
    modifyInspection: false,
    modifyInventory: false,
    generatePaymentApplication: false,
    generatePaymentVoucher: false,
    writeLedger: false,
    postLedger: false,
    writeOffPayment: false,
    executeRealPayment: false,
  },
  checkedAt: new Date().toISOString(),
}, null, 2))
