import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const VERSION='V1.14.2.8.18.13.1'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')
const source={container:read('src/meta/runtime/listContainerRuntime.js'),filter:read('src/meta/runtime/unifiedFilterSchema.js'),
  action:read('src/meta/runtime/listActionColumnRuntime.js'),table:read('src/meta/components/PceEnterpriseListTable.vue'),
  scroll:read('src/meta/components/BusinessTableScrollContainer.vue'),shell:read('src/meta/components/PceListPageShell.vue'),
  inquiry:read('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),supplier:read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
  comparison:read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),price:read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue'),
  contracts:read('src/meta/process/scm/scmUnifiedListActionContractsV1142813.js')}
const tests=spawnSync(process.execPath,['--test','tests/acceptance/enterpriseListRuntimeGovernanceV11428131.test.mjs',
  'tests/acceptance/enterpriseUnifiedListRuntimeV1142813.test.mjs','tests/acceptance/enterpriseSupplierQuoteSimpleRuntimeV11428121.test.mjs'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=spawnSync(process.execPath,[vite,'build','.'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const legacy=spawnSync(process.execPath,['scripts/verifyEnterpriseListPage.mjs'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
for(const run of [tests,build,legacy])if(run.status!==0)process.stderr.write(`${run.stdout||''}${run.stderr||''}`)
const governed=page=>page.includes('filterFields')&&page.includes('optionsProvider')&&page.includes('createUnifiedFilterSchema')
  &&page.includes('action-contracts')&&page.includes('action-state-field')&&!page.includes('<template #actions')
const checks=[
  ['Responsive Layout',tests.status===0&&source.container.includes("overflowX: 'hidden'")&&source.shell.includes('min-width: 0')],
  ['Table Overflow',source.container.includes("overflowX: 'auto'")&&source.scroll.includes('overflow-x: auto')&&source.scroll.includes('--pce-table-min-width')],
  ['Filter Runtime',tests.status===0&&['text','select','date','number-range'].every(type=>source.filter.includes(`'${type}'`))],
  ['Action Column',tests.status===0&&source.action.includes("actionSource: 'Action Contract'")&&source.table.includes('data-pce-default-action-column="true"')],
  ['SCM Purchase Inquiry',governed(source.inquiry)&&['inquiryNo','sourceRequestNo','buyerName','businessStatusCode','processStatusCode'].every(field=>source.inquiry.includes(field))],
  ['SCM Supplier Quote',governed(source.supplier)&&['inquiryNo','supplierCode','materialCode','quoted'].every(field=>source.supplier.includes(field))],
  ['SCM Quote Comparison',governed(source.comparison)&&['sourceInquiryId','materialCode','supplierCodes','comparisonStatus'].every(field=>source.comparison.includes(field))],
  ['SCM Price Approval',governed(source.price)&&source.contracts.includes("actionCode: 'VIEW_PRICE_APPROVAL'")&&source.contracts.includes("actionCode: 'OPEN_SUPPLIER_RECOMMENDATION'")&&!source.contracts.includes("actionCode: 'CREATE_PURCHASE_ORDER'")],
  ['Build',build.status===0],['Regression',tests.status===0&&legacy.status===0&&legacy.stdout.includes('"fail": 0')],
]
console.log(`Version: ${VERSION}`)
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'PCE_LIST_RUNTIME_GOVERNANCE_ISSUES_FOUND':'PCE_LIST_RUNTIME_GOVERNANCE_READY')
if(failures.length)process.exitCode=1
