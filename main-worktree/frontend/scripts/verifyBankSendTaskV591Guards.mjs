import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')

const service = read('backend/bank_send_task/services.py')
const canary = read('backend/bank_send_task/canary.py')
const model = read('backend/bank_send_task/models.py')
const view = read('backend/bank_send_task/views.py')
const runtime = read('frontend/src/meta/runtime/bankSendTaskRuntime.js')
const page = read('frontend/src/meta/pages/BankSendTaskPage.vue')
const actionRegistry = read('frontend/src/meta/runtime/pceBusinessActionRegistry.js')

const guards = {
  server_status_code_and_label:
    service.includes('"statusCode": task.status')
    && service.includes('"statusLabel": status_label'),
  required_chinese_labels:
    ['已准备', '已进入发送队列', '发送前就绪']
      .every(label => service.includes(label)),
  sent_label_forbidden:
    !service.match(/["']sent["']\s*:\s*["'][^"']+["']/),
  page_prioritizes_server_label:
    page.includes('prop="statusLabel" label="业务状态"')
    && page.includes('{{ row.statusLabel }}')
    && page.includes('prop="statusCode" label="状态编码"'),
  frontend_validates_instead_of_recalculates:
    runtime.includes('row.statusLabel !== SERVER_STATUS_LABELS[row.statusCode]')
    && page.includes(':value="currentTask?.statusLabel"'),
  canary_pool_has_no_business_status:
    model.includes('class BankSendTaskCanaryPoolEntry')
    && !model.split('class BankSendTaskCanaryPoolEntry')[1]
      .split('class Meta:')[0].includes('status ='),
  pool_minimums:
    canary.includes('NORMAL_POOL_MINIMUM = 8')
    && canary.includes('BLOCKED_POOL_MINIMUM = 5')
    && canary.includes('RESERVE_POOL_MINIMUM = 20'),
  blocked_scenarios_complete:
    [
      'APPROVAL_NOT_APPROVED',
      'FORMAL_PAYMENT_ORDER_FREEZE_INCONSISTENT',
      'RISK_REVIEW_NOT_PASSED',
      'FUNDS_NOT_AVAILABLE',
      'SEGREGATION_OF_DUTIES_NOT_PASSED',
    ].every(code => canary.includes(code)),
  canary_facts_complete:
    [
      'normalPoolCount',
      'blockedPoolCount',
      'reservePoolCount',
      'createdTaskCount',
      'blockedTaskCount',
      'availablePoolCount',
    ].every(field => canary.includes(`"${field}"`)),
  four_surfaces_consistent:
    view.includes('"canaryPoolFacts": bank_send_task_canary_facts()')
    && runtime.includes('canaryPoolFacts,')
    && page.includes('canaryPoolFacts: { ...canaryPoolFacts }'),
  isolated_database_guard:
    canary.includes('BankSendTask Canary Pool is test-database only')
    && canary.includes('productionUserDataWritten'),
  no_send_business_action:
    !actionRegistry.includes("action('send-bank'")
    && !actionRegistry.includes("action('execute-payment'"),
  protection_copy_complete:
    [
      '当前阶段：银行发送前准备阶段',
      '✓ 创建银行发送任务',
      '× 发送银行',
      '× 执行付款',
      '× 资金扣减',
      '× 生成银行流水',
      '× 生成付款凭证',
      '× 写总账',
    ].every(label => page.includes(label)),
}

const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failedGuards.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.59.1',
  guardCount: Object.keys(guards).length,
  blockerCount: failedGuards.length,
  failedGuards,
  guards,
  bankSendExecutionWriteCount: 0,
  businessProgressWriteCount: 0,
  productionUserDataWritten: false,
}
const output = path.join(
  root,
  'frontend',
  'test-results',
  'bank-send-task-v591',
)
fs.mkdirSync(output, { recursive: true })
fs.writeFileSync(
  path.join(output, 'static-guard-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (failedGuards.length) {
  throw new Error(`V59.1 static guards failed: ${failedGuards.join(', ')}`)
}
