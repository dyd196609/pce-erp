import purchaseOrderSchema from '../schema/purchase/purchaseOrder.js'
import purchaseOrderDetailSchema from '../schema/purchase/purchaseOrderDetail.js'
import { getGlobalModuleSchemas } from '../registry/globalModuleRegistry.js'

export const schemaRegistry = {
  '/purchase/order': () => Promise.resolve({ default: purchaseOrderSchema }),
  '/purchase/order/:id': () => Promise.resolve({ default: purchaseOrderDetailSchema }),
}

const schemaEntries = [
  ['/purchase/order', purchaseOrderSchema],
  ['/purchase/order/:id', purchaseOrderDetailSchema],
]

getGlobalModuleSchemas().forEach(({ route, schema }) => {
  schemaRegistry[route] = () => Promise.resolve({ default: schema })

  if (!schemaEntries.some(([entryRoute]) => entryRoute === route)) {
    schemaEntries.push([route, schema])
  }
})

export function registerSchema(route, schema) {
  schemaRegistry[route] = () => Promise.resolve({ default: schema })

  const existingIndex = schemaEntries.findIndex(([entryRoute]) => entryRoute === route)
  if (existingIndex >= 0) {
    schemaEntries.splice(existingIndex, 1, [route, schema])
  } else {
    schemaEntries.push([route, schema])
  }

  return {
    route,
    schema,
  }
}

export function getAllSchemas() {
  return schemaEntries.map((entry) => entry[1])
}

export function getAllSchemaEntries() {
  return schemaEntries.map(([route, schema]) => ({ route, schema }))
}
