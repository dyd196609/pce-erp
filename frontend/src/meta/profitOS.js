import { runAgentCore } from './agent-core/index.js'
import { runBusinessCore } from './business-core/index.js'
import { runKernel } from './kernel-core/index.js'
import { runReviewControlLoop } from './review/reviewControlEngine.js'

export function runProfitOS(input = {}, context = {}) {
  const goal = input.goal || input
  const businessData = context.data || context.order || {}

  const kernel = runKernel(input, context)
  const agent = runAgentCore(goal, context)
  const business = runBusinessCore(businessData)
  const reviewControl = runReviewControlLoop()

  return {
    mode: 'PROFITOS_SAAS',
    tenant: context.tenantId || 'default',
    kernel,
    agent,
    business,
    reviewControl,
  }
}
