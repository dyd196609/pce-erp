import { defineProcess } from './processDefinitionEngine.js'

const taskLedger = []

function dependenciesForStep(type = 'purchase', step = 'draft') {
  const process = defineProcess(type)
  const transition = process.transitions.find((item) => item.to === step)
  return transition ? [transition.from] : []
}

export function resolveTaskDependencies(type = 'purchase', step = 'draft', completedSteps = []) {
  const dependencies = dependenciesForStep(type, step)
  const missing = dependencies.filter((dependency) => !completedSteps.includes(dependency))

  return {
    step,
    dependencies,
    missing,
    resolved: missing.length === 0,
  }
}

export function assignTaskToRole(type = 'purchase', step = 'draft', context = {}) {
  const process = defineProcess(type)
  const role = process.roles[step] || context.role || 'Process Owner'
  const task = {
    id: `${type}:${step}:${taskLedger.length + 1}`,
    type,
    step,
    role,
    assignee: context.assignee || role,
    status: 'ASSIGNED',
    dependencies: dependenciesForStep(type, step),
    dependencyStatus: resolveTaskDependencies(type, step, context.completedSteps || []),
    createdAt: new Date().toISOString(),
    completedAt: null,
  }

  taskLedger.unshift(task)
  return task
}

export function completeTask(task = {}, context = {}) {
  if (!task?.id) {
    return {
      completed: false,
      reason: 'TASK_NOT_FOUND',
    }
  }

  const completed = {
    ...task,
    status: 'COMPLETED',
    executionConfirmed: true,
    completedBy: context.completedBy || task.role,
    completedAt: new Date().toISOString(),
  }
  const index = taskLedger.findIndex((item) => item.id === task.id)
  if (index >= 0) taskLedger.splice(index, 1, completed)

  return {
    completed: true,
    task: completed,
  }
}

export function autoCompleteTask(task = {}, context = {}) {
  const dependencyStatus = task.dependencyStatus || resolveTaskDependencies(
    task.type,
    task.step,
    context.completedSteps || []
  )

  if (!dependencyStatus.resolved) {
    return {
      completed: false,
      task: {
        ...task,
        status: 'WAITING_DEPENDENCY',
        dependencyStatus,
      },
      reason: 'DEPENDENCY_NOT_RESOLVED',
    }
  }

  return completeTask({
    ...task,
    dependencyStatus,
  }, {
    ...context,
    completedBy: context.completedBy || task.role,
  })
}

export function confirmTaskExecution(task = {}) {
  return {
    confirmed: task.status === 'COMPLETED' && task.executionConfirmed === true,
    taskId: task.id,
    step: task.step,
    role: task.role,
    status: task.status,
    reason: task.status === 'COMPLETED' ? null : 'TASK_NOT_EXECUTED',
  }
}

export function validateTaskCompletion(task = {}) {
  return {
    valid: task.status === 'COMPLETED' && task.executionConfirmed === true,
    taskId: task.id,
    role: task.role,
    reason: task.status === 'COMPLETED' && task.executionConfirmed === true ? null : 'TASK_NOT_COMPLETED',
  }
}

export function trackTaskExecution(type = 'purchase', steps = defineProcess(type).steps) {
  const completedSteps = []

  return steps.map((step) => {
    const assigned = assignTaskToRole(type, step.key, { completedSteps })
    const completion = autoCompleteTask(assigned, { completedSteps })
    if (completion.completed) completedSteps.push(step.key)

    return {
      assigned,
      completion,
      confirmation: confirmTaskExecution(completion.task),
      validation: validateTaskCompletion(completion.task),
    }
  })
}

export function getTaskLedger() {
  return [...taskLedger]
}
