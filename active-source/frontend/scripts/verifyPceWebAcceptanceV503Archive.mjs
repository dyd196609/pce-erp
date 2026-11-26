import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.3'
const CHECKPOINT_ID = 'pce_web_acceptance_v11_strict_pages_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT_ID)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', CHECKPOINT_ID, 'checkpoint')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v11-strict-golden-flow')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const files = root => {
  const rows = []
  const walk = (directory, prefix = '') => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === 'verification') continue
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) walk(full, relative)
      else rows.push(relative)
    }
  }
  walk(root)
  return rows.sort()
}
const sourceFiles = files(source)
const archiveFiles = files(archive)
const missingFiles = sourceFiles.filter(file => !archiveFiles.includes(file))
const extraFiles = archiveFiles.filter(file => !sourceFiles.includes(file))
const hashMismatches = sourceFiles.filter(file => archiveFiles.includes(file))
  .filter(file => sha(path.join(source, file)) !== sha(path.join(archive, file)))
const report = {
  result: missingFiles.length || extraFiles.length || hashMismatches.length ? 'failed' : 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  source,
  archive,
  sourceFileCount: sourceFiles.length,
  archiveFileCount: archiveFiles.length,
  missingFileCount: missingFiles.length,
  extraFileCount: extraFiles.length,
  hashMismatchCount: hashMismatches.length,
  archiveHashVerified: !hashMismatches.length,
  missingFiles,
  extraFiles,
  hashMismatches,
}
fs.writeFileSync(path.join(resultRoot, 'archive-verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exit(1)
