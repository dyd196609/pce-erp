import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkpointImmutableHashes, checkpointPath } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointId = process.argv[2] || 'order_issued'
const hashesBefore = await checkpointImmutableHashes(checkpointId)
const result = spawnSync(process.execPath, [
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/goldenCheckpointRestore.spec.js',
], {
  cwd: root,
  env: { ...process.env, PCE_CHECKPOINT_ID: checkpointId },
  stdio: 'inherit',
})
const hashesAfter = await checkpointImmutableHashes(checkpointId)
const immutable = JSON.stringify(hashesBefore) === JSON.stringify(hashesAfter)
console.log(JSON.stringify({
  checkpointId,
  checkpointPath: checkpointPath(checkpointId),
  manifestHashBefore: hashesBefore['manifest.json'],
  manifestHashAfter: hashesAfter['manifest.json'],
  storageHashBefore: hashesBefore['storage-state.json'],
  storageHashAfter: hashesAfter['storage-state.json'],
  applicationHashBefore: hashesBefore['application-state.json'],
  applicationHashAfter: hashesAfter['application-state.json'],
  businessEntitiesHashBefore: hashesBefore['business-entities.json'],
  businessEntitiesHashAfter: hashesAfter['business-entities.json'],
  relationshipGraphHashBefore: hashesBefore['relationship-graph.json'],
  relationshipGraphHashAfter: hashesAfter['relationship-graph.json'],
  verificationDirectory: checkpointPath(checkpointId, 'verification'),
  immutable,
}, null, 2))
if (!immutable) process.exit(1)
process.exit(result.status ?? 1)
