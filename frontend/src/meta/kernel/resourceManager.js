export function allocateResources(task = {}) {
  return {
    cpu: 'auto',
    memory: 'dynamic',
    agents: 'elastic',
    priority: task.priority || 'MEDIUM',
  }
}
