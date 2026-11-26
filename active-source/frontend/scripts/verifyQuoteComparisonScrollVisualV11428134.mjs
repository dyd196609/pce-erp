import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const repo=path.resolve(root,'..')
const read=relative=>fs.readFileSync(path.join(repo,relative),'utf8')
const run=args=>spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})

const governanceFiles=['CODEX执行命令规范.md','PCE-ERP开发治理总规范.md','页面开发模板.md',
  '一页一验收规范.md','统一列表运行层规范.md','治理符合性检查矩阵.md','问题案例库.md']
const governanceLoaded=governanceFiles.every(file=>fs.existsSync(path.join(repo,'docs/governance',file)))
  &&read('docs/governance/CODEX执行命令规范.md').includes('人工验收反向校验机制')

const tests=run(['--test','tests/acceptance/enterpriseQuoteComparisonScrollVisualV11428134.test.mjs',
  'tests/acceptance/enterpriseTableScrollRuntimeV11428132.test.mjs',
  'tests/acceptance/enterpriseTableScrollVisualStructureV11428133.test.mjs'])
const regression=run(['scripts/verifyListRuntimeGovernanceV11428131.mjs'])
const build=run([path.join(root,'node_modules','vite','bin','vite.js'),'build','.'])
for(const result of [tests,regression,build])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)

const evidencePath=path.join(repo,'docs/acceptance/PCE-QUOTE-COMPARISON-SCROLL-V11428134.json')
let evidence=null
try{evidence=JSON.parse(fs.readFileSync(evidencePath,'utf8'))}catch{}
const requiredPages=['purchase-inquiry','supplier-quote','quote-comparison','price-approval']
const pageFact=page=>evidence?.pages?.[page]
const visibleScroll=page=>{const fact=pageFact(page);return Boolean(fact?.containerExists
  &&fact.scrollWidth>fact.clientWidth&&fact.elementVisible&&fact.scrollbarHeight>0
  &&fact.stickyActionInsideContainer)}
const noPageOverflow=page=>{const fact=pageFact(page);return Boolean(fact?.viewportWidth>0
  &&fact.bodyScrollWidth<=fact.viewportWidth)}
const quoteFact=pageFact('quote-comparison')
const dynamicWidthPass=tests.status===0&&Boolean(!evidence||quoteFact?.dynamicColumnCount>=6)

const checks=[
  ['Governance Files Loaded',governanceLoaded],
  ['QuoteComparison Component Chain',tests.status===0],
  ['Unified Table Runtime',tests.status===0],
  ['Scroll Container',tests.status===0],
  ['Visible Horizontal Scroll',requiredPages.every(visibleScroll)],
  ['No Page Overflow',requiredPages.every(noPageOverflow)],
  ['Dynamic Column Width',dynamicWidthPass],
  ['SCM Regression',regression.status===0&&regression.stdout.includes('PCE_LIST_RUNTIME_GOVERNANCE_READY')],
  ['Build',build.status===0],
]

console.log('Version: V1.14.2.8.18.13.4')
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
for(const page of requiredPages)console.log(`${page} Browser Geometry ${visibleScroll(page)&&noPageOverflow(page)?'PASS':'FAIL'}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
console.log(failures.length?'PCE_QUOTE_COMPARISON_SCROLL_ISSUES_FOUND':'PCE_QUOTE_COMPARISON_SCROLL_READY')
if(failures.length)process.exitCode=1
