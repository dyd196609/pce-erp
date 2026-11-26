import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateBusinessNameRegistry, resolveBusinessName } from '../src/meta/governance/businessNameRegistry.js'
import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { validateScmNodePageGovernanceV11428103, listScmNodePageMappingsV11428103 } from '../src/meta/process/scmNodePageGovernanceV11428103.js'

const frontendRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const workspaceRoot=path.resolve(frontendRoot,'..')
const readWorkspace=relative=>fs.readFileSync(path.join(workspaceRoot,relative),'utf8')
const readFrontend=relative=>fs.readFileSync(path.join(frontendRoot,relative),'utf8')
const governanceFiles=['CODEX执行命令规范.md','PCE-ERP开发治理总规范.md','页面开发模板.md',
  'Approval审批治理规范.md','一页一验收规范.md','问题案例库.md','治理符合性检查矩阵.md']
const governanceLoaded=governanceFiles.every(name=>readWorkspace(`docs/governance/${name}`).trim().length>0)
const commandStandard=readWorkspace('docs/governance/CODEX执行命令规范.md')
const approvalStandard=readWorkspace('docs/governance/Approval审批治理规范.md')
const matrix=readWorkspace('docs/governance/治理符合性检查矩阵.md')
const cases=readWorkspace('docs/governance/问题案例库.md')
const nameReport=readWorkspace('docs/governance/业务名称一致性报告.md')
const router=readFrontend('src/router/index.js')
const codexCommand001=commandStandard.includes('CODEX-COMMAND-001')&&commandStandard.includes('失败阻断规范')
const nameGov001=validateBusinessNameRegistry().result==='PASS'&&matrix.includes('NAME-GOV-001')
  && nameReport.includes('BusinessNameRegistry')&&resolveBusinessName('quality-inspection').pageTitle==='来料检验'
  && resolveBusinessName('warehouse-receipt').pageTitle==='入库'
const nodeTest=spawnSync(process.execPath,['--test','tests/acceptance/enterpriseBusinessNameApprovalBindingV114281032.test.mjs'],
  {cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const approvalRuntime001=nodeTest.status===0&&approvalStandard.includes('APPROVAL-RUNTIME-001')
  && approvalStandard.includes('Approval Configuration → Approval Policy → Approval Instance → Approval Task → Approval Result → Business State Writeback')
const casePass=id=>cases.includes(id)&&cases.includes('V1.14.2.8.18.10.3.2')
const mappings=listScmNodePageMappingsV11428103()
const mappingValidation=validateScmNodePageGovernanceV11428103()
const approvalMapping=mappings.find(item=>item.nodeCode==='purchase-approval')
const pageIdentity=mappings.every(mapping=>{const identity=resolveScmPageIdentity(mapping.pageContract.route)
  return identity&&['pageCode','pageName','route','moduleCode','businessObject'].every(key=>identity[key]===mapping.pageContract[key])})
  && resolveScmPageIdentity('/admin/approval-flow-config')?.businessObject==='ApprovalConfiguration'
  && resolveScmPageIdentity('/scm/purchase-approvals')?.businessObject==='PurchaseRequestApproval'
const nodePage=mappingValidation.result==='PASS'&&approvalMapping?.pageContract.route==='/scm/purchase-approvals'
  && approvalMapping?.pageContract.pageCode==='purchase-approval'&&approvalMapping?.pageContract.route!=='/admin/approval-flow-config'
  && router.includes("wrapPceListPage('purchase-approval'")
const acceptanceFiles=[
  ['PAGE-PURCHASE-APPROVAL.md','/scm/purchase-approvals'],['PAGE-PURCHASE-REQUEST.md','/scm/purchase-request'],
  ['PAGE-INQUIRY-PREPARATION.md','/scm/inquiry-preparations'],['PAGE-PURCHASE-INQUIRY.md','/scm/purchase-inquiry'],
  ['PAGE-SUPPLIER-QUOTE.md','/scm/supplier-quotes'],['QUOTE-COMPARISON-PAGE.md','/scm/quote-comparisons'],
  ['PAGE-SUPPLIER-RECOMMENDATION.md','/scm/supplier-recommendations'],['PAGE-PURCHASE-ORDER-GATE.md','/scm/purchase-order-gate'],
]
const process009=acceptanceFiles.every(([file,route])=>{const source=readWorkspace(`docs/acceptance/${file}`)
  return source.includes(route)&&source.includes('页面名称')&&(source.includes('规范编号')||source.includes('规则编号'))
    &&source.includes('检查项')&&source.includes('证据')&&source.includes('结果')&&source.includes('PASS')})
const regressionRun=spawnSync(process.execPath,['scripts/verifyScmPageGovernanceComplianceV114281031.mjs'],
  {cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const regression=regressionRun.status===0&&regressionRun.stdout.includes('SCM_PAGE_GOVERNANCE_COMPLIANCE_READY')
const vite=path.join(frontendRoot,'node_modules','vite','bin','vite.js')
const buildRun=spawnSync(process.execPath,[vite,'build','.'],{cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
for(const result of [nodeTest,regressionRun,buildRun])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)
const checks=[['Governance Files Loaded',governanceLoaded],['CODEX-COMMAND-001',codexCommand001],
  ['NAME-GOV-001',nameGov001],['APPROVAL-RUNTIME-001',approvalRuntime001],
  ['CASE-SCM-023',casePass('CASE-SCM-023')],['CASE-SCM-024',casePass('CASE-SCM-024')],
  ['CASE-SCM-025',casePass('CASE-SCM-025')],['CASE-SCM-026',casePass('CASE-SCM-026')],
  ['PAGE-IDENTITY',pageIdentity],['NODE-PAGE',nodePage],['PROCESS-009',process009],
  ['Regression',regression],['Build',buildRun.status===0]]
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}: 证据缺失或验证失败，影响业务名称或审批运行治理，请修复后重跑。`))}
console.log(failures.length?'PCE_BUSINESS_NAME_APPROVAL_GOVERNANCE_ISSUES_FOUND':'PCE_BUSINESS_NAME_APPROVAL_GOVERNANCE_READY')
if(failures.length)process.exitCode=1
