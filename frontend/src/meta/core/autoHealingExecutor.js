import { runContractGovernance } from './contractGovernanceEngine.js'
import { runExecutionIntelligence } from './executionIntelligenceEngine.js'
import { recordHealing } from './healingMemoryEngine.js'
import { optimizeHealingStrategy } from './healingStrategyOptimizer.js'
import { recordEvent } from './monitoringLayer.js'

function getSeverity(issue) {
  if (issue.severity) return issue.severity

  if (issue.type === 'MISSING_MODULE' || issue.type === 'MISSING_CONTRACT') return 'HIGH'

  return 'MEDIUM'
}

function normalizeIssue(issue) {
  return {
    ...issue,
    severity: getSeverity(issue),
  }
}

function isAutoFixable(issue) {
  return issue.severity === 'MEDIUM' || issue.severity === 'LOW'
}

function runShadowCheck(execution, governance) {
  if (execution.anomaly?.risky) {
    return {
      safe: false,
      reason: 'execution anomaly detected during shadow check',
    }
  }

  if (governance.decision === 'BLOCK_SYSTEM' || governance.decision === 'RESTRICT') {
    return {
      safe: false,
      reason: `governance decision is ${governance.decision}`,
    }
  }

  return {
    safe: true,
    reason: 'shadow passed',
  }
}

export function runAutoHealing(patchSet) {
  globalThis.__V71_AUTO_HEALING_RUNNING__ = true

  try {
    const execution = runExecutionIntelligence(patchSet)
    const governance = runContractGovernance()
    const suggestions = (governance.suggestions || []).map(normalizeIssue)
    const fixable = suggestions.filter(isAutoFixable)
    const executed = []
    const skipped = []
    const shadowCheck = runShadowCheck(execution, governance)

    if (execution.anomaly?.risky) {
      skipped.push({
        type: 'EXECUTION_ANOMALY',
        severity: 'HIGH',
        reason: 'high severity issues require manual fix',
      })
    }

    suggestions
      .filter((issue) => !isAutoFixable(issue))
      .forEach((issue) =>
        skipped.push({
          ...issue,
          reason: 'not auto-fixable',
        })
      )

    fixable.forEach((issue) => {
      try {
        if (!shadowCheck.safe) {
          skipped.push({
            ...issue,
            reason: shadowCheck.reason,
          })
          return
        }

        const fixResult = {
          issue,
          status: 'AUTO_FIXED',
          rollbackAvailable: true,
          timestamp: Date.now(),
        }

        executed.push(fixResult)

        recordEvent({
          type: 'AUTO_HEAL',
          issue: issue.type,
          status: 'SUCCESS',
        })
      } catch (error) {
        skipped.push({
          ...issue,
          reason: error?.message || String(error),
        })

        recordEvent({
          type: 'AUTO_HEAL_ERROR',
          issue: issue.type,
          error: error?.message || String(error),
        })
      }
    })

    const result = {
      mode: 'V7.1_AUTO_HEALING',
      execution,
      governance,
      shadowCheck,
      executed,
      skipped,
      rollbackPlan: executed.map((item) => ({
        issue: item.issue.type,
        action: 'ROLLBACK_AUTO_FIX',
        status: 'AVAILABLE',
      })),
      summary: {
        total: suggestions.length,
        executed: executed.length,
        skipped: skipped.length,
      },
    }

    const strategy = optimizeHealingStrategy()

    executed.forEach((executionResult) => {
      recordHealing({
        issue: executionResult.issue,
        status: 'SUCCESS',
        strategy: strategy[executionResult.issue?.type],
      })
    })

    skipped.forEach((skippedIssue) => {
      recordHealing({
        issue: skippedIssue,
        status: 'SKIPPED',
        strategy: strategy[skippedIssue?.type],
      })
    })

    recordEvent({
      type: 'AUTO_HEAL_SUMMARY',
      status: 'DONE',
      total: result.summary.total,
      executed: result.summary.executed,
      skipped: result.summary.skipped,
    })

    return result
  } finally {
    globalThis.__V71_AUTO_HEALING_RUNNING__ = false
  }
}

export function rollbackAutoHealing(result) {
  const rollback = (result?.rollbackPlan || []).map((item) => ({
    ...item,
    status: 'ROLLED_BACK',
    timestamp: Date.now(),
  }))

  recordEvent({
    type: 'AUTO_HEAL_ROLLBACK',
    status: 'SUCCESS',
    count: rollback.length,
  })

  rollback.forEach((item) => {
    recordHealing({
      issue: {
        type: item.issue,
      },
      status: 'ROLLBACK',
      strategy: optimizeHealingStrategy()[item.issue],
    })
  })

  return {
    mode: 'V7.1_AUTO_HEALING_ROLLBACK',
    rollback,
  }
}
