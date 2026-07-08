// ======================================
// Enterprise Network V23
// 企业经济网络
// ======================================

const enterprises = new Map()

export const registerEnterprise = (enterprise) => {
  enterprises.set(enterprise.id, enterprise)
}

export const getEnterprise = (id) => {
  return enterprises.get(id)
}

export const getAllEnterprises = () => {
  return Array.from(enterprises.values())
}

/**
 * 企业之间建立关系
 */
export const linkEnterprises = (a, b, relation) => {
  const A = enterprises.get(a)
  const B = enterprises.get(b)

  if (!A || !B) return

  A.links = A.links || []
  B.links = B.links || []

  A.links.push({ to: b, relation })
  B.links.push({ to: a, relation })
}
