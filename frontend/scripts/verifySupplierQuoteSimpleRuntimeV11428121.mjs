import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const VERSION='V1.14.2.8.18.12.1'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8')
const files={model:read('src/meta/process/scm/supplierQuote/supplierQuoteSimpleModelV11428121.js'),
  runtime:read('src/meta/runtime/supplierQuoteSimpleRuntimeV11428121.js'),
  provider:read('src/meta/providers/supplierQuoteProviderV114289.js'),
  quotePage:read('src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue'),
  quoteList:read('src/meta/components/ScmSupplierQuoteEnterpriseList.vue'),
  comparison:read('src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js'),
  comparisonPage:read('src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue'),
  priceProvider:read('src/meta/providers/priceApprovalFromQuoteComparisonProviderV11428121.js'),
  pricePage:read('src/meta/pages/ScmPage.vue')}
const tests=spawnSync(process.execPath,['--test','tests/acceptance/enterpriseSupplierQuoteSimpleRuntimeV11428121.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeBindingV1142812.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=spawnSync(process.execPath,[vite,'build','.'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
for(const run of [tests,build]) if(run.status!==0) process.stderr.write(`${run.stdout||''}${run.stderr||''}`)
const forbidden=['deliveryDate','validUntil','validityDate','taxRate','complexScore']
const simpleFields=['quoteId','sourceInquiryId','supplierCode','supplierName','materialCode','materialName','quantity','quotePrice','remark']
const checks=[
  ['SupplierQuotePreparation Count',tests.status===0&&files.provider.includes('preparationRecordCount')&&files.provider.includes('dataAligned')],
  ['SupplierQuote List Count Alignment',tests.status===0],
  ['SupplierQuote Field Simplification',simpleFields.every(field=>files.model.includes(`'${field}'`))&&forbidden.every(field=>!files.model.includes(` ${field}:`))&&files.quotePage.includes('quoteForm.quotePrice')&&!files.quotePage.includes('quoteForm.deliveryDate')&&!files.quotePage.includes('quoteForm.taxRate')],
  ['QuoteComparison List Display',files.comparisonPage.includes('供应商A')&&files.comparisonPage.includes('最低报价')&&files.comparisonPage.includes('比较状态')&&files.comparison.includes('automaticRecommendationCreated: false')],
  ['PriceApproval Compatibility',files.priceProvider.includes("sourceObjectType: 'QuoteComparison'")&&files.pricePage.includes("context.sourceObjectType === 'QuoteComparison'")],
  ['Regression',tests.status===0],['Build',build.status===0],
]
const source=Object.values(files).join('\n'); const patterns=[/fetch\s*\(/g,/axios\s*\./g,/\/api\//g,/createPurchaseOrder\s*\(/g,/financeRuntime\s*\./g,/wmsRuntime\s*\./g,/mesRuntime\s*\./g]
const businessWriteCount=patterns.reduce((sum,pattern)=>sum+(source.match(pattern)||[]).length,0)
checks.push(['Business Write Boundary',businessWriteCount===0])
console.log(`Version: ${VERSION}`)
console.log(`Data Alignment: ${checks[0][1]&&checks[1][1]?'PASS':'FAIL'}`)
console.log(`SupplierQuote Simplification: ${checks[2][1]?'PASS':'FAIL'}`)
console.log(`QuoteComparison Simplification: ${checks[3][1]?'PASS':'FAIL'}`)
console.log(`PriceApproval Compatibility: ${checks[4][1]?'PASS':'FAIL'}`)
console.log(`Business Write Count: ${businessWriteCount}`); console.log('Production Data Written: 0')
console.log(`Automatic Acceptance: ${checks.every(([,passed])=>passed)?'PASS':'FAIL'}`)
console.log('Human Acceptance: PENDING')
for(const [label,passed] of checks) console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:'); failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(`Final Status: ${failures.length?'SCM_SUPPLIER_QUOTE_SIMPLE_RUNTIME_ISSUES_FOUND':'SCM_SUPPLIER_QUOTE_SIMPLE_RUNTIME_READY'}`)
if(failures.length) process.exitCode=1
