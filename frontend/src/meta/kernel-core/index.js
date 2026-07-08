import { runUnifiedDecisionKernel } from '../core/unifiedDecisionKernel.js'
import { getLogs, getSystemHealth, recordEvent } from '../core/monitoringLayer.js'
import { detectStructuralDrift } from '../kernel/driftDetectionEngine.js'
import { listPlugins } from '../kernel/pluginSystem.js'
import { allocateResources } from '../kernel/resourceManager.js'
import { getStructureState, mutateStructure } from '../kernel/structureMutationEngine.js'

function runDecision(input, context = {}) {
  return runUnifiedDecisionKernel({
    input,
    context,
  })
}

function runRuntime(context = {}) {
  const resources = allocateResources({
    priority: context.priority,
  })

  const simulationEvents = context.mutations || []
  const simulatedStructure = simulationEvents.reduce(
    (_, event) => mutateStructure(event),
    getStructureState()
  )

  return {
    mode: 'KERNEL_RUNTIME',
    resources,
    logs: getSystemHealth(),
    selfModification: {
      mode: 'SIMULATION',
      structure: simulatedStructure,
    },
  }
}

function runPlugins() {
  return {
    registered: listPlugins(),
  }
}

function detectDrift() {
  return detectStructuralDrift()
}

export function runKernel(input, context = {}) {
  const execution = runDecision(input, context)
  const runtime = runRuntime(context)
  const plugins = runPlugins()
  const drift = detectDrift()

  recordEvent({
    type: 'KERNEL_RUN',
    module: 'kernel-core',
    status: execution.finalDecision?.decision || 'UNKNOWN',
  })

  return {
    mode: 'PROFITOS_KERNEL',
    execution,
    runtime,
    plugins,
    drift,
    logs: getLogs(),
  }
}
