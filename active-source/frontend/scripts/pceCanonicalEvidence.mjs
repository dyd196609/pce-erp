import fs from 'node:fs'
import path from 'node:path'

export function createCanonicalRunOutput(outputParent) {
  fs.mkdirSync(outputParent, { recursive: true })
  return fs.mkdtempSync(path.join(outputParent, 'canonical-'))
}

export function canonicalEvidenceId(moduleRecord) {
  const routeSuffix = String(moduleRecord.route || '').replace(/^\/+|\/+$/g, '').replace(/[^a-zA-Z0-9]+/g, '-')
  return `${moduleRecord.moduleId}--${routeSuffix || 'root'}`
}

export function canonicalEvidenceIdentity(moduleRecord) {
  return JSON.stringify([moduleRecord.moduleId, moduleRecord.route])
}

export function writeCanonicalEvidence(testInfo, moduleRecord, value) {
  const file = testInfo.outputPath('pce-name-consistency', `${canonicalEvidenceId(moduleRecord)}.json`)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
  return file
}

export function readCanonicalEvidence(outputDir) {
  const records = new Map()
  function visit(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name)
      // Dirent checks deliberately do not follow links to another run.
      if (entry.isDirectory()) visit(file)
      else if (entry.isFile() && path.basename(dir) === 'pce-name-consistency' && entry.name.endsWith('.json')) {
        const record = JSON.parse(fs.readFileSync(file, 'utf8'))
        if (typeof record.moduleId !== 'string' || typeof record.route !== 'string') {
          throw new Error(`Invalid canonical evidence identity: ${file}`)
        }
        records.set(canonicalEvidenceIdentity(record), record)
      }
    }
  }
  if (fs.existsSync(outputDir)) visit(outputDir)
  return [...records.values()]
}
