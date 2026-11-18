export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_OWNERSHIP_VERSION = 'V1.14.2.8.6.16'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_OWNERSHIP = Object.freeze([
  Object.freeze({ state: 'created', owner: 'FormalPriceApprovalRuntime', ownershipMode: 'future_design', mutationAllowed: false }),
  Object.freeze({ state: 'pending_approval', owner: 'FuturePriceApprovalWorkflow', ownershipMode: 'isolated_future', mutationAllowed: false }),
  Object.freeze({ state: 'approved', owner: 'FuturePriceApprovalWorkflow', ownershipMode: 'isolated_future', mutationAllowed: false }),
  Object.freeze({ state: 'rejected', owner: 'FuturePriceApprovalWorkflow', ownershipMode: 'isolated_future', mutationAllowed: false }),
  Object.freeze({ state: 'cancelled', owner: 'FormalPriceApprovalRuntime', ownershipMode: 'future_design', mutationAllowed: false }),
])

export function validateFormalPriceApprovalPostCreationStateOwnership(ownership = FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_OWNERSHIP) {
  const states = ownership.map((item) => item.state)
  const valid = states.join(',') === 'created,pending_approval,approved,rejected,cancelled'
    && new Set(states).size === ownership.length
    && ownership.every((item) => item.mutationAllowed === false)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
