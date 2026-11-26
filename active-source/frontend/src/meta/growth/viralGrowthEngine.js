import { getReferralNetwork, inviteTenant, trackReferral } from './referralEngine.js'

export function trackReferralEvent(context = {}) {
  return trackReferral({
    fromTenant: context.fromTenant || context.tenantId,
    toTenant: context.toTenant || context.invitedTenant,
    campaign: context.campaign || 'growth_referral',
    template: context.template || 'enterprise_workflow',
    accepted: context.accepted === true,
  })
}

export function inviteTenantToNetwork(context = {}) {
  return inviteTenant({
    fromTenant: context.fromTenant || context.tenantId,
    toTenant: context.toTenant || context.email || 'pending_invite',
    campaign: context.campaign || 'tenant_invitation',
  })
}

export function calculateViralCoefficient() {
  const network = getReferralNetwork()
  const activeReferrers = new Set(network.edges.map((edge) => edge.from)).size || 1

  return Number((network.accepted / activeReferrers).toFixed(2))
}

export function getViralGrowthSnapshot(context = {}) {
  if (context.referralEvent) {
    trackReferralEvent(context.referralEvent)
  }

  return {
    viralGrowth: 'ENABLED',
    network: getReferralNetwork(),
    viralCoefficient: calculateViralCoefficient(),
  }
}
