import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { listBusinessProcessNodes } from '../../src/meta/process/businessProcessRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const page = readFrontend('src/meta/pages/EnterpriseOSPage.vue')
const component = readFrontend('src/meta/components/ProcessNodeNavigation.vue')
const governance = fs.readFileSync(path.join(
  workspaceRoot,
  'docs/governance/04-页面与交互治理/PCE-ERP页面与交互开发规范.md',
), 'utf8')
const nodes = listBusinessProcessNodes('SCM_PURCHASE_SETTLEMENT')

test('SCM流程Registry节点数量、顺序与关键节点保持不变', () => {
  assert.equal(nodes.length, 22)
  assert.deepEqual(
    nodes.map(node => node.sequence),
    Array.from({ length: nodes.length }, (_, index) => index + 1),
  )
  for (const required of ['采购询价', '供应商报价', '报价比较', '采购核价', '供应商推荐', '采购订单准入']) {
    assert.ok(nodes.some(node => node.nodeName === required), required)
  }
})

test('节点保持卡片视觉身份并完整声明编号、状态、版本与入口', () => {
  for (const token of [
    'data-process-node-visual="card"',
    ':data-process-node-sequence="node.sequence"',
    ':data-process-node-status="node.acceptanceStatus"',
    ':data-process-node-version="node.pageVersion || undefined"',
    ':data-page-url="node.pageUrl || undefined"',
  ]) assert.ok(component.includes(token), token)
  assert.match(component, /box-sizing:\s*border-box/)
  assert.match(component, /min-width:\s*200px/)
  assert.match(component, /max-width:\s*200px/)
})

test('流程区域独占横向滚动且页面容器不横向溢出', () => {
  assert.ok(page.includes('data-horizontal-scroll-owner="process-region"'))
  assert.match(page, /\.process-node-track\s*\{[\s\S]*?overflow-x:\s*auto/)
  assert.match(page, /\.scm-purchase-process\s*\{[\s\S]*?min-width:\s*0;[\s\S]*?max-width:\s*100%;[\s\S]*?overflow-x:\s*hidden/)
  assert.match(page, /\.operation-shell,[\s\S]*?min-width:\s*0;[\s\S]*?max-width:\s*100%;[\s\S]*?overflow-x:\s*hidden/)
})

test('箭头连接按节点间隙渲染且未退化为表格', () => {
  assert.ok(page.includes('index < scmPurchaseProcessNodes.length - 1'))
  assert.ok(page.includes('class="process-arrow"'))
  assert.ok(page.includes('data-process-layout="card-flow"'))
  assert.doesNotMatch(page, /data-process-layout="table"/)
})

test('PROCESS-VISUAL-001写入现有页面治理规范', () => {
  assert.ok(governance.includes('PROCESS-VISUAL-001'))
  for (const rule of ['业务卡片', '页面级横向滚动', '流程区域内部', '编号', '阶段名称', '状态', '版本', '页面入口']) {
    assert.ok(governance.includes(rule), rule)
  }
})
