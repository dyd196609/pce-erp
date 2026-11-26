import {
  createProcessActionRuntimeContract,
  createProcessContextContract,
  createProcessHandoffContract,
  createProcessNodeRuntimeContract,
  createProcessStateTransitionContract,
} from '../contract/index.js'

const prepareNode = createProcessNodeRuntimeContract({
  nodeCode: 'work-item-prepare',
  nodeName: 'Work Item Prepare',
  inputObject: 'GenericWorkItem',
  outputObject: 'GenericWorkItem',
  actions: ['COMPLETE_PREPARATION'],
  stateModel: 'WORK_ITEM_PREPARATION_STATE',
  nextNode: 'work-item-review',
})

const reviewNode = createProcessNodeRuntimeContract({
  nodeCode: 'work-item-review',
  nodeName: 'Work Item Review',
  inputObject: 'GenericWorkItem',
  outputObject: 'GenericWorkItem',
  actions: ['LOCK_REVIEW'],
  stateModel: 'WORK_ITEM_REVIEW_STATE',
  nextNode: null,
})

const preparationState = createProcessStateTransitionContract({
  modelCode: 'WORK_ITEM_PREPARATION_STATE',
  objectType: 'GenericWorkItem',
  initialState: 'draft',
  states: ['draft', 'prepared'],
  transitions: [{ actionCode: 'COMPLETE_PREPARATION', from: 'draft', to: 'prepared' }],
})

const reviewState = createProcessStateTransitionContract({
  modelCode: 'WORK_ITEM_REVIEW_STATE',
  objectType: 'GenericWorkItem',
  initialState: 'pending_review',
  states: ['pending_review', 'locked'],
  transitions: [{ actionCode: 'LOCK_REVIEW', from: 'pending_review', to: 'locked' }],
})

const handoff = createProcessHandoffContract({
  handoffCode: 'PREPARE_TO_REVIEW',
  fromNode: 'work-item-prepare',
  toNode: 'work-item-review',
  outputObject: 'GenericWorkItem',
  inputObject: 'GenericWorkItem',
  actionCode: 'COMPLETE_PREPARATION',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export const PROCESS_RUNTIME_REFERENCE_DEFINITION = Object.freeze({
  pages: Object.freeze([
    Object.freeze({ pageCode: 'generic-work-item-prepare', nodeCode: 'work-item-prepare', buttonBindings: Object.freeze([{ buttonCode: 'complete-preparation', actionCode: 'COMPLETE_PREPARATION' }]) }),
    Object.freeze({ pageCode: 'generic-work-item-review', nodeCode: 'work-item-review', buttonBindings: Object.freeze([{ buttonCode: 'lock-review', actionCode: 'LOCK_REVIEW' }]) }),
  ]),
  nodes: Object.freeze([prepareNode, reviewNode]),
  actions: Object.freeze([
    createProcessActionRuntimeContract({
      actionCode: 'COMPLETE_PREPARATION',
      actionName: 'Complete Preparation',
      buttonCode: 'complete-preparation',
      nodeCode: 'work-item-prepare',
      objectType: 'GenericWorkItem',
      stateModel: 'WORK_ITEM_PREPARATION_STATE',
      allowedFromStates: ['draft'],
      resultState: 'prepared',
      handoffCode: 'PREPARE_TO_REVIEW',
    }),
    createProcessActionRuntimeContract({
      actionCode: 'LOCK_REVIEW',
      actionName: 'Lock Review',
      buttonCode: 'lock-review',
      nodeCode: 'work-item-review',
      objectType: 'GenericWorkItem',
      stateModel: 'WORK_ITEM_REVIEW_STATE',
      allowedFromStates: ['pending_review'],
      resultState: 'locked',
    }),
  ]),
  stateModels: Object.freeze([preparationState, reviewState]),
  handoffs: Object.freeze([handoff]),
  contexts: Object.freeze([
    createProcessContextContract({
      processInstanceId: 'process-reference-001',
      processCode: 'GENERIC_WORK_ITEM_FLOW',
      objectType: 'GenericWorkItem',
      objectId: 'work-item-001',
      nodeCode: 'work-item-prepare',
      state: 'draft',
      actorId: 'reference-user',
      actorRole: 'process-operator',
      correlationId: 'correlation-reference-001',
      attributes: { source: 'process-runtime-reference' },
    }),
  ]),
  regressions: Object.freeze([
    Object.freeze({ caseCode: 'REG-RULE-001-ACTION-BINDING', result: 'PASS' }),
    Object.freeze({ caseCode: 'REG-RULE-004-NODE-HANDOFF', result: 'PASS' }),
  ]),
  businessWalkthrough: Object.freeze({
    type: 'End-to-End Business Walkthrough',
    walkthroughCode: 'GENERIC-WORK-ITEM-E2E',
    sourceNode: 'work-item-prepare',
    targetNode: 'work-item-review',
    executed: true,
    completed: true,
    result: 'PASS',
    steps: Object.freeze([
      Object.freeze({ sequence: 1, stepCode: 'PREPARE_WORK_ITEM', result: 'PASS', evidence: 'GenericWorkItem:draft' }),
      Object.freeze({ sequence: 2, stepCode: 'HANDOFF_TO_REVIEW', result: 'PASS', evidence: 'work-item-prepare->work-item-review' }),
    ]),
  }),
})
