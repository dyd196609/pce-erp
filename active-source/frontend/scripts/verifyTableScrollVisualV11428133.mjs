import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const repo=path.resolve(root,'..')
const run=args=>spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const tests=run(['--test','tests/acceptance/enterpriseTableScrollVisualStructureV11428133.test.mjs',
  'tests/acceptance/enterpriseTableScrollRuntimeV11428132.test.mjs'])
const regression=run(['scripts/verifyListRuntimeGovernanceV11428131.mjs'])
const build=run([path.join(root,'node_modules','vite','bin','vite.js'),'build','.'])
for(const result of [tests,regression,build])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)
const evidencePath=path.join(repo,'docs/acceptance/PCE-TABLE-SCROLL-VISUAL-V11428133.json')
let evidence=null
try{evidence=JSON.parse(fs.readFileSync(evidencePath,'utf8'))}catch{}
const requiredPages=['purchase-inquiry','supplier-quote','quote-comparison','price-approval']
const pagePass=page=>{const fact=evidence?.pages?.[page];return Boolean(fact?.containerExists
  &&fact.scrollWidth>fact.clientWidth&&fact.elementVisible&&fact.bodyScrollWidth<=fact.viewportWidth
  &&fact.scrollbarHeight>0&&fact.stickyActionInsideContainer)}
const visualPass=requiredPages.every(pagePass)
const checks=[
  ['DOM Structure',tests.status===0],
  ['Scroll Container',tests.status===0],
  ['SCM Regression',regression.status===0&&regression.stdout.includes('PCE_LIST_RUNTIME_GOVERNANCE_READY')],
  ['Build',build.status===0],
  ['Browser Visual Evidence',visualPass],
]
console.log('Version: V1.14.2.8.18.13.3')
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
for(const page of requiredPages)console.log(`${page} Visual ${pagePass(page)?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'PCE_TABLE_SCROLL_VISUAL_ISSUES_FOUND':'PCE_TABLE_SCROLL_VISUAL_READY')
if(failures.length)process.exitCode=1
