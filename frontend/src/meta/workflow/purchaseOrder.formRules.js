export default {
  draft: {
    editable: ['*'], // 全部可编辑
    readonly: [],
  },

  pending: {
    editable: [],
    readonly: ['*'], // 全部只读
  },

  approved: {
    editable: [],
    readonly: ['*'],
  },

  rejected: {
    editable: ['supplier', 'buyer', 'date'],
    readonly: ['order_no'],
  },
}
