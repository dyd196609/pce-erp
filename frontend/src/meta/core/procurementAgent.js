export function procurementAgent(task) {
  return {
    agent: 'PROCUREMENT',
    result: `Processed procurement task: ${task.step}`,
  }
}
