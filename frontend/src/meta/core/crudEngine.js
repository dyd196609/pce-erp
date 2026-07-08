import { dataGateway } from '../runtime/dataGateway.js'

export async function list(module, params = {}) {
  return dataGateway.list(module, params)
}

export async function detail(module, id) {
  return dataGateway.detail(module, id)
}

export async function create(module, data) {
  return dataGateway.execute('create', {
    module,
    apiAction: 'create',
    method: 'POST',
    data,
  })
}

export async function update(module, id, data) {
  return dataGateway.execute('update', {
    module,
    apiAction: 'update',
    method: 'PUT',
    params: { id },
    data,
  })
}

export async function remove(module, id) {
  return dataGateway.execute('delete', {
    module,
    apiAction: 'delete',
    method: 'DELETE',
    params: { id },
  })
}

export const crudEngine = {
  list,
  detail,
  create,
  update,
  delete: remove,
  remove,
}
