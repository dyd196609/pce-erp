import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { resolveScmPageIdentity } from '../src/meta/schema/scm/scmPageIdentityRegistry.js'
import { resolveScmStandardPageContract } from '../src/meta/schema/scm/scmStandardPageContract.js'
import { listScmNodePageMappingsV11428103, validateScmNodePageGovernanceV11428103 } from '../src/meta/process/scmNodePageGovernanceV11428103.js'
import { evaluateScmPageGovernanceCompliance, SCM_NODE_SEMANTIC_MAPPINGS,
  SCM_PAGE_GOVERNANCE_TARGETS } from '../src/meta/process/scmPageGovernanceComplianceV114281031.js'

const frontendRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const workspaceRoot=path.resolve(frontendRoot,'..')
const readFrontend=relative=>fs.readFileSync(path.join(frontendRoot,relative),'utf8')
const readWorkspace=relative=>fs.readFileSync(path.join(workspaceRoot,relative),'utf8')
const governanceFiles=['PCE-ERP开发治理总规范.md','节点开发模板.md','页面开发模板.md','一页一验收规范.md','问题案例库.md','NODE-PAGE-001节点页面唯一映射规范.md']
const governanceLoaded=governanceFiles.every(file=>readWorkspace(`docs/governance/${file}`).trim().length>0)
const matrix=readWorkspace('docs/governance/治理符合性检查矩阵.md')
const caseLibrary=readWorkspace('docs/governance/问题案例库.md')
const routerSource=readFrontend('src/router/index.js')
const shellSource=readFrontend('src/meta/components/PceListPageShell.vue')
const standardContractSource=readFrontend('src/meta/schema/scm/scmStandardPageContract.js')
const mappings=listScmNodePageMappingsV11428103()
const mappingValidation=validateScmNodePageGovernanceV11428103()

