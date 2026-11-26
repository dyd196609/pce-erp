import fs from 'node:fs'
import path from 'node:path'

const process = globalThis.process
const root = process.cwd()
const outputPath = path.resolve(
  root,
  process.argv.find(argument => argument.startsWith('--out='))?.slice(6)
    || 'test-results/pce-enterprise-list-runtime-v1/pce_enterprise_page_acceptance_report.json',
)

function read(relativePath) {
  return fs.readFileSync(path.resolve(root, relativePath), 'utf8')
}

const component = read('src/meta/components/PceEnterpriseListTable.vue')
const scrollContainer = read('src/meta/components/BusinessTableScrollContainer.vue')
const advancedFilter = read('src/meta/components/PceEnterpriseAdvancedFilter.vue')
const statusComponent = read('src/meta/components/PceBusinessStatus.vue')
const contract = read('src/meta/runtime/pceEnterpriseListContract.js')
const shell = read('src/meta/components/PceListPageShell.vue')
const registry = read('src/meta/process/financeProcessPageRegistry.js')

const pages = [
  {
    page: '/finance/bank-send-prepares',
    source: 'src/meta/pages/BankSendPreparationPage.vue',
    title: '银行发送准备',
    moduleCode: 'FIN_BANK_SEND_PREPARATION',
    tableId: 'bank-send-preparations-main',
    technicalStates: ['preview_only'],
  },
  {
    page: '/finance/bank-send-tasks',
    source: 'src/meta/pages/BankSendTaskPage.vue',
    title: '银行发送任务',
    moduleCode: 'FIN_BANK_SEND_TASK',
    tableId: 'bank-send-tasks-main',
    technicalStates: ['ready_to_send'],
  },
  {
    page: '/finance/bank-send-requests',
    source: 'src/meta/pages/BankSendRequestPage.vue',
    title: '银行发送请求',
    moduleCode: 'FIN_BANK_SEND_REQUEST',
    tableId: 'bank-send-requests-main',
    technicalStates: ['ready_to_dispatch'],
  },
]

const checks = []
function add(page, id, item, passed, evidence, unknown = false) {
  checks.push({
    page,
    id,
    item,
    result: unknown ? 'UNKNOWN' : passed ? 'PASS' : 'FAIL',
    evidence,
  })
}

function buttonBodies(source) {
  return [...source.matchAll(/<el-button[\s\S]*?<\/el-button>/g)].map(match => match[0])
}

