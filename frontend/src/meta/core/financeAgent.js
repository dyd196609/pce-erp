export function financeAgent(task) {
  return {
    agent: 'FINANCE',
    result: `Processed finance task: ${task.step}`,
  }
}
