export const WorkflowSchema = {
  entity: 'purchaseOrder',

  stateField: 'workflow_state',

  states: [
    'DRAFT',
    'SUBMITTED',
    'APPROVED',
    'RECEIVED',
    'STOCKED',
    'CLOSED',
  ],

  transitions: [
    { from: 'DRAFT', to: 'SUBMITTED' },
    { from: 'SUBMITTED', to: 'APPROVED' },
    { from: 'APPROVED', to: 'RECEIVED' },
    { from: 'RECEIVED', to: 'STOCKED' },
    { from: 'STOCKED', to: 'CLOSED' },
  ],

  actions: {
    SUBMIT: ['DRAFT'],
    APPROVE: ['SUBMITTED'],
    RECEIVE: ['APPROVED'],
    STOCK: ['RECEIVED'],
  },
}

export default WorkflowSchema

