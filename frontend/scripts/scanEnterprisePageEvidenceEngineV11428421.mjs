import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listEnterprisePageAcceptanceTemplates } from '../src/meta/acceptance/enterprisePageAcceptanceTemplateLibrary.js'
import { registerScmBusinessPageEvidenceCollectors } from '../src/meta/acceptance/evidence/scmBusinessPageEvidenceCollectors.js'
import { listEvidenceCollectors } from '../src/meta/acceptance/evidence/enterprisePageEvidenceCollectorRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputRoot = path.join(frontendRoot, 'test-results/page-evidence-engine-v11428421')
const sourceRoots = ['src/meta/acceptance','src/meta/runtime','src/meta/pages','src/router','scripts','tests']
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? walk(path.join(dir, entry.name)) : [path.join(dir, entry.name)])
const sourceFiles = sourceRoots.flatMap(relative => walk(path.join(frontendRoot, relative))).filter(file => /\.(js|mjs|vue|json|md)$/.test(file))
const textByFile = new Map(sourceFiles.map(file => [file, fs.readFileSync(file, 'utf8')]))
const templates = listEnterprisePageAcceptanceTemplates()
registerScmBusinessPageEvidenceCollectors()
const collectors = listEvidenceCollectors()
const allChecks = [...templates.commonChecklist.checks, ...templates.scmBusinessPage.scmChecks]
const duplicateCheckIds = allChecks.map(item => item.id).filter((id, index, ids) => ids.indexOf(id) !== index)
const coveredChecks = new Set(collectors.flatMap(item => item.supportedChecks))
const report = {
  version: 'V1.14.2.8.4.21',
  generatedAt: new Date().toISOString(),
  scanScope: sourceRoots,
  sourceFileCount: sourceFiles.length,
  acceptanceTemplateCount: 3,
  checkCount: allChecks.length,
  evidenceSources: ['router','registry','server','browser','filesystem','database_hash','manual'],
  existingPrograms: sourceFiles.filter(file => /acceptance|evidence/i.test(path.basename(file))).map(file => path.relative(frontendRoot, file).replaceAll('\\','/')),
  browserEvidenceFormats: ['screenshot','trace','dom','network','performance'],
  archiveStructure: ['manifest.json','acceptance.json','evidence.json','automatic-evidence.json','manual-acceptance.md','database-protection.json','hashes.json','screenshots/','traces/'],
  missingEvidenceCapabilities: allChecks.filter(check => !coveredChecks.has(check.id)).map(check => check.id),
  duplicateCheckIds,
  purchaseRequestBindings: {
    route: [...textByFile].some(([file, text]) => file.endsWith(path.join('router','index.js')) && text.includes("path: 'scm/purchase-request'")),
    page: [...textByFile].some(([file, text]) => file.endsWith('ScmPurchaseRequestPage.vue') && text.includes('PceEnterpriseListTable')),
    serverFacts: [...textByFile].some(([file, text]) => file.endsWith('ScmPurchaseRequestPage.vue') && text.includes("factSource:'server'")),
    canaryRuntime: [...textByFile].some(([file, text]) => file.endsWith('scmBusinessPageRuntimeProvider.js') && text.includes('canary_acceptance')),
  },
  productionUserDataWritten: false,
}
fs.mkdirSync(outputRoot, { recursive: true })
const output = `${JSON.stringify(report, null, 2)}\n`
fs.writeFileSync(path.join(outputRoot, 'page_acceptance_evidence_engine_scan_v11428421.json'), output)
fs.writeFileSync(path.join(frontendRoot, 'page_acceptance_evidence_engine_scan_v11428421.json'), output)
console.log(output)
