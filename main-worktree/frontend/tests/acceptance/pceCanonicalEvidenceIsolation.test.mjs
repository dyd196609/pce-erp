import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createCanonicalRunOutput } from '../../scripts/pceCanonicalEvidence.mjs'
import { buildChildEnvironment, cleanupRuntimeIsolation, createRuntimeIsolation, frontendRoot } from '../../scripts/pcePlaywrightRunner.mjs'

const cli = path.join(frontendRoot, 'node_modules/@playwright/test/cli.js')
const config = path.join(frontendRoot, 'playwright.canonical.config.js')
const helper = pathToFileURL(path.join(frontendRoot, 'scripts/pceCanonicalEvidence.mjs')).href
const playwright = pathToFileURL(path.join(frontendRoot, 'node_modules/@playwright/test/index.mjs')).href
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex')

function run(args, cwd, env) {
  return spawnSync(process.execPath, [cli, ...args], { cwd, env, encoding: 'utf8', windowsHide: true, timeout: 60_000, maxBuffer: 2_000_000 })
}

function jsonFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(dir, entry.name)
    return entry.isDirectory() ? jsonFiles(file) : entry.isFile() && file.endsWith('.json') ? [file] : []
  })
}

test('canonical chain isolates repeated runs, retries, report reads and owned cleanup without browser or database', () => {
  const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'pce-canonical-isolation-test-'))
  // All paths here are disposable fixtures, outside both the project and formal DB.
  const history = path.join(sandbox, 'history')
  fs.mkdirSync(history)
  const sentinels = [
    'test-results/pce-name-consistency/alpha--alpha.json',
    'test-results/pce-name-consistency/old-only.json',
    'test-results/pce-runtime-html-report/index.html',
    'parent-output/results/alpha--alpha.json',
    'parent-output/html/index.html',
  ].map(name => {
    const file = path.join(history, name)
    fs.mkdirSync(path.dirname(file), { recursive: true })
    fs.writeFileSync(file, `PREEXISTING ${name}`, { flag: 'wx' })
    return { file, sha256: hash(file) }
  })
  const isolation = createRuntimeIsolation({ env: { ...process.env, PCE_PLAYWRIGHT_TEMP_BASE: sandbox } })
  const env = buildChildEnvironment(isolation)
  // Override only this disposable fixture's output parent, never a project path.
  env.PLAYWRIGHT_OUTPUT_DIR = path.join(history, 'parent-output')
  env.PLAYWRIGHT_HTML_OUTPUT_DIR = path.join(history, 'test-results/pce-runtime-html-report')
  env.PLAYWRIGHT_HTML_OPEN = 'always'
  delete env.PCE_CANONICAL_OUTPUT_DIR
  const missing = run(['test', '-c', config, '--list'], history, env)
  assert.notEqual(missing.status, 0)
  assert.match(missing.stdout + missing.stderr, /Canonical output isolation requires/)
  for (const item of sentinels) assert.equal(hash(item.file), item.sha256)

  const fixtures = path.join(isolation.tempRoot, 'fixtures')
  fs.mkdirSync(fixtures)
  const probeConfig = path.join(isolation.tempRoot, 'probe.config.mjs')
  fs.writeFileSync(probeConfig, `import config from ${JSON.stringify(pathToFileURL(config).href)};
export default {...config, testDir:${JSON.stringify(fixtures)}, testMatch:'output.spec.mjs', webServer:undefined};
`, { flag: 'wx' })
  fs.writeFileSync(path.join(fixtures, 'output.spec.mjs'), `
import fs from 'node:fs';
import path from 'node:path';
import {test, expect} from ${JSON.stringify(playwright)};
import {writeCanonicalEvidence,readCanonicalEvidence,canonicalEvidenceIdentity} from ${JSON.stringify(helper)};
test.describe.configure({retries:1});
const modules=[{moduleId:'alpha',route:'/alpha'},{moduleId:'beta',route:'/beta'}];
for(const record of modules) test(record.moduleId, async ({}, info)=>{
 expect(info.project.outputDir).toBe(path.join(process.env.PCE_CANONICAL_OUTPUT_DIR,'results'));
 const file=writeCanonicalEvidence(info,record,{...record,exactMatched:true});
 const before=fs.readFileSync(file,'utf8');
 expect(()=>writeCanonicalEvidence(info,record,{...record,exactMatched:false})).toThrow(/EEXIST/);
 expect(fs.readFileSync(file,'utf8')).toBe(before);
 if(record.moduleId==='beta') expect(info.retry,'intentional isolated retry fixture').toBe(1);
});
test('complete coverage',async ({}, info)=>{
 const files=readCanonicalEvidence(info.project.outputDir);
 expect(files.length).toBe(modules.length);
 expect(files.map(canonicalEvidenceIdentity).sort()).toEqual(modules.map(canonicalEvidenceIdentity).sort());
 console.log('CANONICAL_PROBE_READBACK '+JSON.stringify({outputDir:info.project.outputDir,count:files.length}));
});
`, { flag: 'wx' })

  const results = []
  for (let index = 0; index < 2; index++) {
    const outputRoot = createCanonicalRunOutput(env.PLAYWRIGHT_OUTPUT_DIR)
    const result = run(['test', '-c', probeConfig], history, { ...env, PCE_CANONICAL_OUTPUT_DIR: outputRoot })
    assert.ifError(result.error)
    assert.equal(result.status, 0, result.stdout + result.stderr)
    assert.match(result.stdout, /CANONICAL_PROBE_READBACK/)
    const files = jsonFiles(path.join(outputRoot, 'results')).filter(file => path.basename(path.dirname(file)) === 'pce-name-consistency')
    assert.equal(files.length, 3, 'one alpha and both beta retry attempts must remain')
    assert.equal(new Set(files.map(file => JSON.parse(fs.readFileSync(file, 'utf8')).moduleId)).size, 2)
    assert.ok(fs.existsSync(path.join(outputRoot, 'html/index.html')))
    for (const item of sentinels) assert.equal(hash(item.file), item.sha256)
    for (const previous of results) for (const item of previous.files) assert.equal(hash(item.file), item.sha256)
    results.push({ outputRoot, files: [...files, path.join(outputRoot, 'html/index.html')].map(file => ({ file, sha256: hash(file) })) })
  }
  assert.notEqual(results[0].outputRoot, results[1].outputRoot)
  // The existing owner-checked cleanup may remove only the run it created.
  assert.equal(cleanupRuntimeIsolation(isolation).removed, true)
  assert.equal(fs.existsSync(isolation.tempRoot), false)
  for (const item of sentinels) assert.equal(hash(item.file), item.sha256)
  for (const result of results) for (const item of result.files) assert.equal(hash(item.file), item.sha256)
  console.log('CANONICAL_ISOLATION_VALIDATED ' + JSON.stringify({ sandbox, sentinelCount:sentinels.length, runs:results, ownedTempRemoved:true, browserFixtures:0, databaseConnections:0, intentionalRetryFixtures:2 }))
  // Keep disposable evidence and sentinels for inspection; do not clean their parent.
})

test('canonical gate keeps original checks and never refers to the historical output as its input', () => {
  const spec = fs.readFileSync(path.join(frontendRoot, 'tests/ui-baseline/pceCanonicalNames.spec.js'), 'utf8')
  assert.match(spec, /expect\(evidence\.exactMatched, JSON\.stringify\(evidence, null, 2\)\)\.toBe\(true\)/)
  assert.match(spec, /expect\(files\.length\)\.toBe\(modules\.length\)/)
  assert.match(spec, /files\.map\(canonicalEvidenceIdentity\)\.sort\(\)/)
  assert.doesNotMatch(spec, /unlinkSync|rmSync|readdirSync|process\.cwd\(/)
  const gate = fs.readFileSync(path.join(frontendRoot, 'scripts/verifyPceCanonicalNames.mjs'), 'utf8')
  assert.match(gate, /playwright\.canonical\.config\.js/)
  assert.match(gate, /PCE_CANONICAL_OUTPUT/)
  assert.match(gate, /result\.error \|\| result\.status !== 0/)
})
