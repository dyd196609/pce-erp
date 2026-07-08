import { runAutonomousCycle } from '../ai/selfDrivingEngine.js'
import { buildEnterpriseGraph } from './enterpriseGraphEngine.js'
import { simulateCompetition } from './competitionSimulationEngine.js'
import { buildWorkflowMesh, simulateCrossEnterpriseTransition } from './interEnterpriseWorkflowMesh.js'
import { simulateResourceExchange } from './resourceExchangeEngine.js'

function buildGlobalSignals(graph, resourceExchange, competition) {
  return graph.nodes.map((node) => {
    const received = resourceExchange.transfers
      .filter((item) => item.to === node.id)
      .reduce((sum, item) => sum + item.inventoryTransfer, 0)
    const market = competition.market.find((item) => item.enterprise === node.id)
    const supplyDemandGap = Math.max(0, node.demand - node.inventory - received)

    return {
      enterprise: node.id,
      role: node.role,
      action: supplyDemandGap > 0 ? 'INCREASE_SUPPLY' : 'MAINTAIN_FLOW',
      efficiencySignal: received > 0 ? 'BALANCED' : 'MONITOR',
      costSignal: market?.pricingImpact < 1 ? 'PRICE_PRESSURE' : 'STABLE',
      supplyDemandGap,
    }
  })
}

export function optimizeEnterpriseNetwork(enterprises = [], context = {}) {
  const graph = buildEnterpriseGraph(enterprises)
  const workflowMesh = buildWorkflowMesh(enterprises)
  const crossEnterpriseFlow = simulateCrossEnterpriseTransition(enterprises)
  const resourceExchange = simulateResourceExchange(enterprises)
  const competition = simulateCompetition(enterprises, context)
  const selfDrivingReports = graph.nodes.map((enterprise) => runAutonomousCycle({
    schema: enterprise.schema || {
      name: enterprise.id,
      api: { module: enterprise.id },
      workflow: {
        stateField: 'workflow_state',
        states: ['READY', 'ACTIVE', 'CLOSED'],
        transitions: [
          { from: 'READY', to: 'ACTIVE' },
          { from: 'ACTIVE', to: 'CLOSED' },
        ],
        actions: {
          ACTIVATE: ['READY'],
          CLOSE: ['ACTIVE'],
        },
      },
    },
    record: enterprise.record || { workflow_state: 'READY', amount: enterprise.cash, stock_qty: enterprise.inventory },
    rows: enterprise.rows || [{ workflow_state: 'READY', amount: enterprise.cash, stock_qty: enterprise.inventory }],
    action: 'ACTIVATE',
    runtimeState: context.runtimeState,
  }))
  const signals = buildGlobalSignals(graph, resourceExchange, competition)
  const networkEfficiency = Math.round(
    Math.min(100, 60 + resourceExchange.inventoryTransfer / 10 + signals.filter((item) => item.efficiencySignal === 'BALANCED').length * 5)
  )
  const totalCost = resourceExchange.cashFlow
  const supplyDemandBalance = Math.max(0, 100 - signals.reduce((sum, item) => sum + item.supplyDemandGap, 0) / 10)

  return {
    mode: 'V13.5_GLOBAL_NETWORK_OPTIMIZATION',
    graph,
    workflowMesh,
    crossEnterpriseFlow,
    resourceExchange,
    competition,
    selfDrivingReports,
    globalOptimization: {
      objective: 'maximize efficiency, minimize cost, balance supply-demand',
      networkEfficiency,
      totalCost,
      supplyDemandBalance,
      signals,
    },
  }
}
