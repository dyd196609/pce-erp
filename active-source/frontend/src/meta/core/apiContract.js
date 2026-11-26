import { registerContract } from './contractRegistry.js'

export const ApiContract = {
  purchaseOrder: {
    list: '/api/execution/purchase/list',
    detail: '/api/execution/purchase/detail/:id',
    create: '/api/execution/purchase/create',
    update: '/api/execution/purchase/update/:id',
    delete: '/api/execution/purchase/delete/:id',
    close: '/api/execution/purchase/close/:id',
  },

  purchaseOrderDetail: {
    list: '/api/execution/purchase/detail',
    detail: '/api/execution/purchase/detail/:id',
  },

  inventory: {
    list: '/api/execution/inventory/list',
    detail: '/api/execution/inventory/detail/:id',
    create: '/api/execution/inventory/create',
    update: '/api/execution/inventory/update/:id',
    delete: '/api/execution/inventory/delete/:id',
  },

  finance: {
    list: '/api/execution/finance/list',
    detail: '/api/execution/finance/detail/:id',
    create: '/api/execution/finance/create',
    update: '/api/execution/finance/update/:id',
    delete: '/api/execution/finance/delete/:id',
  },

  crm: {
    list: '/api/execution/crm/list',
    detail: '/api/execution/crm/detail/:id',
    create: '/api/execution/crm/create',
    update: '/api/execution/crm/update/:id',
    delete: '/api/execution/crm/delete/:id',
  },

  scm: {
    list: '/api/execution/scm/list',
    detail: '/api/execution/scm/detail/:id',
    create: '/api/execution/scm/create',
    update: '/api/execution/scm/update/:id',
    delete: '/api/execution/scm/delete/:id',
  },
}

Object.entries(ApiContract).forEach(([module, contract]) => {
  registerContract(module, contract)
})
