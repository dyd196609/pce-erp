import { buildEnterpriseGraph } from './enterpriseGraphEngine.js'

const defaultStateByRole = {
  supplier: 'SUPPLY_READY',
  manufacturer: 'PRODUCTION_READY',
  distributor: 'DISTRIBUTION_READY',
  retailer: 'SELLING_READY',
}

function nextNetworkState(role, currentState) {
  const transitions = {
    supplier: {
      SUPPLY_READY: 'MATERIAL_SENT',
      MATERIAL_SENT: 'SUPPLY_CLOSED',
    },
    manufacturer: {
      PRODUCTION_READY: 'PRODUCTION_STARTED',
      PRODUCTION_STARTED: 'GOODS_READY',
    },
    distributor: {
      DISTRIBUTION_READY: 'IN_TRANSIT',
      IN_TRANSIT: 'DELIVERED',
    },
    retailer: {
      SELLING_READY: 'SELLING',
      SELLING: 'CLOSED',
    },
  }

  return transitions[role]?.[currentState] || currentState || defaultStateByRole[role] || 'READY'
}

export function buildWorkflowMesh(enterprises = []) {
  const graph = buildEnterpriseGraph(enterprises)

  return {
    mode: 'INTER_ENTERPRISE_WORKFLOW_MESH',
    graph,
    paths: [
      ['supplier', 'manufacturer'],
      ['manufacturer', 'distributor'],
      ['distributor', 'retailer'],
    ],
    transitions: graph.edges.map((edge) => ({
      ...edge,
      state: 'READY_TO_TRANSFER',
      allowed: true,
    })),
  }
}

export function simulateCrossEnterpriseTransition(enterprises = []) {
  const graph = buildEnterpriseGraph(enterprises)
  const nodes = graph.nodes.map((enterprise) => {
    const currentState = enterprise.record?.workflow_state || defaultStateByRole[enterprise.role] || 'READY'

    return {
      enterprise: enterprise.id,
      role: enterprise.role,
      from: currentState,
      to: nextNetworkState(enterprise.role, currentState),
    }
  })

  return {
    mode: 'CROSS_ENTERPRISE_STATE_TRANSITION',
    nodes,
    edges: graph.edges,
  }
}
