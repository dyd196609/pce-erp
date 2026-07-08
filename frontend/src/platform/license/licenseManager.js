/**
 * ============================
 * Meta Runtime V13 - License System
 * ============================
 */

let license = null

export const activateLicense = (key) => {
  license = {
    key,
    type: key.includes('enterprise') ? 'enterprise' : 'pro',
    valid: true,
    activatedAt: Date.now(),
  }

  return license
}

export const checkLicense = () => {
  return license?.valid === true
}

export const getLicense = () => license
