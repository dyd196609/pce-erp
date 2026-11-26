import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const version = 'V1.14.2.8'

const pageFiles = [
  { file: 'src/meta/pages/PayablePreparePage.vue', label: '采购应付预备' },
  { file: 'src/meta/pages/InvoicePreparePage.vue', label: '采购发票准备' },
  { file: 'src/meta/pages/AccountPayableConfirmPage.vue', label: '应付确认' },
  { file: 'src/meta/pages/PaymentApplicationPage.vue', label: '付款申请' },
]

const failures = []

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function assert(condition, message) {
  if (!condition) failures.push(message)
}

for (const page of pageFiles) {
  const source = read(page.file)
  assert(source.includes('type="selection"'), `${page.label} 缺少表格选择列`)
  assert(source.includes('fixed="left"'), `${page.label} 选择列未固定在左侧`)
  assert(source.includes('business-table-selection-column'), `${page.label} 缺少选择列验收标识`)
  assert(source.includes('data-acceptance-id="business-flow-selected-count"'), `${page.label} 缺少已选择数量显示`)
  assert(source.includes('pce-fixed-index-column'), `${page.label} 缺少序号列固定验收标识`)
  assert(source.includes('pce-fixed-primary-no-column'), `${page.label} 缺少主业务编号固定验收标识`)
  assert(source.includes('data-acceptance-id="business-flow-action-toolbar"'), `${page.label} 缺少业务流程操作工具栏`)
  assert(source.includes('data-acceptance-id="business-flow-primary-actions"'), `${page.label} 缺少业务主操作区域`)
  assert(source.includes('data-acceptance-id="business-flow-secondary-actions"'), `${page.label} 缺少辅助操作区域`)
  assert(source.includes('data-acceptance-id="business-flow-primary-action-button"'), `${page.label} 缺少业务动作按钮验收标识`)
  assert(source.includes('data-acceptance-id="business-flow-action-disabled-reason"'), `${page.label} 缺少未选择记录禁用原因`)
  assert(!source.includes('copyDiagnostics'), `${page.label} 主页面仍保留页面级复制诊断函数`)
  assert(!source.includes('复制诊断数据'), `${page.label} 主业务工具栏仍显示复制诊断数据按钮`)
  assert(!source.includes('V1.14.2.1'), `${page.label} 仍包含旧诊断版本 V1.14.2.1`)
  assert(!source.includes('console.log('), `${page.label} 业务按钮不能是 console-only`)
}

const shell = read('src/meta/components/BusinessOperationPageShell.vue')
assert(shell.includes('const runtimeAcceptanceVersion = BUSINESS_ACCEPTANCE_COPY_VERSION'), `统一壳层版本不是 ${version}`)
assert(shell.includes('copyRuntimeDiagnostics'), '统一壳层缺少复制诊断实现')
assert(shell.includes('data-acceptance-id="copy-diagnostic-data-button"'), '统一壳层缺少复制诊断按钮标识')
assert(shell.includes('technical-diagnostics-content'), '统一壳层复制诊断未放入技术诊断区域')
assert(shell.includes('selectionColumnRequired'), '统一壳层诊断缺少 selectionColumnRequired')
assert(shell.includes('selectionColumnVisible'), '统一壳层诊断缺少 selectionColumnVisible')
assert(shell.includes('selectedRowCount'), '统一壳层诊断缺少 selectedRowCount')
assert(shell.includes('businessActionButtonCount'), '统一壳层诊断缺少 businessActionButtonCount')
assert(shell.includes('copyDiagnosticButtonLocation'), '统一壳层诊断缺少 copyDiagnosticButtonLocation')
assert(shell.includes('targetEvidenceStatus'), '统一壳层诊断缺少 targetEvidenceStatus')
assert(shell.includes('runtimeDisplayConsistencyPassed'), '统一壳层诊断缺少 runtimeDisplayConsistencyPassed')
assert(shell.includes('missingEvidenceCodes'), '统一壳层诊断缺少 missingEvidenceCodes')

const operationRegistry = read('src/meta/process/businessOperationPageRegistry.js')
assert(operationRegistry.includes("routePath: '/finance/payment-order-drafts'"), '业务页面注册缺少正式付款单草稿路径')
assert(operationRegistry.includes("routePath: '/finance/payment-risk-reviews'"), '业务页面注册缺少真实付款风险评审路径')

const processRegistry = read('src/meta/process/businessProcessRegistry.js')
assert(processRegistry.includes('payment-order-draft'), '业务流程注册缺少正式付款单草稿步骤')
assert(processRegistry.includes('payment-risk-review'), '业务流程注册缺少真实付款风险评审步骤')

if (failures.length) {
  console.error(`${version} 业务选择列与流程按钮校验失败：${failures.length} 项`)
  failures.forEach((item) => console.error(`- ${item}`))
  process.exit(1)
}

console.log(`${version} 业务选择列、流程按钮、页面名称与诊断入口源码校验通过。`)

