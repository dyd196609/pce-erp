export function inventoryAgent(task) {
  return {
    agent: 'INVENTORY',
    result: `Processed inventory task: ${task.step}`,
  }
}
