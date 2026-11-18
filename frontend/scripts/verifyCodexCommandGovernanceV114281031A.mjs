import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const workspaceRoot=path.resolve(frontendRoot,'..')
const governanceRoot=path.join(workspaceRoot,'docs','governance')
const readGovernance=name=>fs.readFileSync(path.join(governanceRoot,name),'utf8')

const governanceFiles=['PCE-ERP开发治理总规范.md','节点开发模板.md','页面开发模板.md',
  '一页一验收规范.md','问题案例库.md','治理符合性检查矩阵.md']
const governanceFilesLoaded=governanceFiles.every(name=>{
  const file=path.join(governanceRoot,name)
  return fs.existsSync(file)&&fs.readFileSync(file,'utf8').trim().length>0
})

const standardFile=path.join(governanceRoot,'CODEX执行命令规范.md')
const standardExists=fs.existsSync(standardFile)&&fs.readFileSync(standardFile,'utf8').trim().length>0
const standard=standardExists?fs.readFileSync(standardFile,'utf8'):''
const requiredSections=['第一章：目的','第二章：任务身份规范','第三章：治理资产加载规范',
  '第四章：治理规则映射规范','第五章：历史案例绑定规范','第六章：当前系统状态规范',
  '第七章：执行范围规范','第八章：实施步骤规范','第九章：验收矩阵规范',
  '第十章：最终报告规范','第十一章：失败阻断规范','第十二章：CODEX 任务模板']
const requiredTaskTypes=['新功能开发','页面开发','节点开发','问题修复','治理升级','自动验收','回归测试']
const requiredSteps=['Step 1：读取治理文件','Step 2：扫描现状','Step 3：输出差异','Step 4：实施修改',
  'Step 5：自动验收','Step 6：更新案例库']
const requiredReportFields=['Governance Files Loaded:','Governance Mapping:','Implementation Completed:',
  'Acceptance:','Issues:','Final Status:']
const requiredSectionsPass=[...requiredSections,...requiredTaskTypes,...requiredSteps,...requiredReportFields,
  '规范编号','规范名称','检查内容','验收方式','CASE 编号','READY','ISSUES_FOUND']
  .every(token=>standard.includes(token))

const general=readGovernance('PCE-ERP开发治理总规范.md')
const matrix=readGovernance('治理符合性检查矩阵.md')
const caseLibrary=readGovernance('问题案例库.md')
const governanceIntegration=general.includes('CODEX执行命令规范.md')
  && general.includes('所有后续 CODEX')&&general.includes('规范 → 检查项 → 验收证据 → 结果')
  && matrix.includes('CODEX-COMMAND-001')&&matrix.includes('verifyCodexCommandGovernanceV114281031A.mjs')
const caseLibraryUpdated=caseLibrary.includes('CASE-SCM-027')
  && caseLibrary.includes('CODEX 执行命令缺少统一规范管理')
  && caseLibrary.includes('PROCESS-010')&&caseLibrary.includes('CODEX-COMMAND-001')

const regressionRun=spawnSync(process.execPath,['scripts/verifyScmPageGovernanceComplianceV114281031.mjs'],{
  cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const regression=regressionRun.status===0
  && regressionRun.stdout.includes('SCM_PAGE_GOVERNANCE_COMPLIANCE_READY')
const vite=path.join(frontendRoot,'node_modules','vite','bin','vite.js')
const buildRun=spawnSync(process.execPath,[vite,'build','.'],{
  cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
if(regressionRun.status!==0)process.stderr.write(`${regressionRun.stdout||''}${regressionRun.stderr||''}`)
if(buildRun.status!==0)process.stderr.write(`${buildRun.stdout||''}${buildRun.stderr||''}`)

const checks=[
  ['Governance Files Loaded',governanceFilesLoaded],
  ['CODEX Command Standard Exists',standardExists],
  ['Required Sections',requiredSectionsPass],
  ['CODEX Command Standard',standardExists&&requiredSectionsPass],
  ['Governance Integration',governanceIntegration],
  ['Case Library Updated',caseLibraryUpdated],
  ['CASE-SCM-027',caseLibraryUpdated],
  ['Regression',regression],
  ['Build',buildRun.status===0],
]
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){
  console.log('Issues:')
  failures.forEach((label,index)=>console.log(`${index+1}. ${label}: 关键治理证据缺失或验证失败；影响命令治理签发；请补齐后重跑本脚本。`))
}
console.log(failures.length?'PCE_CODEX_COMMAND_STANDARD_ISSUES_FOUND':'PCE_CODEX_COMMAND_STANDARD_READY')
if(failures.length)process.exitCode=1
