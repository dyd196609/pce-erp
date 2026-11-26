import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(repositoryRoot, 'docs', 'governance')
const read = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')

const governanceFiles = [
  'PCE-ERP开发治理总规范.md',
  '页面开发规范.md',
  '页面验收管理规范.md',
  '一页一验收规范.md',
  '金丝雀测试管理规范.md',
  '页面归档管理规范.md',
  '页面操作指引编写规范.md',
]
const governanceExists = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.statSync(file).size > 0
})

const standardName = 'PCE-ERP统一页面验收标准V1.1.md'
const standardExists = fs.existsSync(path.join(governanceRoot, standardName))
const standard = standardExists ? read(standardName) : ''
const requiredParts = ['第一部分：页面基础规范', '第二部分：企业列表标准', '第三部分：表单标准',
  '第四部分：业务对象标准', '第五部分：基础数据关联标准', '第六部分：智能联动标准',
  '第七部分：业务流程标准', '第八部分：权限与边界保护', '第九部分：金丝雀测试标准',
  '第十部分：运行模式标准', '第十一部分：自动验收标准', '第十二部分：人工验收标准',
  '第十三部分：验收归档标准']
const unifiedTemplate = standardExists && requiredParts.every(part => standard.includes(part))

const guideIds = Array.from({ length: 10 }, (_, index) =>
  `GUIDE-${String(index + 1).padStart(3, '0')}`)
const guideFiles = ['PCE-ERP统一页面验收标准V1.1.md', '页面操作指引编写规范.md',
  '一页一验收规范.md']
const guideModule = guideFiles.every(name => guideIds.every(id => read(name).includes(id)))
  && standard.includes('页面操作指引用于说明') && standard.includes('流程导航用于说明')

const statusVocabulary = ['PASS', 'FAIL', 'N/A', 'UNKNOWN']
const statusRule = statusVocabulary.every(status => standard.includes(status))
  && read('页面验收管理规范.md').includes('N/A')
  && read('页面验收管理规范.md').includes('UNKNOWN')
  && read('一页一验收规范.md').includes('N/A保留')

const archiveRule = read('页面归档管理规范.md')
const archiveStandard = ['docs/governance', 'frontend/test-results', 'CheckpointArchive']
  .every(value => archiveRule.includes(value) && standard.includes(value))
  && fs.existsSync(path.join(repositoryRoot, 'CheckpointArchive', 'README.md'))

const scmTemplateFile = path.join(governanceRoot, 'SCM页面验收模板.md')
const matrixFile = path.join(governanceRoot, 'enterprise_page_acceptance_matrix.json')
let matrix = null
try { matrix = JSON.parse(fs.readFileSync(matrixFile, 'utf8')) } catch { matrix = null }
const scmTemplate = fs.existsSync(scmTemplateFile)
  && ['PR-*', 'PI-*', 'PO-*', 'SR-*'].every(value => read('SCM页面验收模板.md').includes(value))
  && matrix?.matrixCode === 'enterprise_page_acceptance_matrix'
  && matrix?.commonItemsRequired === true
  && matrix?.moduleExtensions?.SCM?.template === 'SCM页面验收模板.md'

const governanceLoadUpdate = read('CODEX执行命令规范.md')
const governanceLoadRule = ['页面开发规范.md', '页面验收管理规范.md', '一页一验收规范.md',
  '对应模块验收模板'].every(value => governanceLoadUpdate.includes(value))

const checks = [
  ['Governance Files', governanceExists && governanceLoadRule],
  ['Unified Acceptance Template', unifiedTemplate],
  ['GUIDE Module', guideModule],
  ['PASS/FAIL/N/A/UNKNOWN Rule', statusRule],
  ['Archive Governance', archiveStandard],
  ['SCM Page Template', scmTemplate],
]

const passed = checks.every(([, result]) => result)
console.log('Version: V1.14.2.8.4.20.8')
for (const [name, result] of checks) console.log(`${name} ${result ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'PAGE_ACCEPTANCE_FRAMEWORK_V11_READY'
  : 'PAGE_ACCEPTANCE_FRAMEWORK_V11_ISSUES_FOUND')
if (!passed) process.exitCode = 1
