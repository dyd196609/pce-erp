import { outcome } from './pageRules.js'

const make = (id, name, evaluate) => Object.freeze({ id, name, family: 'ACTION', evaluate })
const forbidden = ['银行发送', '立即发送', '执行发送', '提交银行', '付款执行', '扣款', '资金扣减']

export const actionRules = Object.freeze([
  make('ACTION-001', '按钮来自Business Action Registry', e => outcome(
    e.actions?.registrySource,
    'data-pce-action-source=PCE Business Action Registry',
    '未找到Business Action Registry来源标记',
  )),
  make('ACTION-002', '危险动作按钮不存在', e => outcome(
    Array.isArray(e.actions?.buttonTexts)
      ? forbidden.every(label => !e.actions.buttonTexts.includes(label))
      : null,
    `buttons=${JSON.stringify(e.actions?.buttonTexts || [])}`,
    '页面出现禁止业务动作按钮',
  )),
  make('ACTION-003', '查看类动作可用', e => outcome(
    Number.isInteger(e.actions?.viewActionCount) ? e.actions.viewActionCount > 0 : null,
    `viewActionCount=${e.actions?.viewActionCount}`,
    '页面没有查看类动作',
  )),
])