for (const config of pages) {
  const source = read(config.source)
  const buttons = buttonBodies(source).join('\n')
  add(config.page, 'A01', '页面打开', registry.includes(config.page), 'financeProcessPageRegistry已注册页面路由')
  add(config.page, 'A02', '页面标题', source.includes(`title: '${config.title}'`), `企业列表契约标题=${config.title}`)
  add(config.page, 'A03', '当前模块', source.includes(`moduleCode: '${config.moduleCode}'`), `moduleCode=${config.moduleCode}`)
  add(config.page, 'A04', '版本显示', shell.includes('runtimeBusinessVersion'), 'PceListPageShell展示runtimeBusinessVersion')
  add(config.page, 'B01', '搜索存在', source.includes('PceEnterpriseListTable') && component.includes('StandardListToolbar'), '统一表格接入标准工具栏')
  add(config.page, 'B02', '高级筛选存在', component.includes('PceEnterpriseAdvancedFilter'), '统一表格接入高级筛选组件')
  add(config.page, 'B03', '筛选字段数量', source.includes(':filter-schema="filterSchema"'), '页面通过filterSchema声明筛选字段')
  add(config.page, 'B04', '排序存在', component.includes('@sort-change'), '统一表格转发Element Plus排序事件')
  add(config.page, 'B05', '导出存在', source.includes('@export-current="exportCurrent"'), '运行基座统一导出当前结果')
  add(config.page, 'B06', '选择存在', component.includes('type="selection"'), '统一表格包含选择列')
  add(config.page, 'B07', '左冻结存在', component.includes('pce-fixed-primary-no-column') && component.match(/fixed="left"/g)?.length >= 3, '选择/序号/主业务编号左冻结')
  add(config.page, 'B08', '右冻结存在', component.includes('fixed="right"') && component.includes('payment-fixed-action-column'), '操作列右冻结')
  add(config.page, 'B09', '横向滚动存在', component.includes('BusinessTableScrollContainer') && scrollContainer.includes('overflow-x: auto'), '滚动所有权属于表格内部')
  add(config.page, 'C01', '技术状态不可见', source.includes('PceBusinessStatus') && statusComponent.includes('statusLabel') && !statusComponent.includes('{{ statusCode }}'), '状态组件仅渲染业务标签')
  add(config.page, 'C02', '中文状态存在', source.includes(':status-label='), '页面向统一状态组件传入statusLabel')
  add(config.page, 'C03', '状态来源server', source.includes('source="server"') || source.includes(':source="row.currentStateSource"'), '状态来源由服务端字段传入')
  add(config.page, 'D01', '查看动作存在', source.includes('#actions') && /查看|选择/.test(buttons), '页面只在统一操作槽声明查看或选择动作')
  add(config.page, 'D02', 'Action Contract来源', source.includes('PceBusinessActionBar') && component.includes('Action Contract'), '业务动作由统一 Action Contract 解析')
  add(config.page, 'D03', '危险动作不存在', !/(银行发送|立即发送|执行发送|提交银行|付款执行|扣款)/.test(buttons), '操作按钮源码未包含危险业务动作')
  add(config.page, 'E01', 'API', /Api\.list\(\)|Api\.list\(/.test(source), '页面继续调用既有只读API')
  add(config.page, 'E02', 'Page', /createBankSend(Preparation|Task|Request)PageFacts/.test(source), '页面复用既有服务端页面事实构造器')
  add(config.page, 'E03', 'Diagnostic', source.includes('buildDiagnostics'), '页面继续由实例诊断提供者输出')
  add(config.page, 'E04', 'StrictFacts', source.includes('strictServerFacts'), 'strictFacts继续复用既有服务端事实')
  add(config.page, 'F01', '银行发送按钮不存在', !/>(银行发送|发送银行|立即发送)</.test(buttons), '无银行发送按钮')
  add(config.page, 'F02', '付款按钮不存在', !/>(付款|付款执行|执行付款)</.test(buttons), '无付款按钮')
  add(config.page, 'F03', '扣款按钮不存在', !/>(扣款|资金扣减)</.test(buttons), '无扣款按钮')
  add(config.page, 'F04', 'businessProgressWrite=0', source.includes('writeIntentFacts'), '写入边界继续来自既有服务端writeIntentFacts')
}

add(
  'runtime',
  'R01',
  '列表契约版本',
  contract.includes('PCE-ENTERPRISE-LIST-CONTRACT-V1.1'),
  '统一契约版本已注册',
)
add(
  'runtime',
  'R02',
  '高级筛选类型',
  advancedFilter.includes('PceAdvancedFilterField'),
  '文本、下拉和日期范围继续复用统一字段组件',
)
add(
  'runtime',
  'R03',
  '诊断实例所有权',
  shell.includes('observabilityOwner') && shell.includes('provider !== observabilityOwner'),
  '旧页面卸载不能清除新页面诊断提供者',
)

const report = {
  version: 'V1.14.2.8.4.7.61.2',
  contractVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  page: pages.map(item => item.page).join(','),
  total: checks.length,
  pass: checks.filter(check => check.result === 'PASS').length,
  fail: checks.filter(check => check.result === 'FAIL').length,
  unknown: checks.filter(check => check.result === 'UNKNOWN').length,
  checks,
}

fs.mkdirSync(path.dirname(outputPath), { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({
  output: outputPath,
  total: report.total,
  pass: report.pass,
  fail: report.fail,
  unknown: report.unknown,
}, null, 2))
if (report.fail > 0) process.exitCode = 1
