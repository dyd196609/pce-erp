import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const VERSION='V1.14.2.8.18.13'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')
const sources={filter:read('src/meta/runtime/listFilterRuntime.js'),action:read('src/meta/runtime/listActionColumnRuntime.js'),
  pageRule:read('src/meta/runtime/listPageContainerRule.js'),table:read('src/meta/components/PceEnterpriseListTable.vue'),
  scroll:read('src/meta/components/BusinessTableScrollContainer.vue'),shell:read('src/meta/components/PceListPageShell.vue'),
  supplier:read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
  comparison:read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),
  price:read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')}
const tests=spawnSync(process.execPath,['--test','tests/acceptance/enterpriseUnifiedListRuntimeV1142813.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteSimpleRuntimeV11428121.test.mjs'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=spawnSync(process.execPath,[vite,'build','.'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
for(const run of [tests,build])if(run.status!==0)process.stderr.write(`${run.stdout||''}${run.stderr||''}`)
const scm=[sources.supplier,sources.comparison,sources.price]
const checks=[
  ['List Filter Runtime',tests.status===0&&['text','select','date','number'].every(type=>sources.filter.includes(`'${type}'`))&&sources.filter.includes('optionsSource')],
  ['Action Column Runtime',tests.status===0&&sources.action.includes("actionSource: 'Action Contract'")&&sources.table.includes('data-pce-action-source="Action Contract"')&&scm.every(source=>source.includes('action-contracts'))],
  ['Horizontal Scroll',sources.scroll.includes('overflow-x: auto')&&sources.scroll.includes('--pce-table-min-width')&&sources.table.includes('fixed="left"')&&sources.table.includes('fixed="right"')],
  ['Responsive Layout',sources.shell.includes('overflow-x: hidden')&&sources.shell.includes('min-width: 0')&&sources.pageRule.includes("overflowX: 'hidden'")],
  ['SCM Regression',tests.status===0&&scm.every(source=>source.includes('PceEnterpriseListTable')&&source.includes('optionsSource'))],
  ['Build',build.status===0],
]
console.log(`Version: ${VERSION}`)
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'PCE_LIST_RUNTIME_STANDARD_ISSUES_FOUND':'PCE_LIST_RUNTIME_STANDARD_READY')
if(failures.length)process.exitCode=1
