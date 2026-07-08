import { WorkflowSchema } from '../core/workflowSchema.js'
import { purchaseFields } from '../../data/models/purchaseModel.js'

const purchaseOrderSchema = {
  name: 'purchaseOrder',
  labels: {
    en: 'Purchase Orders',
    'zh-CN': '采购订单',
  },

  meta: {
    module: 'purchase_order',
    title: '采购订单',
  },

  api: {
    module: 'purchaseOrder',
  },

  ui: {
    list: {
      columns: [
        { key: 'index', label: '序号', type: 'index', sortable: false, filter: false },
        ...purchaseFields,
      ],

      actions: [
        { key: 'detail', label: '详情', type: 'route', to: '/purchase/order/:id' },
        { key: 'edit', label: '编辑', type: 'route', to: '/purchase/order/:id/edit' },
        { key: 'delete', label: '删除', type: 'event', event: 'delete' },
        { key: 'SUBMIT', label: '提交', type: 'workflow', workflowAction: 'SUBMIT' },
        { key: 'APPROVE', label: '审批', type: 'workflow', workflowAction: 'APPROVE' },
        { key: 'RECEIVE', label: '收货', type: 'workflow', workflowAction: 'RECEIVE' },
        { key: 'STOCK', label: '入库', type: 'workflow', workflowAction: 'STOCK' },
      ],
    },

    detail: {},
    form: {},
  },

  workflow: {
    ...WorkflowSchema,
    entity: 'purchaseOrder',
    stateField: 'workflow_state',
    states: ['draft', 'submitted', 'approved', 'received', 'closed'],
    transitions: [
      { from: 'draft', to: 'submitted' },
      { from: 'submitted', to: 'approved' },
      { from: 'approved', to: 'received' },
      { from: 'received', to: 'closed' },
    ],
    actions: {
      SUBMIT: ['draft'],
      APPROVE: ['submitted'],
      RECEIVE: ['approved'],
      CLOSE: ['received'],
    },
  },
}

export default purchaseOrderSchema
