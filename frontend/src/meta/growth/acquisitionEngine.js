const acquisitionEvents = []

export function calculateConversion(event = {}) {
  if (event.conversionRate != null) return Number(event.conversionRate)
  if (event.visits && event.conversions != null) return Number(event.conversions) / Number(event.visits || 1)
  if (event.converted === true || event.tenantId) return 1
  return 0
}

export function mapFunnel(event = {}) {
  if (event.funnelStage) return event.funnelStage
  if (event.converted === true || event.tenantId) return 'converted'
  if (event.demoBooked) return 'demo'
  if (event.signupStarted) return 'signup'
  return 'lead'
}

export function trackAcquisition(event = {}) {
  const result = {
    source: event.source || 'direct',
    campaign: event.campaign || 'organic',
    conversionRate: calculateConversion(event),
    funnelStage: mapFunnel(event),
    tenantId: event.tenantId || event.tenant?.id || 'unknown',
    timestamp: Date.now(),
  }

  acquisitionEvents.push(result)
  return result
}

export function getAcquisitionEvents() {
  return acquisitionEvents
}

export function getAcquisitionFunnel() {
  const grouped = acquisitionEvents.reduce((map, event) => {
    const key = `${event.source}:${event.campaign}`
    if (!map[key]) {
      map[key] = {
        source: event.source,
        campaign: event.campaign,
        funnelStage: event.funnelStage || 'lead',
        leads: 0,
        conversions: 0,
      }
    }
    map[key].leads += 1
    if (event.conversionRate > 0) map[key].conversions += 1
    return map
  }, {})

  return Object.values(grouped).map((item) => ({
    ...item,
    conversionRate: item.leads === 0 ? 0 : item.conversions / item.leads,
  }))
}

export function clearAcquisitionEvents() {
  acquisitionEvents.length = 0
}
