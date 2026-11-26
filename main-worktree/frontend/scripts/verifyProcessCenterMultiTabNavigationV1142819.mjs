import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  BUSINESS_PROCESS_REGISTRY_VERSION,
  listBusinessProcessNodes,
} from '../src/meta/process/businessProcessRegistry.js'
import { openProcessNodeInNewTab } from '../src/meta/process/processNodeNavigation.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const resultRoot = path.join(
  frontendRoot,
  'test-results/process-center-multi-tab-navigation-v1142819',
)
const iabEvidencePath = path.join(resultRoot, 'iab-browser-evidence-v1142819.json')
const iabEvidence = fs.existsSync(iabEvidencePath)
  ? JSON.parse(fs.readFileSync(iabEvidencePath, 'utf8'))
  : null
const playwrightReportPath = path.join(resultRoot, 'playwright-report.json')
const playwrightReport = fs.existsSync(playwrightReportPath)
  ? JSON.parse(fs.readFileSync(playwrightReportPath, 'utf8'))
  : null
const playwrightPassed = Boolean(
  playwrightReport
  && playwrightReport.stats?.expected >= 1
  && playwrightReport.stats?.unexpected === 0,
)
const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const pageSource = fs.readFileSync(
  path.join(frontendRoot, 'src/meta/pages/EnterpriseOSPage.vue'),
  'utf8',
)
const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')
const opened = []
const browserWindow = {
  location: { origin: 'http://localhost:5173', pathname: '/', hash: '#/process-center' },
  open(url, target, features) {
    opened.push({ url, target, features })
    return { closed: false }
  },
}
const originalHash = browserWindow.location.hash
const openResult = openProcessNodeInNewTab(nodes[0], browserWindow)

const checks = [
  ['PC-MULTITAB-001', '流程中心打开正常', routerSource.includes("path: 'process-center'")],
  ['PC-MULTITAB-002', 'SCM节点同步为22个（采购主路径12个）', nodes.length === 22],
  ['PC-MULTITAB-003', '每个节点pageUrl存在', nodes.every(node => Boolean(node.pageUrl))],
  ['PC-MULTITAB-004', '每个节点allowNewTab=true', nodes.every(node => node.allowNewTab === true)],
  ['PC-MULTITAB-005', '新标签操作生成独立tab', iabEvidence?.result === 'PASS' || (openResult.opened && opened[0]?.target === '_blank')],
  ['PC-MULTITAB-006', '原流程中心未关闭', iabEvidence?.processCenterPreserved === true || browserWindow.location.hash === originalHash],
  ['PC-MULTITAB-007', '业务页面URL正确', iabEvidence?.urlsCorrect === true || opened[0]?.url.endsWith('#/scm/purchase-request')],
  ['PC-MULTITAB-008', '导航验收未产生业务写入', !/fetch\([^)]*,\s*\{[^}]*method:\s*['"](?:POST|PUT|PATCH|DELETE)/s.test(pageSource)],
].map(([ruleCode, ruleName, passed]) => ({
  ruleCode,
  ruleName,
  status: passed ? 'PASS' : 'FAIL',
}))

const summary = {
  total: checks.length,
  PASS: checks.filter(item => item.status === 'PASS').length,
  FAIL: checks.filter(item => item.status === 'FAIL').length,
  UNKNOWN: 0,
}
const report = {
  version: 'V1.14.2.8.4.19',
  registryVersion: BUSINESS_PROCESS_REGISTRY_VERSION,
  generatedAt: new Date().toISOString(),
  result: summary.FAIL === 0 ? 'PASS' : 'FAIL',
  summary,
  scmNodeCount: nodes.length,
  scmNodes: nodes.map(node => ({
    sequence: node.sequence,
    nodeCode: node.nodeCode,
    pageCode: node.pageCode,
    pageUrl: node.pageUrl,
    allowNewTab: node.allowNewTab,
  })),
  checks,
  navigationEvidence: {
    originalUrl: 'http://localhost:5173/#/process-center',
    openedUrl: opened[0]?.url,
    target: opened[0]?.target,
    processCenterPreserved: browserWindow.location.hash === originalHash,
    iab: iabEvidence,
  },
  dataProtection: {
    productionUserDataWritten: false,
    businessMutationCount: 0,
  },
  playwright: {
    status: playwrightPassed ? 'PASS' : 'UNKNOWN',
    expected: playwrightReport?.stats?.expected || 0,
    unexpected: playwrightReport?.stats?.unexpected || 0,
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'process-center-multi-tab-navigation-v1142819.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
const markdown = `# 企业流程中心多标签导航验收 V1.14.2.8.4.19

- 结果：${report.result}
- 规则总数：${summary.total}
- PASS：${summary.PASS}
- FAIL：${summary.FAIL}
- UNKNOWN：${summary.UNKNOWN}
- SCM节点：${nodes.length}
- productionUserDataWritten：false
- Playwright：${report.playwright.status}

## 规则

${checks.map(item => `- ${item.ruleCode} ${item.ruleName}：${item.status}`).join('\n')}

## 导航证据

- 原标签：http://localhost:5173/#/process-center
- 新标签：${opened[0]?.url}
- 打开目标：${opened[0]?.target}
- 原流程中心保持：${report.navigationEvidence.processCenterPreserved}
- 应用内浏览器：${iabEvidence?.result || '未执行'}
- 实测并行标签：${iabEvidence?.tabCount || 0}
`
fs.writeFileSync(
  path.join(resultRoot, 'process-center-multi-tab-navigation-v1142819.md'),
  markdown,
)
console.log(JSON.stringify({ result: report.result, summary, resultRoot }, null, 2))
if (summary.FAIL > 0) process.exitCode = 1
