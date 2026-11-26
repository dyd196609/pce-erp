import { createHash } from 'node:crypto'
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'

const stable = value => `${JSON.stringify(value, null, 2)}\n`
const sha256 = value => createHash('sha256').update(value).digest('hex')
const safe = value => String(value || '').replace(/[^a-zA-Z0-9._-]/g, '_')

const runProjection = run => ({
  runId: run.runId, pageCode: run.pageCode, pageUrl: run.pageUrl, templateCode: run.templateCode,
  mode: run.mode, status: 'ARCHIVED', startedAt: run.startedAt, completedAt: run.completedAt,
  collectorCount: run.collectorCount, evidenceCount: run.evidenceCount, result: run.result,
  scenarioCode: run.scenarioCode, canaryBatchId: run.canaryBatchId,
})

export async function archiveEnterprisePageAcceptanceRun(run, options = {}) {
  const version = safe(options.version || 'V1.14.2.8.4.22')
  const archiveRoot = path.resolve(options.archiveRoot || path.join(process.cwd(), 'test-results/page-acceptance'))
  const archiveDir = path.join(archiveRoot, version, safe(run.moduleCode), safe(run.pageCode), safe(run.runId))
  await mkdir(archiveDir, { recursive: true })
  const databaseProtection = run.runtimeContext?.databaseProtection || { productionUserDataWritten: false, businessWriteCount: 0, databaseHashUnchanged: false }
  const reportMarkdown = `# 页面验收自动运行报告\n\n- Run：${run.runId}\n- 页面：${run.pageCode}\n- 模板：${run.templateCode}\n- 模式：${run.mode}\n- 结果：${run.result}\n- 证据：${run.evidenceCount}\n- 业务写入：${databaseProtection.businessWriteCount}\n- 生产数据写入：${databaseProtection.productionUserDataWritten}\n`
  const payloads = {
    'run.json': stable(runProjection(run)),
    'acceptance.json': stable(run.evaluation?.acceptance || {}),
    'evidence.json': stable(run.collection?.evidence || []),
    'report.md': reportMarkdown,
    'database-protection.json': stable(databaseProtection),
  }
  const hashes = {}
  for (const [name, body] of Object.entries(payloads)) {
    await writeFile(path.join(archiveDir, name), body, 'utf8')
    hashes[name] = sha256(body)
  }
  for (const source of run.runtimeArtifacts?.screenshots || []) {
    const target = `screenshot-${path.basename(source)}`
    await copyFile(source, path.join(archiveDir, target))
    hashes[target] = sha256(await readFile(path.join(archiveDir, target)))
  }
  for (const source of run.runtimeArtifacts?.traces || []) {
    const target = `trace-${path.basename(source)}`
    await copyFile(source, path.join(archiveDir, target))
    hashes[target] = sha256(await readFile(path.join(archiveDir, target)))
  }
  const hashesPayload = { algorithm: 'sha256', files: hashes, aggregateHash: sha256(Object.entries(hashes).sort().map(([name, hash]) => `${name}:${hash}`).join('\n')) }
  await writeFile(path.join(archiveDir, 'hashes.json'), stable(hashesPayload), 'utf8')
  const manifestBase = {
    version, runnerVersion: options.runnerVersion, templateResolverVersion: options.templateResolverVersion,
    evidenceEngineVersion: options.evidenceEngineVersion, runId: run.runId, pageCode: run.pageCode,
    moduleCode: run.moduleCode, templateCode: run.templateCode, mode: run.mode, result: run.result,
    fileList: [...Object.keys(payloads), 'hashes.json', ...Object.keys(hashes).filter(name => name.startsWith('screenshot-') || name.startsWith('trace-'))],
    immutable: true,
  }
  const manifestHash = sha256(stable(manifestBase))
  await writeFile(path.join(archiveDir, 'manifest.json'), stable({ ...manifestBase, manifestHash }), 'utf8')
  return Object.freeze({ archiveDir, manifestHash, aggregateHash: hashesPayload.aggregateHash, immutable: true })
}

export async function verifyEnterprisePageAcceptanceRunArchive(archiveDir) {
  const required = ['manifest.json','run.json','acceptance.json','evidence.json','report.md','database-protection.json','hashes.json']
  const missing = required.filter(name => !existsSync(path.join(archiveDir, name)))
  const hashes = missing.length ? { files: {} } : JSON.parse(await readFile(path.join(archiveDir, 'hashes.json'), 'utf8'))
  const mismatches = []
  for (const [name, expected] of Object.entries(hashes.files || {})) if (sha256(await readFile(path.join(archiveDir, name))) !== expected) mismatches.push(name)
  return { valid: missing.length === 0 && mismatches.length === 0, missing, mismatches }
}
