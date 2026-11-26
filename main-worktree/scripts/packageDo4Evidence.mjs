// Mechanical evidence export only. Exact local sources are preserved; the ZIP is sanitized.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'

const root = path.resolve(import.meta.dirname, '..')
const out = path.join(root, 'frontend/test-results/pce-order-delivery-planning-do4-operable-closure-20260913')
const existing = fs.readdirSync(path.join(out,'baseline')).map(name=>({name,file:name.replaceAll('__','/')}))
const added = ['backend/sales/source_review.py','backend/sales/source_semantics.py',
  'docs/governance/ORDER_SOURCE_DO4_PRESERVATION_ASSOCIATIONS.md',
  'frontend/tests/acceptance/orderSourceDo4Operable.test.mjs',
  'scripts/inspectOrderSourceDo4.mjs','scripts/inspectDo4Runtime.py','scripts/runDo4IsolatedTests.py',
  'scripts/exportDo4ReadOnlyEvidence.py','scripts/packageDo4Evidence.mjs']
const entries = [...existing,...added.map(file=>({name:file.replaceAll('/','__'),file}))]
const sha = content=>crypto.createHash('sha256').update(content).digest('hex')
const inventory=[]
for(const {name,file} of entries){
  const target=path.join(root,file),final=path.join(out,'final',name),baseline=path.join(out,'baseline',name)
  fs.copyFileSync(target,final)
  let diff
  if(fs.existsSync(baseline)){
    const result=spawnSync('git',['diff','--no-index','--no-ext-diff','--',baseline,final],{encoding:'utf8',windowsHide:true,maxBuffer:20*1024*1024})
    if(![0,1].includes(result.status))throw new Error(result.stderr)
    diff=result.stdout
  }else{
    const lines=fs.readFileSync(final,'utf8').trimEnd().split(/\r?\n/)
    diff=`--- /dev/null\n+++ ${file}\n@@ -0,0 +1,${lines.length} @@\n`+lines.map(x=>'+'+x).join('\n')+'\n'
  }
  fs.writeFileSync(path.join(out,'diffs',name+'.diff'),diff)
  inventory.push({file,baselineSha256:fs.existsSync(baseline)?sha(fs.readFileSync(baseline)):null,finalSha256:sha(fs.readFileSync(final))})
}
fs.writeFileSync(path.join(out,'CHANGE_MANIFEST.json'),JSON.stringify(inventory,null,2)+'\n')
const pcm=fs.readFileSync(path.join(root,'docs/requirements/PCM/PCM开发需求文档_V1.6.md'),'utf8')
fs.writeFileSync(path.join(out,'RULE_AMENDMENT.md'),pcm.slice(pcm.indexOf('## V1.6 DO4 来源语义与原页办理校准')))
console.log(JSON.stringify({exportedFiles:inventory.length,output:out,databasesCopied:0}))

if(process.argv.includes('--share')){
  const stage=path.join(out,'shareable')
  fs.mkdirSync(stage,{recursive:true})
  const names=['FINAL_CONSOLIDATED.md','SOURCE_ROWS_37.md','RULE_AMENDMENT.md','TEST_SUMMARY.md',
    'READ_ONLY_A_PROJECTION.json','READ_ONLY_B_PROJECTION.json','CHANGE_MANIFEST.json','ENVIRONMENT_OBSERVATION.json',
    ...fs.readdirSync(path.join(out,'diffs')).map(name=>'diffs/'+name),
    ...fs.readdirSync(path.join(out,'final')).map(name=>'final/'+name),
    ...['isolated-tests-status-final.log','order-node.log','source-ui-contract.log','six-items-node.log','six-items-python.log',
      'completed-module-contracts.log','vite-build-delivery-final.log'].map(name=>'logs/'+name)]
  const manifest=[]
  for(const name of names){
    const original=fs.readFileSync(path.join(out,name),'utf8')
    const content=original.replaceAll('"not-used"','"ISOLATED_TEST_LITERAL_REDACTED"').replaceAll("'not-used'","'ISOLATED_TEST_LITERAL_REDACTED'")
    if(content.startsWith('SQLite format 3\0') || /pbkdf2_sha\d+\$|argon2\$|eyJ[A-Za-z0-9_-]{20,}\.eyJ/.test(content))throw new Error('Sensitive content refused: '+name)
    if(/\.(sqlite3?|db|bak)$/i.test(name))throw new Error('Database refused')
    const destination=path.join(stage,name)
    fs.mkdirSync(path.dirname(destination),{recursive:true})
    fs.writeFileSync(destination,content)
    manifest.push({name,sha256:sha(content),testLiteralRedacted:content!==original})
  }
  fs.writeFileSync(path.join(stage,'SHARE_MANIFEST.json'),JSON.stringify({databaseFiles:0,credentialValues:0,
    note:'Exact originals remain local. Test-only fixed demonstration literals were redacted in these readable sharing copies.',files:manifest},null,2))
  console.log(JSON.stringify({shareStage:stage,fileCount:manifest.length,redactedFiles:manifest.filter(x=>x.testLiteralRedacted).map(x=>x.name)}))
}
