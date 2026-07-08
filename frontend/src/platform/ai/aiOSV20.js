/**
 * ============================
 * Meta Runtime V20 - AI OS Entry
 * ============================
 */

import { autonomousERP } from './aiBrainV20'
import { bootOS } from '../kernel/metaOSKernelV20'

export const startAIOS = async (prompt) => {
  bootOS()

  const result = await autonomousERP(prompt)

  return {
    status: 'AI OS RUNNING',
    result,
  }
}
