import { getEnterpriseOperationModel } from '../../../enterprise-os/enterpriseOperationModel.js'

export const PURCHASE_INQUIRY_USER_PROVIDER_CODE = 'UserProvider'

export function createPurchaseInquiryUserProvider() {
  return Object.freeze({
    providerCode: PURCHASE_INQUIRY_USER_PROVIDER_CODE,
    load() {
      const users = getEnterpriseOperationModel().organization.users || []
      const options = Object.freeze(users.map(user => Object.freeze({
        label: user.name, value: user.name, userId: user.id, department: user.department, role: user.role,
      })))
      return Object.freeze({ providerCode: this.providerCode, recordCount: options.length, options })
    },
  })
}

export const purchaseInquiryUserProvider = createPurchaseInquiryUserProvider()

