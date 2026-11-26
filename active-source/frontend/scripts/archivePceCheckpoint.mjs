import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'

const checkpointName = process.argv[2]
if (!checkpointName || !/^[a-z0-9_.-]+$/i.test(checkpointName)) {
  throw new Error('checkpoint name is required')
}

const frontend = path.resolve(import.meta.dirname, '..')
const sourceRoot = path.resolve(frontend, '..')
const resultRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow')
const checkpointRoot = path.join(resultRoot, 'checkpoints')
const source = path.join(checkpointRoot, checkpointName)
const archiveRoot = 'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow'
const destination = path.join(archiveRoot, checkpointName)
const coreFiles = [
  'manifest.json', 'storage-state.json', 'application-state.json',
  'business-entities.json', 'relationship-graph.json',
]
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')

if (!fs.existsSync(source)) throw new Error(`checkpoint does not exist: ${source}`)
const coreHashes = {}
for (const name of coreFiles) {
  const file = path.join(source, name)
  if (!fs.existsSync(file) || fs.statSync(file).size === 0) throw new Error(`missing or empty core file: ${name}`)
  coreHashes[name] = hash(file)
}
const manifest = JSON.parse(fs.readFileSync(path.join(source, 'manifest.json'), 'utf8'))
if (manifest.result && manifest.result !== 'passed') throw new Error('checkpoint manifest result is not passed')

fs.mkdirSync(archiveRoot, { recursive: true })
if (fs.existsSync(destination)) {
  const archivedCheckpoint = path.join(destination, 'checkpoint')
  const archivedHashes = Object.fromEntries(coreFiles.map(name => [
    name, hash(path.join(archivedCheckpoint, name)),
  ]))
  const archivedManifest = JSON.parse(fs.readFileSync(path.join(archivedCheckpoint, 'manifest.json'), 'utf8'))
  const comparableSourceManifest = { ...manifest }
  const comparableArchivedManifest = { ...archivedManifest }
  delete comparableSourceManifest.createdAt
  delete comparableArchivedManifest.createdAt
  const immutablePayloadMatches = coreFiles
    .filter(name => name !== 'manifest.json')
    .every(name => archivedHashes[name] === coreHashes[name])
  const semanticManifestEquivalent = JSON.stringify(comparableArchivedManifest) === JSON.stringify(comparableSourceManifest)
  if (!immutablePayloadMatches || !semanticManifestEquivalent) {
    throw new Error(`archive already exists with different content: ${destination}`)
  }
  console.log(JSON.stringify({
    result: 'passed',
    checkpointName,
    source,
    destination,
    coreHashes: archivedHashes,
    archiveHashVerified: true,
    alreadyArchived: true,
    immutablePayloadMatches,
    semanticManifestEquivalent,
    reportFileCount: fs.readdirSync(path.join(destination, 'reports')).length,
    traceAndScreenshotCount: JSON.parse(fs.readFileSync(path.join(destination, 'trace-and-screenshot-list.json'), 'utf8')).length,
  }, null, 2))
  process.exit(0)
}
fs.mkdirSync(destination, { recursive: true })
fs.cpSync(source, path.join(destination, 'checkpoint'), { recursive: true })

const reportsDestination = path.join(destination, 'reports')
fs.mkdirSync(reportsDestination, { recursive: true })
for (const entry of fs.readdirSync(resultRoot, { withFileTypes: true })) {
  if (!entry.isFile() || !/\.(json|png|zip|txt)$/i.test(entry.name)) continue
  fs.copyFileSync(path.join(resultRoot, entry.name), path.join(reportsDestination, entry.name))
}
const traceFiles = []
const runtimeRoot = path.join(frontend, 'test-results', 'pce-runtime-acceptance')
if (fs.existsSync(runtimeRoot)) {
  const walk = root => {
    for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
      const full = path.join(root, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (/trace\.zip$|\.png$/i.test(entry.name)) traceFiles.push(path.relative(frontend, full))
    }
  }
  walk(runtimeRoot)
}
fs.writeFileSync(path.join(destination, 'sha256.json'), JSON.stringify(coreHashes, null, 2))
fs.writeFileSync(path.join(destination, 'trace-and-screenshot-list.json'), JSON.stringify(traceFiles, null, 2))
let gitStatus = ''
try {
  gitStatus = execFileSync('git', ['status', '--short'], { cwd: sourceRoot, encoding: 'utf8' })
} catch {}
fs.writeFileSync(path.join(destination, 'infrastructure-metadata.json'), JSON.stringify({
  checkpointName,
  archivedAt: new Date().toISOString(),
  sourceCheckpointId: manifest.sourceCheckpointId || manifest.inputCheckpoint || '',
  checkpointVersion: manifest.version || manifest.checkpointVersion || '',
  sourcePath: source,
  archivePath: destination,
  archiveOutsideTestResults: !destination.toLowerCase().includes('test-results'),
  gitStatusSummary: gitStatus.split(/\r?\n/).filter(Boolean),
}, null, 2))

const archivedHashes = Object.fromEntries(coreFiles.map(name => [
  name, hash(path.join(destination, 'checkpoint', name)),
]))
if (JSON.stringify(archivedHashes) !== JSON.stringify(coreHashes)) throw new Error('archive hash verification failed')
console.log(JSON.stringify({
  result: 'passed', checkpointName, source, destination, coreHashes,
  archiveHashVerified: true, reportFileCount: fs.readdirSync(reportsDestination).length,
  traceAndScreenshotCount: traceFiles.length,
}, null, 2))
