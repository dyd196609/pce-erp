import { FORMAL_PRICE_APPROVAL_CREATION_SIMULATION } from '../domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationModel.js'
import { evaluateFormalPriceApprovalCreationSimulationRules } from '../domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationSimulationRuleEngine.js'

export const FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR_VERSION = 'V1.14.2.8.6.8'

export const FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR = Object.freeze({
  executorCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR',
  version: FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR_VERSION,
  simulationCode: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.simulationCode,
  executionMode: 'in_memory_zero_write',
  persistenceAdapterConnected: false,
  workflowEngineConnected: false,
  businessObjectFactoryConnected: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function executeFormalPriceApprovalCreationSimulation(input = {}) {
  const ruleEvaluation = evaluateFormalPriceApprovalCreationSimulationRules({ ...input, workflowEngineConnected: false })
  const simulatedReady = ruleEvaluation.decision === 'simulate_only'
  const statusTrace = simulatedReady
    ? Object.freeze(['not_started', 'checking', 'simulated_ready', 'completed'])
    : Object.freeze(['not_started', 'checking', 'blocked'])
  return Object.freeze({
    executorCode: FORMAL_PRICE_APPROVAL_CREATION_ZERO_WRITE_EXECUTOR.executorCode,
    simulationCode: FORMAL_PRICE_APPROVAL_CREATION_SIMULATION.simulationCode,
    artifactType: 'NON_PERSISTENT_SIMULATION',
    finalStatus: simulatedReady ? 'completed' : 'blocked',
    readinessStatus: simulatedReady ? 'simulated_ready' : 'blocked',
    statusTrace,
    ruleEvaluation,
    simulationCompleted: simulatedReady,
    simulationArtifactProduced: simulatedReady,
    simulationArtifactPersisted: false,
    businessObject: false,
    formalPriceApprovalObjectCreated: false,
    formalPriceApprovalObjectCount: 0,
    formalPriceApprovalObjectStatus: 'definition_only',
    approvalInstanceCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
