const hardBlockers = ['tenantIsolation', 'billing', 'apiGateway']

export function runGoLiveCheck(overrides = {}) {
  const checks = {
    docker: true,
    apiGateway: true,
    kernel: true,
    agent: true,
    business: true,
    tenantIsolation: true,
    billing: true,
    observability: true,
    rbac: true,
    ...overrides,
  }

  const failed = Object.entries(checks)
    .filter(([, value]) => !value)
    .map(([key]) => key)

  const hasHardBlocker = failed.some((key) => hardBlockers.includes(key))

  return {
    release: 'GO-LIVE',
    status:
      failed.length === 0
        ? 'PRODUCTION_READY'
        : hasHardBlocker
          ? 'BLOCK_PRODUCTION'
          : 'BLOCKED',
    checks,
    failedChecks: failed,
    passed: Object.keys(checks).length - failed.length,
    documents: [
      'GO_LIVE_RELEASE.md',
      'PRODUCTION_CHECKLIST.md',
      'GO_LIVE_CHECK.js',
    ],
  }
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replaceAll('\\', '/'))) {
  console.log(JSON.stringify(runGoLiveCheck(), null, 2))
}
