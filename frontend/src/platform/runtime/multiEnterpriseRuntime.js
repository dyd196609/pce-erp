const enterprises = new Map()

export const createEnterpriseInstance = (data) => {
  const id = 'ent_' + Date.now()

  enterprises.set(id, {
    id,
    data,
    status: 'RUNNING',
  })

  return id
}

export const getAllEnterprises = () => {
  return Array.from(enterprises.values())
}

export const runAllEnterprises = () => {
  enterprises.forEach((ent) => {
    ent.status = 'RUNNING'
  })
}
