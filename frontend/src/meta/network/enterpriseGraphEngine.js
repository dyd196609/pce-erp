const roleOrder = ['supplier', 'manufacturer', 'distributor', 'retailer']

function normalizeEnterprise(enterprise, index) {
  return {
    id: enterprise.id || `enterprise_${index + 1}`,
    name: enterprise.name || enterprise.id || `Enterprise ${index + 1}`,
    role: enterprise.role || roleOrder[index % roleOrder.length],
    inventory: Number(enterprise.inventory || enterprise.stock || 0),
    cash: Number(enterprise.cash || enterprise.cashFlow || 0),
    demand: Number(enterprise.demand || 0),
    capacity: Number(enterprise.capacity || 100),
    price: Number(enterprise.price || 100),
    schema: enterprise.schema,
    record: enterprise.record,
    rows: enterprise.rows,
  }
}

export function buildDependencies(enterprises = []) {
  const nodes = enterprises.map(normalizeEnterprise)

  return nodes.slice(0, -1).map((enterprise, index) => ({
    from: enterprise.id,
    to: nodes[index + 1].id,
    type: `${enterprise.role}_to_${nodes[index + 1].role}`,
    dependency: enterprise.role === 'supplier' ? 'materials' : 'flow',
    strength: Math.min(1, (enterprise.capacity + nodes[index + 1].demand) / 200),
  }))
}

export function mapInteractions(enterprises = []) {
  const nodes = enterprises.map(normalizeEnterprise)

  return nodes.map((enterprise) => ({
    enterprise: enterprise.id,
    role: enterprise.role,
    supplyPressure: enterprise.inventory < enterprise.demand ? 'HIGH' : 'LOW',
    cashPressure: enterprise.cash < enterprise.demand * enterprise.price ? 'MEDIUM' : 'LOW',
    collaborationNeed: enterprise.inventory < enterprise.demand || enterprise.capacity < enterprise.demand,
  }))
}

export function buildEnterpriseGraph(enterprises = []) {
  const nodes = enterprises.map(normalizeEnterprise)

  return {
    mode: 'V13.5_ENTERPRISE_GRAPH',
    nodes,
    edges: buildDependencies(nodes),
    relationships: mapInteractions(nodes),
  }
}

export function createDefaultEnterpriseNetwork() {
  return [
    { id: 'supplier_a', name: 'Supplier A', role: 'supplier', inventory: 900, cash: 120000, demand: 300, capacity: 600, price: 80 },
    { id: 'manufacturer_a', name: 'Manufacturer A', role: 'manufacturer', inventory: 260, cash: 220000, demand: 420, capacity: 500, price: 160 },
    { id: 'distributor_a', name: 'Distributor A', role: 'distributor', inventory: 180, cash: 150000, demand: 360, capacity: 380, price: 210 },
    { id: 'retailer_a', name: 'Retailer A', role: 'retailer', inventory: 90, cash: 90000, demand: 260, capacity: 300, price: 280 },
  ]
}
