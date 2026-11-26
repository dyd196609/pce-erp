import { dataGateway } from '../runtime/dataGateway.js'
import { canPerformAction } from '../runtime/permissionEngine.js'
import { stateManager } from '../runtime/stateManager.js'

export const canExecute = (action) => {
  return canPerformAction(stateManager.getRole(), action?.permission || 'EXECUTE')
}

export const executeAction = async (action, row, ctx) => {
  switch (action.action) {
    case 'view':
      ctx.openDialog(row)
      break

    case 'edit':
      ctx.openDialog(row)
      break

    case 'close': {
      if (action.confirm) {
        const ok = confirm('Close this order?')
        if (!ok) return
      }

      const result = await dataGateway.execute('close', {
        module: 'purchaseOrder',
        apiAction: 'close',
        method: 'POST',
        params: { id: row.id },
      })

      if (result.success !== false) {
        ctx.reload()
      }
      break
    }

    default:
      console.warn('Unknown action:', action.action)
  }
}
