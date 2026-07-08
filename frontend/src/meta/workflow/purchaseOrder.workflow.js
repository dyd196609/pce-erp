export default {
  name: 'purchaseOrderWorkflow',

  states: {
    draft: {
      label: '草稿',
      actions: ['submit'],
    },

    pending: {
      label: '审批中',
      actions: ['approve', 'reject'],
    },

    approved: {
      label: '已通过',
      actions: [],
    },

    rejected: {
      label: '已拒绝',
      actions: ['submit'],
    },
  },

  transitions: {
    submit: {
      from: ['draft', 'rejected'],
      to: 'pending',
    },

    approve: {
      from: ['pending'],
      to: 'approved',
    },

    reject: {
      from: ['pending'],
      to: 'rejected',
    },
  },
}
