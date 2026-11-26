import { validateBusinessNameRegistry } from './businessNameRegistry.js'
import { validatePageNameConsumptionGovernance } from './pageNameConsumptionGovernance.js'
import { validatePageShellNameGovernance } from './pageShellNameGovernance.js'

export const BUSINESS_NAME_SINGLE_SOURCE_VERSION = 'V1.14.2.8.18.10.3.6'

export function validateBusinessNameSingleSourceGovernance() {
  const registry = validateBusinessNameRegistry()
  const consumption = validatePageNameConsumptionGovernance()
  const shell = validatePageShellNameGovernance()
  const runtimeSourcesAligned = shell.rows.every(row => [
    row.processCenterNameSource,
    row.nodeIdentityNameSource,
    row.routerNameSource,
    row.shellNameSource,
    row.contentHeaderNameSource,
    row.browserTitleNameSource,
  ].every(source => source === 'BusinessNameRegistry'))
  const runtimeNamesAligned = shell.rows.every(row => [
    row.processCenterName,
    row.nodeIdentityName,
    row.routerName,
    row.registryName,
    row.shellHeaderName,
    row.contentHeaderName,
    row.browserTitle,
  ].every(value => value === row.registryName))
  return Object.freeze({
    version: BUSINESS_NAME_SINGLE_SOURCE_VERSION,
    ruleCodes: ['NAME-GOV-001', 'NAME-GOV-002', 'NAME-GOV-003', 'NAME-GOV-004', 'NAME-GOV-005', 'NAME-GOV-006'],
    registry,
    consumption,
    shell,
    runtimeSourcesAligned,
    runtimeNamesAligned,
    result: registry.result === 'PASS'
      && consumption.result === 'PASS'
      && shell.result === 'PASS'
      && runtimeSourcesAligned
      && runtimeNamesAligned
      ? 'PASS'
      : 'FAIL',
  })
}
