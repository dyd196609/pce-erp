import { runAgentCore } from '../agent-core/index.js'

export async function runAgent(goalInput, context = {}) {
  return runAgentCore(goalInput, context)
}
