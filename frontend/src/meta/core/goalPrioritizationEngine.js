export function prioritizeGoals(goals) {
  const priorityMap = {
    HIGH: 3,
    MEDIUM: 2,
    LOW: 1,
  }

  return [...goals].sort((a, b) => {
    return (priorityMap[b.priority] || 0) - (priorityMap[a.priority] || 0)
  })
}
