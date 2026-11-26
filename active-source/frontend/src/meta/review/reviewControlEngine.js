import { recordEvent } from '../core/monitoringLayer.js'
import { PAGE_STATE } from '../specs/pageExecutionContract.v1.js'
import { generateReviewStatus } from './reviewExecutionEngine.js'
import { runAutoOptimization } from './autoOptimizationEngine.js'

const thresholds = {
  compliance: 0.6,
  module: 0.5,
  integrity: 0.8,
}

const moduleRestrictionMap = {
  ERP: ['dashboard'],
  MES: ['agents'],
  SCM: ['orders'],
  WMS: ['inventory'],
  CRM: ['customers'],
  BI: ['profit-analysis'],
  ProfitOS: ['system-health'],
}

let reviewControlState = {
  mode: 'V12.5_REVIEW_CONTROL_LOOP',
  decision: 'ALLOW',
  controlMode: PAGE_STATE.NORMAL,
  score: 100,
  restrictedModules: [],
  restrictions: [],
  allowedActions: ['detail', 'view', 'edit', 'delete'],
  permissionAdjustment: 'NONE',
  workflowOptimization: null,
  reason: 'review control not evaluated yet',
  lastReview: null,
  updatedAt: Date.now(),
}

function unique(values) {
  return Array.from(new Set(values))
}

function resolvePageModuleKey(schema = {}) {
  const module = schema?.api?.module || schema?.name || schema?.meta?.module || ''
  const normalized = String(module).toLowerCase()

  if (normalized.includes('purchase')) return 'orders'
  if (normalized.includes('inventory') || normalized.includes('warehouse')) return 'inventory'
  if (normalized.includes('customer')) return 'customers'
  if (normalized.includes('agent')) return 'agents'
  if (normalized.includes('profit')) return 'profit-analysis'
  if (normalized.includes('system')) return 'system-health'

  return normalized || 'dashboard'
}

function normalizeActionKey(action) {
  return action?.key || action?.action || action?.name || action?.event
}

function actionAllowed(action, allowedActions = []) {
  return allowedActions.includes(normalizeActionKey(action))
}

function resolveAllowedActions(controlMode) {
  if (controlMode === PAGE_STATE.BLOCKED) return []
  if (controlMode === PAGE_STATE.RESTRICTED) return ['detail', 'view', 'SUBMIT', 'APPROVE', 'RECEIVE', 'STOCK']
  if (controlMode === PAGE_STATE.MONITOR) return ['detail', 'view', 'edit']

  return ['detail', 'view', 'edit', 'delete', 'SUBMIT', 'APPROVE', 'RECEIVE', 'STOCK']
}

function mapDecisionToControlMode(decision) {
  if (decision === 'BLOCK') return PAGE_STATE.BLOCKED
  if (decision === 'RESTRICT') return PAGE_STATE.RESTRICTED
  if (decision === 'MONITOR') return PAGE_STATE.MONITOR

  return PAGE_STATE.NORMAL
}

function buildRestrictedModules(reviewStatus) {
  return unique(
    reviewStatus.moduleCompliance
      .filter((module) => module.complianceRate < thresholds.module)
      .flatMap((module) => moduleRestrictionMap[module.module] || [])
  )
}

function resolveDecision(reviewStatus, restrictedModules) {
  const complianceLow = reviewStatus.complianceRate < thresholds.compliance
  const criticalLow = reviewStatus.complianceRate < 0.25
  const integrityLow = reviewStatus.systemEvaluation.crossModule.integrityRate < thresholds.integrity
  const integrityCritical = reviewStatus.systemEvaluation.crossModule.integrityRate < 0.5
  const hasLowModules = restrictedModules.length > 0

  if (criticalLow || integrityCritical) {
    return {
      decision: 'BLOCK',
      reason: criticalLow
        ? 'critical review compliance failure'
        : 'critical cross-system integrity failure',
    }
  }

  if (integrityLow) {
    return {
      decision: 'RESTRICT',
      reason: 'cross-system integrity below threshold',
    }
  }

  if (complianceLow || hasLowModules) {
    return {
      decision: 'RESTRICT',
      reason: complianceLow
        ? 'enterprise review compliance below threshold'
        : 'one or more module scores below threshold',
    }
  }

  if (reviewStatus.completionRate < 0.9) {
    return {
      decision: 'MONITOR',
      reason: 'feature completion below observation threshold',
    }
  }

  return {
    decision: 'ALLOW',
    reason: 'review compliance is within control threshold',
  }
}

