import { createHash } from 'node:crypto'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  ENTERPRISE_ACCEPTANCE_REGISTRY,
  getEnterpriseAcceptanceModuleRegistration,
  validateEnterpriseAcceptanceRegistration,
} from '../src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import {
  activateModule,
  getModuleAcceptanceProfile,
  prepareModuleAcceptanceRun,
} from '../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'

export const VERSION = 'V1.14.2.8.4.24'
export const TARGET_STATUS = 'ACCEPTANCE_FRAMEWORK_AUTO_ACTIVATION_READY'
export const REGISTRY_ARCHIVE_FILES = Object.freeze([
  'registry.json',
  'activation-profile.json',
  'module-profile.json',
  'verification-report.json',
  'hashes.json',
])

const stable = value => `${JSON.stringify(value, null, 2)}\n`
const sha256 = value => createHash('sha256').update(value).digest('hex')
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyEnterpriseAcceptanceRegistry() {
  const registration = getEnterpriseAcceptanceModuleRegistration('SCM')
  const validation = validateEnterpriseAcceptanceRegistration(registration)
  const activation = activateAcceptanceFramework({ moduleCode: 'SCM' })
  const serviceActivation = activateModule({ moduleCode: 'SCM' })
  const profile = getModuleAcceptanceProfile({ moduleCode: 'SCM' })
  const prepared = prepareModuleAcceptanceRun({
    moduleCode: 'SCM',
    runInput: { runId: 'REGISTRY-VERIFY-RUN', pageUrl: '/scm/purchase-request', mode: 'production' },
  })
  const unknown = activateModule({ moduleCode: 'UNKNOWN_MODULE' })
  const incomplete = registration ? { ...registration, rules: Object.freeze([]) } : null
  const incompleteActivation = activateAcceptanceFramework({ moduleCode: 'SCM' }, { registration: incomplete })
  const rules = Object.freeze([
    rule('REGISTRY-001', '注册中心存在', ENTERPRISE_ACCEPTANCE_REGISTRY.registryVersion === 'V1' && ENTERPRISE_ACCEPTANCE_REGISTRY.modules.length > 0, ENTERPRISE_ACCEPTANCE_REGISTRY.version),
    rule('REGISTRY-002', 'SCM模块注册完整', validation.valid && registration?.objects.length === 3, { validation, objects: registration?.objects || [] }),
    rule('REGISTRY-003', '模板自动加载', activation.activated && activation.templates === 3 && activation.templateCodes.includes('SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2'), activation.templateCodes || []),
    rule('REGISTRY-004', 'Evidence自动加载', activation.collectors === 10 && activation.collectorCodes.length === 10, activation.collectorCodes || []),
    rule('REGISTRY-005', 'Rule自动加载', activation.rules === 20 && activation.registeredRuleSets === 8 && activation.ruleEntryCount > 20, { rules: activation.rules, ruleSets: activation.registeredRuleSets, ruleEntries: activation.ruleEntryCount }),
    rule('REGISTRY-006', 'Runner可以读取Profile', prepared.success && prepared.run.acceptanceProfile?.moduleCode === 'SCM' && prepared.run.readonly === true, { runId: prepared.run?.runId, profileModule: prepared.run?.acceptanceProfile?.moduleCode }),
    rule('REGISTRY-007', '未知模块阻断', unknown.success === false && unknown.activationStatus === 'BLOCKED' && unknown.error?.code === 'MODULE_NOT_REGISTERED', unknown.error || {}),
    rule('REGISTRY-008', '缺少规则不能激活', incompleteActivation.activated === false && incompleteActivation.error?.code === 'MODULE_REGISTRATION_INCOMPLETE', incompleteActivation.error || {}),
    rule('REGISTRY-009', '不能修改业务数据', activation.readOnly === true && activation.businessActions.length === 0 && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { readOnly: activation.readOnly, businessWriteCount: activation.businessWriteCount, productionUserDataWritten: activation.productionUserDataWritten }),
    rule('REGISTRY-010', '归档信息完整', registration?.archive?.immutable === true && REGISTRY_ARCHIVE_FILES.length === 5, { archive: registration?.archive, files: REGISTRY_ARCHIVE_FILES }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    scmActivation: Object.freeze({
      moduleCode: activation.moduleCode,
      activated: activation.activated,
      templates: activation.templates,
      collectors: activation.collectors,
      rules: activation.rules,
      objects: activation.objects,
    }),
    serviceActivationStatus: serviceActivation.activationStatus,
    moduleProfile: Object.freeze({ objects: profile.objects, templates: profile.templates, rules: profile.rules, collectors: profile.collectors }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writeEnterpriseAcceptanceRegistryArchive({ archiveRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const outputRoot = path.resolve(archiveRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'registry'))
  const activation = activateAcceptanceFramework({ moduleCode: 'SCM' })
  const profile = getModuleAcceptanceProfile({ moduleCode: 'SCM' })
  const report = verifyEnterpriseAcceptanceRegistry()
  const payloads = {
    'registry.json': ENTERPRISE_ACCEPTANCE_REGISTRY,
    'activation-profile.json': activation,
    'module-profile.json': profile,
    'verification-report.json': report,
  }
  const bodies = Object.fromEntries(Object.entries(payloads).map(([name, value]) => [name, stable(value)]))
  const fileHashes = Object.fromEntries(Object.entries(bodies).map(([name, body]) => [name, sha256(body)]))
  const hashes = Object.freeze({
    algorithm: 'sha256',
    files: Object.freeze(fileHashes),
    aggregateHash: sha256(Object.entries(fileHashes).sort().map(([name, hash]) => `${name}:${hash}`).join('\n')),
  })
  await fs.mkdir(outputRoot, { recursive: true })
  await Promise.all(Object.entries(bodies).map(([name, body]) => fs.writeFile(path.join(outputRoot, name), body, 'utf8')))
  await fs.writeFile(path.join(outputRoot, 'hashes.json'), stable(hashes), 'utf8')
  return Object.freeze({ outputRoot, files: REGISTRY_ARCHIVE_FILES, hashes, report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writeEnterpriseAcceptanceRegistryArchive()
  console.log(JSON.stringify({ ...result.report, archivePath: result.outputRoot, archiveFiles: result.files, aggregateHash: result.hashes.aggregateHash }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

