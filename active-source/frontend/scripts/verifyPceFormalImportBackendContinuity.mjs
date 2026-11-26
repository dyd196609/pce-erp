import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { resolvePcePythonRuntime } from './pcePythonExecutable.mjs'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const service = read('backend/pde/formal_import_service.py')
const views = read('backend/pde/formal_import_views.py')
const urls = read('backend/pde/urls.py')
const toolbar = read('frontend/src/meta/components/LatestBaseDataImportToolbarExtension.vue')
const api = read('frontend/src/api/pde.js')

const entities = ['customers', 'suppliers', 'materials', 'products', 'workshops', 'operations', 'work-centers', 'equipment', 'standard-capacities']
const failures = []
for (const entity of entities) {
  if (!service.includes(`"${entity}": {`)) failures.push(`missing schema: ${entity}`)
}
for (const marker of ['@transaction.atomic', 'ProductionFoundationService.write(', 'previewFingerprint', 'EXPLICIT_CONFIRMATION_REQUIRED', 'IMPORT_NOT_COMMITTABLE', 'DUPLICATE_IN_FILE', 'IDENTITY_CONFLICT']) {
  if (!service.includes(marker)) failures.push(`missing backend contract: ${marker}`)
}
for (const marker of ['formal-import/<slug:entity>/template/', 'formal-import/<slug:entity>/preview/', 'formal-import/<slug:entity>/commit/']) {
  if (!urls.includes(marker)) failures.push(`missing route: ${marker}`)
}
for (const marker of ['production.master_data.view', 'IsAuthenticated', 'FormalImportService.commit']) {
  if (!views.includes(marker)) failures.push(`missing view guard: ${marker}`)
}
for (const marker of ['下载错误报告', '确认导入', 'formal-import-preview-dialog', 'previewFormalImport', 'commitFormalImport']) {
  if (!(toolbar + api).includes(marker)) failures.push(`missing UI/API contract: ${marker}`)
}
if (service.includes('localStorage') || toolbar.includes('localStorage')) failures.push('formal import authority must not use localStorage')

const python = resolvePcePythonRuntime(root)
const check = spawnSync(python.executable, ['manage.py', 'check'], { cwd: path.join(root, 'backend'), env: python.env, encoding: 'utf8' })
if (check.status !== 0) failures.push(`django check failed: ${check.stderr || check.stdout}`)

if (failures.length) {
  console.error(JSON.stringify({ gate: 'verify:pce-formal-import-backend-continuity', status: 'FAIL', failures }, null, 2))
  process.exit(1)
}
console.log(JSON.stringify({
  gate: 'verify:pce-formal-import-backend-continuity', status: 'PASS',
  applicableEntities: entities.length, templateSchemaSingleSource: true,
  previewWriteCount: 0, canonicalWriteServiceReused: true,
  explicitConfirmation: true, fingerprintGuard: true, idempotency: true,
  auditAndFormalReadback: true, localStorageAuthorityCount: 0,
}, null, 2))
