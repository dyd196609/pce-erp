import fs from 'node:fs'
import path from 'node:path'
import {
  PCE_ADVANCED_FILTER_CONTRACT_VERSION,
  isPceDocumentNumberField,
  isPceScenarioCodeField,
  isPceSourceDocumentNumberField,
} from '../src/meta/runtime/pceAdvancedFilterContract.js'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { findPceBusinessModuleById } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { findPageAcceptanceContract } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const VERSION = 'V1.14.2.8.4.7.53.2'
const frontend = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-filter-control-v532')
const scannedPages = []
const wrongDocumentControls = []
const wrongSourceControls = []
const wrongScenarioControls = []

for (const page of financeProcessPageRegistry) {
  const moduleRecord = findPceBusinessModuleById(page.pageStepId)
  const acceptance = findPageAcceptanceContract(page.routePath)
  const moduleSchema = moduleRecord?.advancedFilterSchema || []
  const acceptanceSchema = acceptance?.listContracts?.[0]?.advancedFilterSchema || []
  const fields = []
  for (const field of moduleSchema) {
    const acceptanceField = acceptanceSchema.find(item => item.field === field.field)
    const row = {
      pageCode: page.pageStepId,
      canonicalName: page.canonicalName,
      fullUrl: page.fullUrl,
      field: field.field,
      label: field.label,
      type: field.type,
      controlType: acceptanceField?.controlType || acceptanceField?.type || '',
      optionsProvider: field.optionsProvider,
    }
    fields.push(row)
    const wrong = field.type !== 'select' || row.controlType !== 'select'
    if (isPceScenarioCodeField(field.field)) {
      if (wrong) wrongScenarioControls.push(row)
    } else if (isPceSourceDocumentNumberField(field.field)) {
      if (wrong) wrongSourceControls.push(row)
    } else if (isPceDocumentNumberField(field.field)) {
      if (wrong) wrongDocumentControls.push(row)
    }
  }
  scannedPages.push({
    pageCode: page.pageStepId,
    canonicalName: page.canonicalName,
    fullUrl: page.fullUrl,
    fields,
  })
}

const counts = {
  documentNoWrongControlCount: wrongDocumentControls.length,
  sourceNoWrongControlCount: wrongSourceControls.length,
  scenarioCodeWrongControlCount: wrongScenarioControls.length,
}
const guards = {
  filter_document_number_requires_select: counts.documentNoWrongControlCount === 0,
  filter_source_number_requires_select: counts.sourceNoWrongControlCount === 0,
  filter_scenario_code_requires_select: counts.scenarioCodeWrongControlCount === 0,
}
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  contractVersion: PCE_ADVANCED_FILTER_CONTRACT_VERSION,
  strictPageCount: financeProcessPageRegistry.length,
  scannedPageCount: scannedPages.length,
  ...counts,
  guards,
  failures,
  wrongControls: {
    documentNumbers: wrongDocumentControls,
    sourceDocumentNumbers: wrongSourceControls,
    scenarioCodes: wrongScenarioControls,
  },
  pages: scannedPages,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'filter-identifier-control-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({
  result: report.result,
  version: report.version,
  contractVersion: report.contractVersion,
  strictPageCount: report.strictPageCount,
  scannedPageCount: report.scannedPageCount,
  documentNoWrongControlCount: report.documentNoWrongControlCount,
  sourceNoWrongControlCount: report.sourceNoWrongControlCount,
  scenarioCodeWrongControlCount: report.scenarioCodeWrongControlCount,
  guards: report.guards,
  failures: report.failures,
}, null, 2))
if (failures.length) process.exit(1)