function buildReviewEnforcement(reviewStatus = generateReviewStatus()) {
  const restrictedModules = buildRestrictedModules(reviewStatus)
  const decision = resolveDecision(reviewStatus, restrictedModules)
  const controlMode = mapDecisionToControlMode(decision.decision)

  return {
    ...decision,
    controlMode,
    score: Math.round(reviewStatus.complianceRate * 100),
    restrictedModules,
    restrictions: restrictedModules,
    allowedActions: resolveAllowedActions(controlMode),
    thresholds,
    permissionAdjustment: restrictedModules.length > 0 ? 'RESTRICT_LOW_SCORE_MODULES' : 'NONE',
  }
}

export function enforceUIControl(schema = {}) {
  const reviewStatus = generateReviewStatus()
  const enforcement = buildReviewEnforcement(reviewStatus)
  const pageModuleKey = resolvePageModuleKey(schema)
  const pageRestricted = enforcement.restrictedModules.includes(pageModuleKey)
  const controlMode = pageRestricted ? PAGE_STATE.BLOCKED : enforcement.controlMode
  const allowedActions = resolveAllowedActions(controlMode)

  return {
    ...enforcement,
    controlMode,
    pageModuleKey,
    pageRestricted,
    allowedActions,
  }
}

export function enforceComplianceRules(subject = generateReviewStatus(), actions = [], schema = {}) {
  if (Array.isArray(subject)) {
    const uiControl = enforceUIControl(schema)

    return {
      columns: subject,
      actions: actions.filter((action) => actionAllowed(action, uiControl.allowedActions)),
      controlMode: uiControl.controlMode,
      allowedActions: uiControl.allowedActions,
      restrictions: uiControl.restrictions,
      pageModuleKey: uiControl.pageModuleKey,
    }
  }

  return buildReviewEnforcement(subject)
}

export function triggerSystemAdjustment(reviewStatus = generateReviewStatus()) {
  const optimization = runAutoOptimization(reviewStatus)
  const enforcement = enforceComplianceRules(reviewStatus)

  return {
    mode: 'REVIEW_SYSTEM_ADJUSTMENT',
    enforcement,
    optimization,
    workflowOptimization: optimization.workflow,
    executionPath: optimization.execution,
    loadRebalance: optimization.load,
  }
}

export function applyReviewDecisionToSystem(reviewStatus = generateReviewStatus()) {
  const adjustment = triggerSystemAdjustment(reviewStatus)

  reviewControlState = {
    mode: 'V12.5_REVIEW_CONTROL_LOOP',
    decision: adjustment.enforcement.decision,
    controlMode: adjustment.enforcement.controlMode,
    score: adjustment.enforcement.score,
    restrictedModules: adjustment.enforcement.restrictedModules,
    restrictions: adjustment.enforcement.restrictions,
    allowedActions: adjustment.enforcement.allowedActions,
    permissionAdjustment: adjustment.enforcement.permissionAdjustment,
    workflowOptimization: adjustment.workflowOptimization,
    executionPath: adjustment.executionPath,
    loadRebalance: adjustment.loadRebalance,
    reason: adjustment.enforcement.reason,
    lastReview: {
      complianceRate: reviewStatus.complianceRate,
      completionRate: reviewStatus.completionRate,
      integrityRate: reviewStatus.systemEvaluation.crossModule.integrityRate,
      systemScores: reviewStatus.systemScores,
    },
    updatedAt: Date.now(),
  }

  recordEvent({
    type: reviewControlState.decision === 'ALLOW' ? 'REVIEW_CONTROL' : 'REVIEW_CONTROL_ADJUSTMENT',
    module: 'review',
    status: reviewControlState.decision,
    reason: reviewControlState.reason,
    restrictedModules: reviewControlState.restrictedModules,
  })

  return reviewControlState
}

export function getReviewControlState() {
  return reviewControlState
}

export function isModuleRestrictedByReview(moduleKey) {
  return reviewControlState.restrictedModules.includes(moduleKey)
}

export function runReviewControlLoop(schema = {}) {
  const review = generateReviewStatus()
  const control = applyReviewDecisionToSystem(review)
  const pageControl = enforceUIControl(schema)

  return {
    mode: pageControl.controlMode,
    score: control.score,
    restrictions: control.restrictions,
    allowedActions: pageControl.allowedActions,
    controlMode: pageControl.controlMode,
    review,
    control,
    pageControl,
    loopMode: 'REVIEW_DECISION_EXECUTION_REVIEW_LOOP',
    loop: ['Review', 'Decision', 'Execution', 'Review'],
  }
}
