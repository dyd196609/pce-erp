function inferGoalType(goal) {
  const text = String(goal || '').toLowerCase()

  if (text.includes('purchase') || text.includes('procurement')) return 'PROCUREMENT'
  if (text.includes('inventory') || text.includes('stock')) return 'INVENTORY'
  if (text.includes('finance') || text.includes('billing')) return 'FINANCE'

  return 'GENERAL'
}

export function parseGoal(input) {
  const goal = typeof input === 'object' && input !== null ? input.goal : input

  return {
    goal,
    type: inferGoalType(goal),
    priority: 'MEDIUM',
    timestamp: Date.now(),
  }
}