import fs from 'node:fs/promises'
import path from 'node:path'
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool'

const outputPath = path.resolve(
  'outputs/engineering-table-process-config-save-closure-20260919/产品设计导入模板.xlsx',
)
const workbook = Workbook.create()
const sheet = workbook.worksheets.add('产品设计导入')
sheet.showGridLines = false
sheet.freezePanes.freezeRows(5)
sheet.freezePanes.freezeColumns(3)

sheet.getRange('A2:R2').merge()
sheet.getRange('A2').values = [['产品设计导入模板']]
sheet.getRange('A3:R3').merge()
sheet.getRange('A3').values = [[
  '更新必须填写稳定产品标识；新增必须填写订单行号。系统字段、来源文件与历史记录不可修改。尺寸按每个产品独立填写。',
]]
sheet.getRange('A5:R7').values = [
  [
    '操作', '稳定产品标识', '订单行号', '产品名称', '安装位置', '实物数量', '实物单位代码',
    '设计长(mm)', '设计宽(mm)', '第三尺寸(mm)', '第三尺寸语义', '产品分类代码',
    '工艺配置代码', '油漆工艺代码', '封边方式代码', '见光条件代码', '设计说明', '修订原因',
  ],
  [
    '更新', 'SO202609180003-DES-01-SRC-示例', '', '示例房门', '次卧', 1, 'PCS',
    2045, 938, 265, '墙厚', 'PDE-DOOR', 'QSFB/FM', 'QSFB', 'EDGE-FOUR-SIDES', 'DOUBLE_FACE',
    '示例数据，仅用于说明字段', '请填写本次变更依据',
  ],
  [
    '新增', '', 3, '示例柜体部件', '图15 书房', 1, 'PCS',
    800, 400, 18, '部件厚', 'PDE-CABINET', '', '', 'EDGE-FOUR-SIDES', 'DOUBLE_FACE',
    '新增设计项示例', '请填写新增依据',
  ],
]

const all = sheet.getRange('A2:R200')
all.format.font = { name: 'Arial', size: 10, color: '#172033' }
all.format.verticalAlignment = 'center'
sheet.getRange('A2:R2').format = {
  font: { name: 'Arial', size: 14, bold: true, color: '#17365D' },
  rowHeight: 28,
}
sheet.getRange('A3:R3').format = {
  font: { name: 'Arial', size: 10, italic: true, color: '#52606D' },
  wrapText: true,
  rowHeight: 34,
}
sheet.getRange('A5:R5').format = {
  fill: '#1F4E78',
  font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
  horizontalAlignment: 'center',
  verticalAlignment: 'center',
  wrapText: true,
  rowHeight: 32,
  borders: { preset: 'all', style: 'thin', color: '#FFFFFF' },
}
sheet.getRange('A6:R7').format = {
  fill: '#FFF8E1',
  borders: { preset: 'inside', style: 'thin', color: '#E3E8EF' },
}
sheet.getRange('A6:A200').dataValidation = { rule: { type: 'list', values: ['更新', '新增'] } }
sheet.getRange('K6:K200').dataValidation = { rule: { type: 'list', values: ['墙厚', '部件厚', '实际厚度'] } }
sheet.getRange('P6:P200').dataValidation = { rule: { type: 'list', values: ['SINGLE_FACE', 'DOUBLE_FACE', 'UNFINISHED', 'EXPLICIT_NONE', 'NOT_APPLICABLE', 'UNKNOWN'] } }
sheet.getRange('C6:C200').format.numberFormat = '0'
sheet.getRange('F6:F200').format.numberFormat = '0.######'
sheet.getRange('H6:J200').format.numberFormat = '0.######'

const widths = [12, 34, 12, 22, 20, 12, 16, 15, 15, 16, 18, 18, 18, 18, 20, 20, 28, 30]
widths.forEach((width, index) => {
  sheet.getRangeByIndexes(0, index, 200, 1).format.columnWidth = width
})

const source = sheet.getRange('T2:W11')
source.values = [
  ['字段说明', '新增', '更新', '口径'],
  ['稳定产品标识', '留空', '必填', '只允许使用系统导出的稳定标识'],
  ['订单行号', '必填', '留空', '当前订单1至4行'],
  ['第三尺寸语义', '必填', '必填', '房门=墙厚；三合一=部件厚；其他=实际厚度'],
  ['封边方式代码', '选填', '选填', '使用正式工程选项代码'],
  ['见光条件代码', '选填', '选填', '使用模板下拉中的受治理代码'],
  ['工艺配置代码', '留空', '选填', '完整配置，如QSFB/FM；仅允许该稳定产品现有来源适用值'],
  ['油漆工艺代码', '留空', '选填', '独立油漆工艺，如QSFB；必须与完整配置关系一致'],
  ['修订原因', '必填', '必填', '保存到审计和设计修订'],
  ['系统保护', '—', '—', '订单、公司、来源文件、审批、历史版本不可通过导入改写'],
]
source.format.font = { name: 'Arial', size: 10 }
sheet.getRange('T2:W2').format = {
  fill: '#D9EAF7', font: { name: 'Arial', size: 10, bold: true, color: '#17365D' },
  borders: { preset: 'outside', style: 'thin', color: '#9FBAD0' },
}
sheet.getRange('T3:W11').format.wrapText = true
sheet.getRange('T2:T11').format.columnWidth = 20
sheet.getRange('U2:V11').format.columnWidth = 12
sheet.getRange('W2:W11').format.columnWidth = 48

workbook.recalculate()
const inspection = await workbook.inspect({
  kind: 'table', range: '产品设计导入!A2:W11', include: 'values,formulas',
  tableMaxRows: 12, tableMaxCols: 23,
})
if (!inspection.ndjson.includes('产品设计导入模板')) {
  throw new Error('Template inspection failed')
}
const errors = await workbook.inspect({
  kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: { useRegex: true, maxResults: 100 },
})
if (/"address"/.test(errors.ndjson)) throw new Error(`Formula errors: ${errors.ndjson}`)

await fs.mkdir(path.dirname(outputPath), { recursive: true })
const preview = await workbook.render({ sheetName: '产品设计导入', range: 'A2:W11', scale: 1.2, format: 'png' })
await fs.writeFile(
  path.resolve('outputs/engineering-table-process-config-save-closure-20260919/产品设计导入模板预览.png'),
  new Uint8Array(await preview.arrayBuffer()),
)
const output = await SpreadsheetFile.exportXlsx(workbook)
await output.save(outputPath)
process.stdout.write(`${outputPath}\n`)
