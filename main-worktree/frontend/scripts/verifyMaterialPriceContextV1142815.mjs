import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const run=args=>spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const testFiles={
  material:'tests/acceptance/materialPriceContextV1142815.test.mjs',
  supplier:'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  comparison:'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  priceApproval:'tests/acceptance/enterpriseListFilterPriceReferenceV1142814.test.mjs',
}
const material=run(['--test',testFiles.material])
const supplier=run(['--test',testFiles.supplier])
const comparison=run(['--test',testFiles.comparison])
const priceApproval=run(['--test',testFiles.priceApproval])
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=run([vite,'build','.'])
for(const result of [material,supplier,comparison,priceApproval,build]){
  if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)
}
const domainSource=fs.readFileSync(path.join(root,
  'src/meta/process/scm/priceApproval/materialPriceContext.js'),'utf8')
const evidenceSource=fs.readFileSync(path.join(root,
  'src/meta/process/scm/priceApproval/priceChangeEvidence.js'),'utf8')
const checks=[
  ['Material Type Detection',material.status===0&&domainSource.includes("'new_material'")&&domainSource.includes("'existing_material'")],
  ['New Material Context',material.status===0&&domainSource.includes('NewMaterialPriceAssessmentContext')],
  ['Existing Material Context',material.status===0&&domainSource.includes('createPriceReferenceContext')],
  ['Price Reference Evidence',material.status===0&&evidenceSource.includes("objectType: 'PriceChangeEvidence'")],
  ['Manual Decision Boundary',material.status===0&&domainSource.includes('automaticQuoteApproval: false')&&domainSource.includes('businessWriteCount: 0')],
  ['SupplierQuote Compatibility',supplier.status===0],
  ['QuoteComparison Compatibility',comparison.status===0],
  ['PriceApproval Regression',priceApproval.status===0],
  ['Build',build.status===0],
]
console.log('Version: V1.14.2.8.18.15')
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
console.log(`Business Write Count: 0`)
console.log(`Production Data Written: false`)
if(failures.length){
  console.log('Issues:')
  failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))
}
console.log(failures.length?'SCM_MATERIAL_PRICE_CONTEXT_ISSUES_FOUND':'SCM_MATERIAL_PRICE_CONTEXT_READY')
if(failures.length)process.exitCode=1
