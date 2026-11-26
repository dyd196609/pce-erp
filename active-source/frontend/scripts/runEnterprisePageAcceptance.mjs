import path from 'node:path'
import { createRun, execute } from '../src/meta/acceptance/runner/enterprisePageAcceptanceRunner.js'
import { collectEnterprisePageRunnerRuntime } from './enterprisePageAcceptanceNodeRuntime.mjs'
import { archiveEnterprisePageAcceptanceRun } from './enterprisePageAcceptanceRunnerArchiveWriter.mjs'

function parseArgs(argv) {
  const result = {}
  for (let index = 0; index < argv.length; index += 1) if (argv[index].startsWith('--')) result[argv[index].slice(2)] = argv[index + 1]?.startsWith('--') ? true : argv[++index]
  return result
}

const args = parseArgs(process.argv.slice(2))
const mode = args.mode === 'canary' ? 'canary' : 'production'
const pageUrl = args.url || '/scm/purchase-request'
const runId = args.runId || `PAGE-ACCEPTANCE-RUNNER-${mode.toUpperCase()}-${Date.now()}`
try {
  const run = createRun({ runId, pageUrl, moduleCode: args.module || '', mode, readonly: true, scenarioCode: args.scenario || '', canaryBatchId: args.batch || '' })
  const result = await execute(run, {
    runtimeContextProvider: currentRun => collectEnterprisePageRunnerRuntime(currentRun, { frontendRoot: process.cwd(), baseURL: args.baseURL || 'http://localhost:5173' }),
    archiveWriter: archiveEnterprisePageAcceptanceRun,
    archiveRoot: path.resolve('test-results/page-acceptance'),
    version: 'V1.14.2.8.4.22',
  })
  const output = { success: result.success, runId: result.runId, pageCode: result.pageCode, templateCode: result.templateCode, mode: result.mode, evidenceCount: result.evidenceCount, result: result.result, archivePath: result.archivePath, productionUserDataWritten: run.runtimeContext?.databaseProtection?.productionUserDataWritten ?? false, businessWriteCount: run.runtimeContext?.databaseProtection?.businessWriteCount ?? 0, databaseHashUnchanged: run.runtimeContext?.databaseProtection?.databaseHashUnchanged ?? false }
  process.stdout.write(`${JSON.stringify(output)}\n`)
  if (!result.success) process.exitCode = 1
} catch (error) {
  process.stdout.write(`${JSON.stringify({ success: false, result: 'FAIL', error: { code: String(error.message || error).split(':')[0], message: error.message || String(error) } })}\n`)
  process.exitCode = 1
}
