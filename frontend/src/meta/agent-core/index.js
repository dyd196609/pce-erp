import { coordinateAgents } from '../core/agentCoordinator.js'
import { decideTasks } from '../core/executionAgent.js'
import { generateGoals } from '../core/goalGenerationEngine.js'
import { parseGoal } from '../core/goalEngine.js'
import { prioritizeGoals } from '../core/goalPrioritizationEngine.js'
import { recordEvent } from '../core/monitoringLayer.js'
import { planTasks } from '../core/taskPlanner.js'
import { getAllAgents } from '../core/agentRegistry.js'
import { getAgentScores, updateAgentScore } from '../core/agentScoreEngine.js'

function normalizeGoals(goalInput, context = {}) {
  const goals = []

  if (goalInput) {
    goals.push({
      ...parseGoal(goalInput),
      source: 'manual',
    })
  }

  const autoGoals = generateGoals(context)
  return prioritizeGoals(goals.concat(autoGoals.goals || []))
}

function selectAgents(plan) {
  return {
    mode: 'AGENT_MARKET_SIMULATION',
    available: getAllAgents(),
    taskCount: plan.tasks.length,
  }
}

function applyFeedback(execution) {
  const feedback = []

  execution.results.forEach((result) => {
    if (result.status === 'EXECUTED') {
      feedback.push(updateAgentScore(result.agent, 0.01))
    }
  })

  return {
    mode: 'AGENT_FEEDBACK',
    feedback,
    scores: getAgentScores(),
  }
}

function execute(plan) {
  const decisions = decideTasks(plan)
  return coordinateAgents(plan, decisions)
}

export function runAgentCore(goal, context = {}) {
  const goals = normalizeGoals(goal, context)
  const runs = goals.map((goalObj) => {
    const plan = planTasks(goalObj)
    const market = selectAgents(plan)
    const execution = execute(plan)
    const feedback = applyFeedback(execution)

    return {
      goal: goalObj,
      plan,
      execution,
      market,
      feedback,
    }
  })

  recordEvent({
    type: 'AGENT_CORE_RUN',
    module: 'agent-core',
    status: 'DONE',
    goals: goals.length,
  })

  return {
    mode: 'PROFITOS_AGENT_CORE',
    goals,
    runs,
    plan: runs[0]?.plan || { goal, tasks: [] },
    execution: runs[0]?.execution || { mode: 'MULTI_AGENT_EXECUTION', results: [] },
    market: runs[0]?.market || { mode: 'AGENT_MARKET_SIMULATION', available: [] },
    feedback: runs[0]?.feedback || { mode: 'AGENT_FEEDBACK', feedback: [] },
  }
}
