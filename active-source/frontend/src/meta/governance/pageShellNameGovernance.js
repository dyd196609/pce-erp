import { resolvePageNameConsumption } from './pageNameConsumer.js'
import { PAGE_NAME_CONSUMPTION_PROFILES } from './pageNameConsumptionGovernance.js'

export const PAGE_SHELL_NAME_GOVERNANCE_VERSION = 'V1.14.2.8.18.10.3.6'

export function createPageShellNameSourceReport() {
  return PAGE_NAME_CONSUMPTION_PROFILES.map(profile => {
    const name = resolvePageNameConsumption({ pageCode: profile.pageCode, route: profile.route })
    const processCenterName = name.processName
    const aligned = name.result === 'PASS'
      && processCenterName === name.pageName
      && name.pageName === name.headerName
      && name.headerName === name.internalTitle
      && name.internalTitle === name.browserTitle
    return Object.freeze({
      businessObject: name.businessObject,
      route: profile.route,
      pageCode: profile.pageCode,
      processCenterName,
      nodeIdentityName: name.processName,
      routerName: name.pageName,
      registryName: name.pageName,
      shellHeaderName: name.headerName,
      contentHeaderName: name.internalTitle,
      browserTitle: name.browserTitle,
      moduleCode: name.moduleCode,
      version: PAGE_SHELL_NAME_GOVERNANCE_VERSION,
      processCenterNameSource: name.nameSource,
      nodeIdentityNameSource: name.nameSource,
      routerNameSource: name.nameSource,
      shellNameSource: name.nameSource,
      contentHeaderNameSource: name.nameSource,
      browserTitleNameSource: name.nameSource,
      nameSource: name.nameSource,
      result: aligned ? 'PASS' : 'FAIL',
    })
  })
}

export function validatePageShellNameGovernance() {
  const rows = createPageShellNameSourceReport()
  const failures = rows.filter(row => row.result !== 'PASS')
  return Object.freeze({
    ruleCode: 'NAME-GOV-004',
    result: failures.length ? 'FAIL' : 'PASS',
    pageCount: rows.length,
    rows,
    failures,
  })
}
