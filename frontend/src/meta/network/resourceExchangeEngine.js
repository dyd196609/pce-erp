import { buildEnterpriseGraph } from './enterpriseGraphEngine.js'

function transferAmount(from, to) {
  const shortage = Math.max(0, to.demand - to.inventory)
  const available = Math.max(0, from.inventory - from.demand)

  return Math.min(shortage, available, 120)
}

export function simulateResourceExchange(enterprises = []) {
  const graph = buildEnterpriseGraph(enterprises)
  const transfers = graph.edges.map((edge) => {
    const from = graph.nodes.find((node) => node.id === edge.from)
    const to = graph.nodes.find((node) => node.id === edge.to)
    const qty = transferAmount(from, to)
    const cash = Math.round(qty * from.price)

    return {
      from: from.id,
      to: to.id,
      inventoryTransfer: qty,
      cashTransfer: cash,
      information: qty > 0 ? 'DEMAND_SIGNAL_PROPAGATED' : 'NO_TRANSFER_REQUIRED',
    }
  })

  return {
    mode: 'RESOURCE_EXCHANGE',
    cashFlow: transfers.reduce((sum, item) => sum + item.cashTransfer, 0),
    inventoryTransfer: transfers.reduce((sum, item) => sum + item.inventoryTransfer, 0),
    informationPropagation: transfers.map((item) => item.information),
    transfers,
  }
}
