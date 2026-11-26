import { enterpriseOSNavigation } from '../enterprise-os/enterpriseOSModel.js'

export const cockpitNavigation = [...enterpriseOSNavigation]

export function registerCockpitNavigation(item) {
  const existingIndex = cockpitNavigation.findIndex((entry) => entry.key === item.key)

  if (existingIndex >= 0) {
    cockpitNavigation.splice(existingIndex, 1, item)
  } else {
    cockpitNavigation.push(item)
  }

  return item
}

export function getCockpitNavigation() {
  const merged = new Map()

  cockpitNavigation.forEach((item) => merged.set(item.key, item))

  return Array.from(merged.values())
}
