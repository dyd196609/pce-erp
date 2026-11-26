import { createHash } from 'node:crypto'
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const stable = value => `${JSON.stringify(value, null, 2)}\n`
const sha256 = value => createHash('sha256').update(value).digest('hex')
const safe = value => String(value || '').replace(/[^a-zA-Z0-9._-]/g, '_')

export async function archiveEnterprisePageEvidenceFiles(evaluated, options = {}) {
  const version = safe(options.version || 'V1.14.2.8.4.21')
  const moduleCode = safe(evaluated.plan.pageIdentity.moduleCode)
  const pageCode = safe(evaluated.plan.pageIdentity.pageCode)
  const acceptanceRunId = safe(evaluated.plan.acceptanceRunId)
  const archiveRoot = path.resolve(options.archiveRoot || path.join(process.cwd(), 'test-results', 'page-acceptance'))
  const archiveDir = path.join(archiveRoot, version, moduleCode, pageCode, acceptanceRunId)
  const screenshotsDir = path.join(archiveDir, 'screenshots')
  const tracesDir = path.join(archiveDir, 'traces')
  await mkdir(screenshotsDir, { recursive: true })
  await mkdir(tracesDir, { recursive: true })
  for (const source of options.screenshots || []) await copyFile(source, path.join(screenshotsDir, path.basename(source)))
  for (const source of options.traces || []) await copyFile(source, path.join(tracesDir, path.basename(source)))

  const databaseProtection = options.databaseProtection || {
    productionUserDataWritten: false,
    businessWriteCount: 0,
    beforeHash: '',
    afterHash: '',
    databaseHashUnchanged: false,
  }
  const automaticEvidence = evaluated.evidence.filter(item => item.source !== 'manual')
  const manualAcceptance = options.manualAcceptance || '# 人工验收\n\n状态：PENDING\n\n说明：等待人工按验收步骤确认。\n'
  const payloads = {
    'acceptance.json': stable(evaluated.acceptance),
    'evidence.json': stable(evaluated.evidence),
    'automatic-evidence.json': stable(automaticEvidence),
    'manual-acceptance.md': manualAcceptance.endsWith('\n') ? manualAcceptance : `${manualAcceptance}\n`,
    'database-protection.json': stable(databaseProtection),
  }
  const fileHashes = {}
  for (const [name, body] of Object.entries(payloads)) {
    await writeFile(path.join(archiveDir, name), body, 'utf8')
    fileHashes[name] = sha256(body)
  }
  const hashes = {
    algorithm: 'sha256',
    files: fileHashes,
    aggregateHash: sha256(Object.entries(fileHashes).sort().map(([name, hash]) => `${name}:${hash}`).join('\n')),
  }
  const hashesBody = stable(hashes)
  await writeFile(path.join(archiveDir, 'hashes.json'), hashesBody, 'utf8')
  const manifestBase = {
    standard: 'PCE-ENTERPRISE-PAGE-ACCEPTANCE-ARCHIVE-V1.0',
    immutable: true,
    version,
    templateCode: evaluated.plan.templateCode || evaluated.plan.run.templateCode,
    templateVersion: evaluated.plan.run.version,
    collectorRegistryVersion: 'PCE-PAGE-EVIDENCE-COLLECTORS-V1.0',
    moduleCode,
    pageCode,
    acceptanceRunId,
    dataMode: evaluated.plan.dataMode,
    status: evaluated.status,
    fileList: [...Object.keys(payloads), 'hashes.json', 'screenshots/', 'traces/'],
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
  }
  const manifestHash = sha256(stable(manifestBase))
  await writeFile(path.join(archiveDir, 'manifest.json'), stable({ ...manifestBase, manifestHash }), 'utf8')
  return Object.freeze({ archiveDir, manifestHash, aggregateHash: hashes.aggregateHash, immutable: true })
}

export async function verifyEnterprisePageEvidenceArchive(archiveDir) {
  const required = ['manifest.json','acceptance.json','evidence.json','automatic-evidence.json','manual-acceptance.md','database-protection.json','hashes.json']
  const hashes = JSON.parse(await readFile(path.join(archiveDir, 'hashes.json'), 'utf8'))
  const mismatches = []
  for (const [name, expected] of Object.entries(hashes.files || {})) {
    const actual = sha256(await readFile(path.join(archiveDir, name)))
    if (actual !== expected) mismatches.push(name)
  }
  return Object.freeze({ valid: mismatches.length === 0, required, mismatches })
}
