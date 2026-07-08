const bridgeHistory = []

const defaultFlows = [
  { from: 'organization', to: 'process-center', flow: 'Organization -> Process ownership', data: 'role_to_workflow' },
  { from: 'process-center', to: 'analytics', flow: 'Process Center -> Analytics sync', data: 'workflow_to_kpi' },
  { from: 'work-center', to: 'process-center', flow: 'Work Center -> Process execution', data: 'task_to_state' },
]

export function createCrossProductBridge(products = []) {
  const productIds = products.map((product) => product.id || product.key || product.name)
  const flows = defaultFlows.map((flow) => ({
    ...flow,
    products: productIds,
    status: 'SYNCED',
    timestamp: Date.now(),
  }))

  bridgeHistory.unshift(...flows)
  if (bridgeHistory.length > 100) bridgeHistory.length = 100

  return {
    crossProductDataFlow: 'ENABLED',
    flows,
    bridgeHealth: 'HEALTHY',
  }
}

export function getCrossProductBridgeSnapshot() {
  return {
    crossProductDataFlow: 'ENABLED',
    flows: [...bridgeHistory],
    bridgeHealth: 'HEALTHY',
  }
}
