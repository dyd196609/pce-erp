import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')
const run=args=>spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const tests=run(['--test','tests/acceptance/enterpriseListFilterPriceReferenceV1142814.test.mjs',
  'tests/acceptance/enterpriseListRuntimeGovernanceV11428131.test.mjs'])
const regression=run(['scripts/verifyListRuntimeGovernanceV11428131.mjs'])
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=run([vite,'build','.'])
for(const result of [tests,regression,build])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)
const sources={filter:read('src/meta/runtime/unifiedFilterSchema.js'),remote:read('src/meta/runtime/remoteSelectOptionsProvider.js'),
  batch:read('src/meta/runtime/batchFilterRuntime.js'),container:read('src/meta/components/BusinessTableScrollContainer.vue'),
  table:read('src/meta/components/PceEnterpriseListTable.vue'),price:read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue'),
  reference:read('src/meta/process/scm/priceApproval/priceReferenceContext.js')}
const checks=[
  ['List Scroll',tests.status===0&&sources.container.includes('overflow-x: auto')&&sources.container.includes('is-horizontal')],
  ['Advanced Filter',['text','select','remote-select','date','number-range'].every(type=>sources.filter.includes(`'${type}'`))],
  ['Remote Select',sources.remote.includes('searchOptions')&&sources.price.includes("type:'remote-select'")],
  ['Batch Filter',sources.batch.includes('createBatchFilterRuntime')&&sources.table.includes('按已选数据筛选')],
  ['Historical Price Reference',['historicalPurchasePrice','lastPurchaseDate','currentQuote','priceChangeRatio'].every(field=>sources.reference.includes(field))&&sources.reference.includes('automaticQuoteRejection: false')],
  ['SCM Regression',regression.status===0&&regression.stdout.includes('PCE_LIST_RUNTIME_GOVERNANCE_READY')],
  ['Build',build.status===0],
]
console.log('Version: V1.14.2.8.18.14')
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'SCM_PRICE_APPROVAL_ENHANCEMENT_ISSUES_FOUND':'SCM_PRICE_APPROVAL_ENHANCEMENT_READY')
if(failures.length)process.exitCode=1
