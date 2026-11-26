import { recordEvent } from '../core/monitoringLayer.js'
import { getStructureState, mutateStructure } from './structureMutationEngine.js'

export function runSelfModifyingKernel(input, context = {}) {
  const modifications = context.mutations || []
  const structure = modifications.reduce(
    (_, modification) => mutateStructure(modification),
    getStructureState()
  )

  recordEvent({
    type: 'KERNEL_MUTATION',
    module: 'selfModifyingKernel',
    status: 'SIMULATION',
    modifications: modifications.length,
  })

  return {
    mode: 'SELF_MODIFYING_SIMULATION',
    input,
    modifications,
    structure,
    system: {
      mutable: false,
      selfEvolving: 'simulation',
    },
  }
}
