// ======================================
// AI → Meta Runtime V13 接入层
// ======================================

import { runPlatformV13 } from '../kernel/metaKernelV13'
import { generateERP } from './aiErpGenerator'
import { registerERP } from '../registry/metaRegistry'
import { registerInstance } from '../runtime/metaControlCenter'

export const aiCreateERP = async (prompt) => {
  const erp = await generateERP(prompt)

  const instance = runPlatformV13({
  meta: erp.meta,
  action: { action: 'init' },
  row: {},
  user: { id: 1 },
})

const instanceId = instance?.id || `runtime_${Date.now()}`

registerInstance({
  id: instanceId,
  meta: erp.meta,
  status: 'DRAFT',
  bpmState: 'DRAFT',
})

return {
  ...instance,
  id: instanceId,
}

import { emitEvent } from '../core/metaEventBus'

emitEvent('ERP_CREATED', {
  id: instanceId,
  meta: erp.meta,
})