const pageSources={
  'purchase-request':readFrontend('src/meta/pages/ScmPurchaseRequestPage.vue'),
  'purchase-approval':readFrontend('src/meta/pages/PurchaseApprovalExecutionPage.vue'),
  'inquiry-preparation':readFrontend('src/meta/pages/ScmInquiryPreparationPage.vue'),
  'purchase-inquiry':readFrontend('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
  'supplier-quote-workbench':readFrontend('src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue')+readFrontend('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
  'quote-comparison-workbench':readFrontend('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),
  'price-approval':readFrontend('src/meta/pages/ScmPage.vue')+readFrontend('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue'),
  'supplier-recommendation':readFrontend('src/meta/pages/ScmSupplierRecommendationPage.vue'),
  'purchase-order-gate':readFrontend('src/meta/pages/ScmPurchaseOrderGatePage.vue'),
}
const acceptanceFiles={
  'purchase-request':'PAGE-PURCHASE-REQUEST.md','purchase-approval':'PAGE-PURCHASE-APPROVAL.md',
  'inquiry-preparation':'PAGE-INQUIRY-PREPARATION.md','purchase-inquiry':'PAGE-PURCHASE-INQUIRY.md',
  'supplier-quote-workbench':'PAGE-SUPPLIER-QUOTE.md','quote-comparison-workbench':'QUOTE-COMPARISON-PAGE.md',
  'price-approval':'PAGE-PRICE-APPROVAL.md','supplier-recommendation':'PAGE-SUPPLIER-RECOMMENDATION.md',
  'purchase-order-gate':'PAGE-PURCHASE-ORDER-GATE.md',
}
function routeHasPage(pageCode){
  if(pageCode==='price-approval')return routerSource.includes("path: 'scm/price-approval'")&&pageSources[pageCode].includes('PceListPageShell')
  return routerSource.includes(`wrapPceListPage('${pageCode}'`)
}
const evidenceByPage=Object.fromEntries(SCM_PAGE_GOVERNANCE_TARGETS.map(page=>{
  const source=pageSources[page.pageCode]
  const identity=resolveScmPageIdentity(page.route)
  const contract=resolveScmStandardPageContract(page.pageCode)
  const mapping=mappings.find(item=>item.pageContract.pageCode===page.pageCode)
  const acceptance=readWorkspace(`docs/acceptance/${acceptanceFiles[page.pageCode]}`)
  const identityOk=Boolean(identity&&mapping&&['pageCode','pageName','route','moduleCode','businessObject']
    .every(field=>identity[field]===mapping.pageContract[field]))
  const pageTemplate=Boolean(contract&&routeHasPage(page.pageCode)
    && ['当前版本','页面名称','业务模块','业务对象','上一步','当前页面','下一步'].every(token=>shellSource.includes(token)))
  const businessRegions=(source.includes('data-acceptance-region=')||source.includes('data-acceptance-id='))
    && shellSource.includes('finance-operation-summary')&&shellSource.includes('module-main-process')
    && shellSource.includes('business-process-navigation')
  const listTemplate=!page.listPage||(source.includes('PceEnterpriseListTable')
    && source.includes('createPceEnterpriseListContract')&&source.includes('filterType')
    && source.includes('exportCurrent')&&source.includes('clearFilters'))
  const actionTemplate=(source.includes('data-process-action')||source.includes('@click=')||source.includes('@change='))
    && (source.includes('router.push')||source.includes('save(')||source.includes('runAction')
      ||source.includes('activatePurchaseInquiry')||source.includes('execute'))
  const stateTemplate=page.pageCode==='purchase-approval'
    ? source.includes('statusLabel')&&source.includes('currentTask')
    : (source.includes('PceBusinessStatus')||source.includes('statusLabel')||source.includes('StatusLabel'))
  const acceptanceRecord=acceptance.includes(page.route)
    && ['页面名称','规则编号','检查项','页面证据','结果','人工验收结果：PASS'].every(token=>acceptance.includes(token))
  return [page.pageCode,{identity:identityOk,pageTemplate,businessRegions,listTemplate,actionTemplate,stateTemplate,
    uniqueMapping:mappingValidation.nodePage001,routeMapping:Boolean(mappingValidation.process011&&routeHasPage(page.pageCode)),acceptanceRecord}]
}))

const compliance=evaluateScmPageGovernanceCompliance(evidenceByPage)
const brokenEvidence=structuredClone(evidenceByPage)
brokenEvidence['supplier-quote-workbench'].listTemplate=false
const failureBlocking=evaluateScmPageGovernanceCompliance(brokenEvidence).result==='FAIL'
const matrixPass=['治理规则编号','检查项','对应页面','验证方式','结果','失败阻断证据'].every(token=>matrix.includes(token))&&failureBlocking
const semantic=SCM_NODE_SEMANTIC_MAPPINGS['purchase-approval']
const semanticPass=semantic.businessObject==='PurchaseRequestApproval'
  && semantic.forbiddenNodeCodes.includes('purchase-order-approval')
  && semantic.forbiddenPageCodes.includes('approval-flow-config')
  && resolveScmStandardPageContract('purchase-approval')?.businessObject==='PurchaseRequestApproval'
  && mappings.find(item=>item.nodeCode==='purchase-order-creation-gate')?.pageContract.route==='/scm/purchase-order-gate'
const casePass=caseLibrary.includes('CASE-SCM-023')&&caseLibrary.includes('治理文件已加载但没有强制门禁')
const allPageChecks=code=>compliance.pageResults.find(page=>page.acceptanceCode===code)?.passed===true
const pageIdentity=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='PAGE-IDENTITY')?.passed)
const pageTemplate=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='PAGE-TEMPLATE')?.passed)
const listTemplate=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='LIST-TEMPLATE')?.passed)
const actionTemplate=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='ACTION-TEMPLATE')?.passed)
const stateTemplate=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='STATE-TEMPLATE')?.passed)
const process009=compliance.pageResults.every(page=>page.checks.find(check=>check.ruleCode==='PROCESS-009')?.passed)

const tests=spawnSync(process.execPath,['--test','tests/acceptance/enterpriseScmPageGovernanceComplianceV114281031.test.mjs',
  'tests/acceptance/enterpriseScmNodePageGovernanceV11428103.test.mjs'],{cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const previous=spawnSync(process.execPath,['scripts/verifyScmNodePageGovernanceV11428103.mjs'],{cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const regression=tests.status===0&&previous.status===0&&previous.stdout.includes('SCM_NODE_PAGE_GOVERNANCE_READY')
const vite=path.join(frontendRoot,'node_modules','vite','bin','vite.js')
const build=spawnSync(process.execPath,[vite,'build','.'],{cwd:frontendRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']})
for(const result of [tests,previous,build])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)

const checks=[
  ['Governance Files Loaded',governanceLoaded],['Governance Compliance Matrix',matrixPass],['CASE-SCM-023',casePass],
  ['NODE-PAGE-001',mappingValidation.nodePage001],['PROCESS-011',mappingValidation.process011&&semanticPass],
  ['PAGE-IDENTITY',pageIdentity],['PAGE-TEMPLATE',pageTemplate],['LIST-TEMPLATE',listTemplate],
  ['ACTION-TEMPLATE',actionTemplate],['STATE-TEMPLATE',stateTemplate],
  ...SCM_PAGE_GOVERNANCE_TARGETS.map(page=>[page.acceptanceCode,allPageChecks(page.acceptanceCode)]),
  ['PROCESS-009',process009],['Regression',regression],['Build',build.status===0],
]
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('未通过项清单：');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'SCM_PAGE_GOVERNANCE_COMPLIANCE_ISSUES_FOUND':'SCM_PAGE_GOVERNANCE_COMPLIANCE_READY')
if(failures.length)process.exitCode=1
