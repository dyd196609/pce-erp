import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const repo=path.resolve(root,'..')
const read=(base,relative)=>fs.readFileSync(path.join(base,relative),'utf8')
const run=args=>spawnSync(process.execPath,args,{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']})
const governance=['CODEX执行命令规范.md','PCE-ERP开发治理总规范.md','统一列表运行层规范.md','页面开发模板.md','一页一验收规范.md','治理符合性检查矩阵.md','问题案例库.md']
const governanceLoaded=governance.every(file=>fs.existsSync(path.join(repo,'docs/governance',file))&&read(repo,`docs/governance/${file}`).trim())
const standard=read(repo,'docs/governance/统一列表运行层规范.md')
const matrix=read(repo,'docs/governance/治理符合性检查矩阵.md')
const cases=read(repo,'docs/governance/问题案例库.md')
const tests=run(['--test','tests/acceptance/enterpriseTableScrollRuntimeV11428132.test.mjs'])
const regression=run(['scripts/verifyListRuntimeGovernanceV11428131.mjs'])
const vite=path.join(root,'node_modules','vite','bin','vite.js')
const build=run([vite,'build','.'])
for(const result of [tests,regression,build])if(result.status!==0)process.stderr.write(`${result.stdout||''}${result.stderr||''}`)
const runtime=read(root,'src/meta/runtime/pceTableScrollRuntime.js')
const container=read(root,'src/meta/components/BusinessTableScrollContainer.vue')
const table=read(root,'src/meta/components/PceEnterpriseListTable.vue')
const checks=[
  ['Governance Files Loaded',governanceLoaded],
  ['Governance First Check',standard.includes('TABLE-SCROLL-RUNTIME-001')&&matrix.includes('HORIZONTAL-SCROLL-VISIBLE-CHECK')&&cases.includes('宽表几何验收补强记录')],
  ['Table Container Contract',tests.status===0&&container.includes('TABLE-SCROLL-RUNTIME-001')&&table.includes('BusinessTableScrollContainer')],
  ['Horizontal Scroll',runtime.includes("tableOverflowX: 'auto'")&&container.includes('overflow-x: auto')],
  ['Horizontal Scroll Visible',tests.status===0&&runtime.includes('scrollWidth > clientWidth')&&container.includes('data-pce-horizontal-scroll-visible')],
  ['No Page Overflow',tests.status===0&&runtime.includes('pageScrollWidth <= pageClientWidth')],
  ['Sticky Action Column',tests.status===0&&table.includes('fixed="right"')&&runtime.includes('stickyColumnsInsideContainer')],
  ['SCM Regression',regression.status===0&&regression.stdout.includes('PCE_LIST_RUNTIME_GOVERNANCE_READY')],
  ['Build',build.status===0],
]
console.log('Version: V1.14.2.8.18.13.2')
for(const [label,passed] of checks)console.log(`${label} ${passed?'PASS':'FAIL'}`)
const automatic=checks.every(([,passed])=>passed)
console.log(`Automatic Acceptance ${automatic?'PASS':'FAIL'}`)
const humanEvidencePath=path.join(repo,'docs/acceptance/PCE-TABLE-SCROLL-RUNTIME-V11428132.json')
let humanAcceptance='PENDING'
if(fs.existsSync(humanEvidencePath)){
  try{
    const evidence=JSON.parse(fs.readFileSync(humanEvidencePath,'utf8'))
    const requiredPages=['purchase-inquiry','supplier-quote','quote-comparison','price-approval']
    if(evidence.result==='PASS'&&requiredPages.every(page=>evidence.pages?.[page]?.horizontalScrollVisible===true
      &&evidence.pages?.[page]?.noPageOverflow===true))humanAcceptance='PASS'
    else humanAcceptance='FAIL'
  }catch{humanAcceptance='FAIL'}
}
console.log(`Human Acceptance ${humanAcceptance}`)
const failures=checks.filter(([,passed])=>!passed).map(([label])=>label)
if(humanAcceptance!=='PASS')failures.push(`Human Acceptance ${humanAcceptance}`)
if(failures.length){console.log('Issues:');failures.forEach((label,index)=>console.log(`${index+1}. ${label}`))}
const ready=automatic&&humanAcceptance==='PASS'
console.log(ready?'PCE_TABLE_SCROLL_RUNTIME_READY':'PCE_TABLE_SCROLL_RUNTIME_ISSUES_FOUND')
if(!ready)process.exitCode=1
