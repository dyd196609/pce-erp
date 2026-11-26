import { test, expect } from '@playwright/test'
import { canonicalEvidenceIdentity, readCanonicalEvidence, writeCanonicalEvidence } from '../../scripts/pceCanonicalEvidence.mjs'
import { listPceProcessNavigationModules } from '../../src/meta/runtime/pceBusinessModuleRegistry.js'
import { loadProcessCenterRuntimeModel } from '../../src/meta/runtime/processCenterRuntime.js'

const VERSION = 'V1.14.2.8.4.6'
const formalProcessRoutes = new Set(
  loadProcessCenterRuntimeModel().processes
    .flatMap((process) => process.nodes || [])
    .map((node) => String(node.pageUrl || '').trim())
    .filter(Boolean),
)

test.describe.configure({ retries: 1 })

function routeUrl(route) {
  return `/#${route}`
}

function normalize(value = '') {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

async function textOrEmpty(locator) {
  if (await locator.count() < 1) return ''
  return normalize(await locator.first().innerText())
}

for (const moduleRecord of listPceProcessNavigationModules()) {
  test(`${moduleRecord.moduleId} ${moduleRecord.route} canonical name every surface`, async ({ page }, testInfo) => {
    const canonicalName = moduleRecord.canonicalName
    const processCenterRequired = formalProcessRoutes.has(moduleRecord.route)
    await page.goto(`/#/process-center?module=${encodeURIComponent(moduleRecord.moduleCode || '')}`, { waitUntil: 'networkidle' })
    await page.getByText(canonicalName).first().waitFor({ state: 'visible', timeout: 8000 }).catch(() => {})
    const processCenterBody = normalize(await page.locator('body').innerText())
    const processCenterText = processCenterBody.includes(canonicalName) ? canonicalName : ''

    await page.goto(routeUrl(moduleRecord.route), { waitUntil: 'networkidle' })
    await page.locator('[data-acceptance-id="page-business-title"]')
      .first()
      .waitFor({ state: 'visible', timeout: 8000 })
    const documentTitle = normalize(await page.title())
    // This suite starts a fresh unauthenticated context. Browser titles retain
    // the account prefix; the business surfaces still require the exact name.
    const expectedDocumentTitle = `未登录｜${canonicalName}`
    const pageH1 = await textOrEmpty(page.locator('[data-acceptance-id="page-business-title"]'))
    const internalSubjectTitle = await textOrEmpty(page.locator('[data-acceptance-id="page-internal-subject-title"]'))
    const breadcrumbTitle = await textOrEmpty(page.locator('[data-acceptance-id="page-breadcrumb-current-title"] strong'))

    const surfaces = {
      canonicalName,
      processCenterText,
      documentTitle,
      pageH1,
      internalSubjectTitle,
      breadcrumbTitle,
    }
    const mismatchItems = Object.entries(surfaces)
      .filter(([key, value]) => key !== 'canonicalName'
        && (key !== 'processCenterText' || processCenterRequired)
        && value !== (key === 'documentTitle' ? expectedDocumentTitle : canonicalName))
      .map(([key, value]) => ({ field: key, expected: key === 'documentTitle' ? expectedDocumentTitle : canonicalName, actual: value }))

    const evidence = {
      version: VERSION,
      moduleId: moduleRecord.moduleId,
      route: moduleRecord.route,
      canonicalName,
      processCenterRequired,
      processCenterText,
      documentTitle,
      expectedDocumentTitle,
      pageH1,
      internalSubjectTitle,
      breadcrumbTitle,
      exactMatched: mismatchItems.length === 0,
      mismatchItems,
      generatedAt: new Date().toISOString(),
    }
    writeCanonicalEvidence(testInfo, moduleRecord, evidence)

    expect(evidence.exactMatched, JSON.stringify(evidence, null, 2)).toBe(true)
  })
}

test('canonical name evidence coverage is complete', async ({}, testInfo) => {
  const modules = listPceProcessNavigationModules()
  const files = readCanonicalEvidence(testInfo.project.outputDir)
  expect(files.length).toBe(modules.length)
  expect(files.map(canonicalEvidenceIdentity).sort()).toEqual(modules.map(canonicalEvidenceIdentity).sort())
})
