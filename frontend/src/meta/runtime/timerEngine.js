const timers = new Map()

export function startNodeTimer(orderId, node) {
  if (!node?.sla) return

  const timer = setTimeout(() => {
    triggerEscalation(orderId, node)
  }, node.sla * 1000)

  timers.set(orderId, timer)
}

export function stopNodeTimer(orderId) {
  const timer = timers.get(orderId)

  if (timer) {
    clearTimeout(timer)
    timers.delete(orderId)
  }
}

function triggerEscalation(orderId, node) {
  console.warn('[ESCALATION] triggered for:', orderId, node?.id || node?.state || 'unknown')
}
