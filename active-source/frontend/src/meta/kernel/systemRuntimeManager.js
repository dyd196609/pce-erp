import { runKernel } from '../kernel-core/index.js'

export function bootEnterpriseSystem(input, context = {}) {
  const system = runKernel(input, context)

  return {
    boot: 'SUCCESS',
    ...system,
    system,
    runtime: {
      ...system.runtime,
      mode: 'ENTERPRISE_OS',
      isolation: true,
      selfManaged: true,
    },
  }
}
