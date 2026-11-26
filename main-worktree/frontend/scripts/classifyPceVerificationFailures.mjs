import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { classifyPceVerificationFailures } from '../src/meta/runtime/pceDefectClassifier.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const inputPath = process.argv[2] ? path.resolve(root, process.argv[2]) : ''
const rawFailures = inputPath && fs.existsSync(inputPath)
  ? JSON.parse(fs.readFileSync(inputPath, 'utf8'))
  : []

const failures = Array.isArray(rawFailures) ? rawFailures : (rawFailures.failures || [])
const classified = classifyPceVerificationFailures(failures)
const manualCount = classified.filter((item) => item.classification.manualClassificationRequired).length
const summary = {
  version: 'V1.14.2.8.4.3',
  inputPath: inputPath ? path.relative(root, inputPath).replaceAll('\\', '/') : 'none',
  failureCount: classified.length,
  basicPageOperationIssueCount: classified.filter((item) => item.classification.category === 'basic_page_operation').length,
  manualClassificationRequiredCount: manualCount,
  classifiedFailures: classified,
}

console.log(JSON.stringify(summary, null, 2))

if (manualCount > 0) {
  console.error(`存在 ${manualCount} 项需要人工分类的页面基础问题，阻断归档。`)
  process.exit(1)
}

console.log('PCE 页面基础问题分类通过。')


