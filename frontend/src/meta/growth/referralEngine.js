const referralEvents = []

export function trackReferral(event = {}) {
  const entry = {
    fromTenant: event.fromTenant || event.tenantId || 'demo_company',
    toTenant: event.toTenant || event.invitedTenant || 'pending_invite',
    template: event.template || event.workflowTemplate || 'default_workflow',
    campaign: event.campaign || 'tenant_invite',
    accepted: event.accepted === true,
    timestamp: Date.now(),
  }

  referralEvents.push(entry)
  return entry
}

export function inviteTenant(event = {}) {
  return trackReferral({
    ...event,
    accepted: false,
  })
}

export function shareWorkflowTemplate(event = {}) {
  return trackReferral({
    ...event,
    template: event.template || 'shared_workflow_template',
  })
}

export function getReferralNetwork() {
  const nodes = new Set()
  const edges = referralEvents.map((event) => {
    nodes.add(event.fromTenant)
    nodes.add(event.toTenant)
    return {
      from: event.fromTenant,
      to: event.toTenant,
      template: event.template,
      accepted: event.accepted,
    }
  })

  return {
    mode: 'V17_REFERRAL_NETWORK',
    nodes: Array.from(nodes),
    edges,
    invites: referralEvents.length,
    accepted: referralEvents.filter((event) => event.accepted).length,
  }
}

export function getReferralEvents() {
  return referralEvents
}

export function clearReferralEvents() {
  referralEvents.length = 0
}
