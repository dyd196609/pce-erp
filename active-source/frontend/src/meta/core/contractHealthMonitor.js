import { ApiContract } from './apiContract.js'

export function checkContractHealth() {
  const report = {
    totalModules: 0,
    missingList: [],
    missingDetail: [],
    healthy: true,
  }

  Object.keys(ApiContract).forEach((module) => {
    const contract = ApiContract[module]

    report.totalModules += 1

    if (!contract.list) {
      report.missingList.push(module)
      report.healthy = false
    }

    if (!contract.detail) {
      report.missingDetail.push(module)
      report.healthy = false
    }
  })

  return report
}
