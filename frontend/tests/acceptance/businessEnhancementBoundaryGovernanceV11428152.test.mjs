import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const readGovernance = file => fs.readFileSync(path.join(governanceRoot, file), 'utf8')

test('required governance assets and human reverse validation are loaded', () => {
  const files = [
    'CODEX执行命令规范.md',
    'PCE-ERP开发治理总规范.md',
    '统一列表运行层规范.md',
    '页面开发模板.md',
    '一页一验收规范.md',
    '治理符合性检查矩阵.md',
    '问题案例库.md',
  ]
  for (const file of files) assert.ok(readGovernance(file).trim(), file)
  const command = readGovernance('CODEX执行命令规范.md')
  assert.match(command, /人工验收反向校验机制/)
  assert.match(command, /AUTO_PASS_HUMAN_FAIL/)
})

test('boundary rule defines business enhancement and direct modification scope', () => {
  const boundary = readGovernance('业务增强版本修改边界规范.md')
  for (const expected of [
    'BUSINESS-ENHANCEMENT-BOUNDARY-001',
    '业务增强版本定义',
    '业务模型',
    'Provider',
    '页面业务区域',
    'SupplierQuote',
    'MaterialPriceContext',
    'PriceReferenceContext',
    'SupplierRecommendationDecision',
    '不得破坏已有 Provider',
  ]) assert.match(boundary, new RegExp(expected))
})

test('public capability changes require governance assessment', () => {
  const boundary = readGovernance('业务增强版本修改边界规范.md')
  for (const expected of [
    'List Runtime',
    'Page Shell',
    'Process Center',
    '公共组件',
    '治理评估',
    '影响范围报告',
    '公共页面自动回归',
    '真实页面人工验收',
    'BUSINESS_ENHANCEMENT_BOUNDARY_BLOCKED',
  ]) assert.match(boundary, new RegExp(expected))
  for (const forbidden of [
    '禁止为单个业务页面直接修改公共组件',
    '禁止为展示业务信息修改基础布局',
    '禁止复制公共组件形成页面私有版本',
    '禁止绕过 Runtime 直接控制',
  ]) assert.match(boundary, new RegExp(forbidden))
})

test('development governance and CODEX command rules consume the boundary', () => {
  const development = readGovernance('PCE-ERP开发治理总规范.md')
  const command = readGovernance('CODEX执行命令规范.md')
  assert.match(development, /业务增强版本修改边界/)
  assert.match(development, /GOV-001/)
  assert.match(development, /PROCESS-008/)
  assert.match(development, /PROCESS-010/)
  assert.match(command, /CODEX-COMMAND-004/)
  for (const type of ['业务增强版本', '平台能力版本', '公共组件版本']) {
    assert.match(command, new RegExp(type))
  }
  for (const target of ['List Runtime', 'Page Shell', 'Process Center', '公共组件']) {
    assert.match(command, new RegExp(target))
  }
})

test('CASE-GOV-001 and compliance matrix close the governance loop', () => {
  const cases = readGovernance('问题案例库.md')
  const matrix = readGovernance('治理符合性检查矩阵.md')
  for (const expected of [
    'CASE-GOV-001',
    'V1.14.2.8.18.15',
    '业务流程中心',
    '采购询价',
    '供应商报价',
    '报价比较',
    '开发边界治理问题',
    'BUSINESS-ENHANCEMENT-BOUNDARY-001',
  ]) assert.match(cases, new RegExp(expected))
  assert.match(matrix, /BUSINESS-ENHANCEMENT-BOUNDARY-001/)
  assert.match(matrix, /verifyBusinessEnhancementBoundaryGovernanceV11428152\.mjs/)
})
