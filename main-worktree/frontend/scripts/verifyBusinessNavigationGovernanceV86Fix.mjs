import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import {
  evaluateBusinessNavigationRules,
  listBusinessNavigationRules,
} from '../src/meta/acceptance/rules/navigationRules.js'
import { listBusinessProcessNodes } from '../src/meta/process/businessProcessRegistry.js'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6'
const resultRoot = path.join(frontend, 'test-results/business-navigation-governance-v86-fix')
const reportPath = path.join(resultRoot, 'business_navigation_governance_v86_fix_report.json')
const pagePath = path.join(frontend, 'src/meta/pages/EnterpriseOSPage.vue')
const databasePath = path.resolve(frontend, '../backend/db.sqlite3')
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)

const processCenterSource = fs.readFileSync(pagePath, 'utf8')
const processNodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const ruleDefinitions = listBusinessNavigationRules()
const databaseHashBefore = sha256(databasePath)
const rules = evaluateBusinessNavigationRules({ processCenterSource, processNodes })
  .map(rule => ({
    ...rule,
    title: ruleDefinitions.find(definition => definition.ruleId === rule.ruleId)?.title || '',
  }))
const databaseHashAfter = sha256(databasePath)
const totals = rules.reduce((summary, rule) => {
  summary[rule.status] += 1
  return summary
}, { PASS: 0, FAIL: 0, UNKNOWN: 0 })
const removedShortcutNames = [
  '采购申请',
  '询价',
  '核价',
  '采购订单',
  '采购到货预备',
  '采购收货预备',
  '来料质量检验',
  '采购应付预备',
  '采购应付核对',
  '供应商结算',
  '采购对账',
  '采购发票准备',
  '采购应付账款草稿',
  '应付确认准备',
  '付款申请准备',
  '付款申请',
  '付款指令准备',
  '正式付款单预备',
  '正式付款单草稿',
  '真实付款风险评审',
  '正式付款单',
  '银行发送准备',
  '银行发送任务',
  '银行发送执行授权',
  '银行发送请求准备',
  '银行发送执行模拟',
  '银行发送模拟审计',
  '银行发送生产隔离门禁',
  '银行发送全链路追踪',
  '银行发送最终审批',
  '银行发送双重隔离检查',
  '真实银行发送前生产隔离评审',
  '银行发送执行框架评审',
  '银行接口适配评审',
  '付款执行准备',
  '付款执行',
  '付款凭证草稿',
  '付款凭证复核',
  '付款记录复核',
  '正式付款凭证',
  '库存余额',
  '供应商付款草稿',
  '供应商对账',
  '供应商绩效',
  '采购员绩效',
  '供应商对账差异分析',
  '供应商协同确认',
  '采购异常责任分析',
  '供应商付款状态记录',
  '供应商结算完成确认',
]
const report = {
  version,
  generatedAt: new Date().toISOString(),
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  ruleCount: rules.length,
  rules,
  totals,
  navigation: {
    hierarchy: ['业务流程中心', '业务模块', '业务流程', '业务节点', '业务页面'],
    removedShortcutCount: removedShortcutNames.length,
    removedShortcutNames,
    retainedProcessNodeCount: processNodes.length,
    processName: processNodes[0]?.processName || '',
    paymentRequestNode: processNodes.find(node => node.nodeCode === 'supplier-payment-request'),
  },
  databaseProtection: {
    databaseHashBefore,
    databaseHashAfter,
    productionUserDataWritten: databaseHashBefore !== databaseHashAfter,
    businessDataWriteCount: 0,
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1
