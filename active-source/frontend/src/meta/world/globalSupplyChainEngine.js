const defaultLanes = [
  { from: 'CN', to: 'US', material: 'electronics', volume: 120, risk: 0.16 },
  { from: 'VN', to: 'DE', material: 'textiles', volume: 78, risk: 0.12 },
  { from: 'DE', to: 'CN', material: 'machinery', volume: 54, risk: 0.08 },
]

function normalizeLanes(context = {}) {
  return context.lanes?.length ? context.lanes : defaultLanes
}

export function simulateRawMaterialFlow(context = {}) {
  return normalizeLanes(context).map((lane) => ({
    from: lane.from,
    to: lane.to,
    material: lane.material,
    volume: lane.volume,
    status: lane.risk > 0.2 ? 'AT_RISK' : 'FLOWING',
  }))
}

export function simulateManufacturingFlow(context = {}) {
  return normalizeLanes(context).map((lane) => ({
    country: lane.from,
    output: Math.round(lane.volume * (1 - lane.risk)),
    capacity: lane.risk > 0.2 ? 'CONSTRAINED' : 'NORMAL',
  }))
}

export function simulateLogisticsNetwork(context = {}) {
  return normalizeLanes(context).map((lane) => ({
    route: `${lane.from}->${lane.to}`,
    leadTime: Math.round(5 + lane.risk * 20),
    logisticsCostIndex: Number((1 + lane.risk).toFixed(2)),
  }))
}

export function propagateDisruption(context = {}) {
  return normalizeLanes(context)
    .filter((lane) => lane.risk > 0.15)
    .map((lane) => ({
      source: lane.from,
      target: lane.to,
      disruption: 'SUPPLY_DELAY',
      impact: Number((lane.risk * lane.volume).toFixed(2)),
    }))
}

export function simulateGlobalSupplyChain(context = {}) {
  return {
    mode: 'V26_GLOBAL_SUPPLY_CHAIN',
    rawMaterialFlow: simulateRawMaterialFlow(context),
    manufacturingFlow: simulateManufacturingFlow(context),
    logisticsNetwork: simulateLogisticsNetwork(context),
    disruptionPropagation: propagateDisruption(context),
  }
}
