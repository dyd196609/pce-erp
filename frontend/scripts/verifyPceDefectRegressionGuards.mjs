import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  PCE_DEFECT_REGRESSION_VERSION,
  pceDefectRegressionRegistry,
} from '../src/meta/runtime/pceDefectRegressionRegistry.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const sourceRoots = [
  path.join(root, 'src/meta/pages'),
  path.join(root, 'src/meta/components'),
  path.join(root, 'src/meta/runtime'),
  path.join(root, 'tests'),
  path.join(root, 'scripts'),
]
const failures = []

function listTextFiles(dir) {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return listTextFiles(full)
    return /\.(vue|js|mjs|ps1|css)$/.test(entry.name) ? [full] : []
  })
}

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function lineOf(source, index) {
  return source.slice(0, Math.max(0, index)).split(/\r?\n/).length
}

function visibleTemplateText(template = '') {
  return template
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]*>/g, ' ')
}

function recordFailure({ defectId, file, line, prohibitedPattern, requiredImplementation, failureMessage }) {
  failures.push({
    defectId,
    file: file ? path.relative(root, file).replaceAll('\\', '/') : '',
    line,
    prohibitedPattern,
    requiredImplementation,
    failureMessage,
  })
}

const files = sourceRoots.flatMap(listTextFiles)
const psFile = path.join(root, 'scripts/Test-PcePurchasePaymentFlow.ps1')
const packageJson = JSON.parse(read('package.json'))

for (const file of files) {
  const relative = path.relative(root, file).replaceAll('\\', '/')
  const source = fs.readFileSync(file, 'utf8')
  const template = source.match(/<template>[\s\S]*?<\/template>/)?.[0] || ''
  const isPage = relative.startsWith('src/meta/pages/')

  if (isPage && /pce-horizontal-scroll-thumb|PceHorizontalScrollArea/.test(source)) {
    recordFailure({
      defectId: 'PCE-REG-002',
      file,
      line: lineOf(source, source.search(/pce-horizontal-scroll-thumb|PceHorizontalScrollArea/)),
      prohibitedPattern: 'custom horizontal scrollbar in business page',
      requiredImplementation: 'Use BusinessTableScrollContainer native baseline only.',
      failureMessage: 'Business page contains legacy custom horizontal scrollbar.',
    })
  }

  const visibleText = visibleTemplateText(template)
  if (isPage && /source=|target=|\.js\b/.test(visibleText)) {
    const technicalText = visibleText.search(/source=|target=|\.js\b/)
    recordFailure({
      defectId: 'PCE-REG-007',
      file,
      line: lineOf(visibleText, technicalText),
      prohibitedPattern: 'technical text in template',
      requiredImplementation: 'Business page text must use Chinese display formatter; raw values belong in diagnostics.',
      failureMessage: 'Business page primary view leaks technical values.',
    })
  }
}

const requiredDefectIds = [
  'PCE-REG-033',
  'PCE-REG-034',
  'PCE-REG-035',
  'PCE-REG-036',
  'PCE-REG-037',
  'PCE-REG-038',
  'PCE-REG-039',
  'PCE-REG-048',
  'PCE-REG-049',
  'PCE-REG-050',
  'PCE-REG-051',
  'PCE-REG-052',
  'PCE-REG-053',
  'PCE-REG-054',
  'PCE-REG-055',
  'PCE-REG-056',
  'PCE-REG-057',
  'PCE-REG-058',
  'PCE-REG-059',
  'PCE-REG-060',
  'PCE-REG-061',
  'PCE-REG-062',
  'PCE-REG-063',
  'PCE-REG-064',
  'PCE-REG-065',
  'PCE-REG-066',
  'PCE-REG-067',
  'PCE-REG-068',
  'PCE-REG-069',
  'PCE-REG-070',
  'PCE-REG-071',
  'PCE-REG-072',
  'PCE-REG-073',
  'PCE-REG-074',
  'PCE-REG-075',
  'PCE-REG-076',
  'PCE-REG-077',
  'PCE-REG-078',
  'PCE-REG-079',
  'PCE-REG-080',
  'PCE-REG-081',
  'PCE-REG-082',
  'PCE-REG-083',
  'PCE-REG-084',
  'PCE-REG-085',
  'PCE-REG-086',
  'PCE-REG-087',
  'PCE-REG-088',
  'PCE-REG-089',
  'PCE-REG-090',
  'PCE-REG-091',
  'PCE-REG-092',
]
for (const defectId of requiredDefectIds) {
  if (!pceDefectRegressionRegistry.some((item) => item.defectId === defectId)) {
    recordFailure({
      defectId: 'PCE-REG-039',
      file: null,
      line: 1,
      prohibitedPattern: `missing ${defectId}`,
      requiredImplementation: 'V1.14.2.8.4.1 repeated defects must be registered.',
      failureMessage: `${defectId} is not registered.`,
    })
  }
}

const requiredScripts = [
  'verify:pce-change-scope',
  'verify:pce-capability-invariants',
  'verify:pce-page-enforcement',
  'verify:pce-canonical-names',
  'verify:pce-selection-export-context',
  'verify:pce-selection-export-canonical',
  'verify:pce-operation-column-layout',
  'verify:pce-list-required-controls',
  'verify:pce-fixed-columns',
  'verify:pce-horizontal-scroll',
  'verify:pce-ui-fast',
  'verify:pce-ui-runtime',
  'verify:pce-ui-visual',
  'build',
]
for (const scriptName of requiredScripts) {
  if (!packageJson.scripts?.[scriptName]) {
    recordFailure({
      defectId: 'PCE-REG-039',
      file: path.join(root, 'package.json'),
      line: 1,
      prohibitedPattern: `missing npm script ${scriptName}`,
      requiredImplementation: 'Package scripts must expose all PCE page baseline gates.',
      failureMessage: `${scriptName} is missing from package.json.`,
    })
  }
}

if (!String(packageJson.scripts?.prebuild || '').includes('verify:pce-change-scope')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-selection-export-context')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-canonical-names')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-operation-column-layout')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-list-required-controls')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-fixed-columns')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-horizontal-scroll')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-capability-invariants')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-page-enforcement')
  || !String(packageJson.scripts?.prebuild || '').includes('verify:pce-ui-fast')) {
  recordFailure({
    defectId: 'PCE-REG-039',
    file: path.join(root, 'package.json'),
    line: 1,
    prohibitedPattern: 'build without PCE table binding page enforcement',
    requiredImplementation: 'prebuild must run verify:pce-canonical-names, verify:pce-fixed-columns, verify:pce-change-scope, verify:pce-capability-invariants, verify:pce-page-enforcement and verify:pce-ui-fast.',
    failureMessage: 'prebuild gate does not enforce PCE page/table binding checks.',
  })
}

const scrollContainerFile = path.join(root, 'src/meta/components/BusinessTableScrollContainer.vue')
if (fs.existsSync(scrollContainerFile)) {
  const source = fs.readFileSync(scrollContainerFile, 'utf8')
  const legacyActionShift = source.search(/translateX|translate3d\(|requestAnimationFrame|addEventListener\(['"]scroll|position:\s*sticky/)
  if (legacyActionShift >= 0) {
    recordFailure({
      defectId: 'PCE-REG-087',
      file: scrollContainerFile,
      line: lineOf(source, legacyActionShift),
      prohibitedPattern: 'fixed column transform/sticky/scroll synchronization',
      requiredImplementation: 'BusinessTableScrollContainer must leave fixed positioning to Element Plus native fixed columns.',
      failureMessage: 'BusinessTableScrollContainer still contains a conflicting fixed-column controller.',
    })
  }
  if (!source.includes('data-pce-horizontal-scroll-owner="element-plus-native"')) {
    recordFailure({
      defectId: 'PCE-REG-087',
      file: scrollContainerFile,
      line: 1,
      prohibitedPattern: 'missing native fixed owner declaration',
      requiredImplementation: 'BusinessTableScrollContainer must declare Element Plus native horizontal scroll ownership.',
      failureMessage: 'Element Plus native fixed-column ownership is not declared.',
    })
  }
}

const appExperienceFile = path.join(root, 'src/styles/appExperience.css')
if (fs.existsSync(appExperienceFile)) {
  const source = fs.readFileSync(appExperienceFile, 'utf8')
  const fixedBlocks = source.match(/[^{}]*(?:payment-fixed-action-column|el-table-fixed-column--left|el-table-fixed-column--right)[^{}]*\{[^{}]*\}/g) || []
  const conflictingBlock = fixedBlocks.find((block) => /position:\s*sticky|transform:\s*translate/.test(block))
  if (conflictingBlock) {
    recordFailure({
      defectId: 'PCE-REG-087',
      file: appExperienceFile,
      line: lineOf(source, source.indexOf(conflictingBlock)),
      prohibitedPattern: 'global Element Plus fixed-column sticky/transform override',
      requiredImplementation: 'Global CSS may style fixed-column backgrounds and shadows but must not control their position or transform.',
      failureMessage: 'Global CSS still overrides Element Plus fixed-column positioning.',
    })
  }
}

for (const file of files.filter((item) => path.relative(root, item).replaceAll('\\', '/').startsWith('src/meta/pages/'))) {
  const source = fs.readFileSync(file, 'utf8')
  const fixedColumnBlock = /:deep\([^)]*(business-table-selection-column|payment-fixed-selection-column|pce-fixed-index-column|payment-fixed-index-column|pce-fixed-primary-no-column|payment-fixed-no-column)[^)]*\)\s*\{[\s\S]{0,220}?(position:\s*sticky|left:\s*\d+px)/m
  const match = source.match(fixedColumnBlock)
  if (match) {
    recordFailure({
      defectId: 'PCE-REG-067',
      file,
      line: lineOf(source, source.indexOf(match[0])),
      prohibitedPattern: 'page-level fixed column sticky/left offset',
      requiredImplementation: 'Business table fixed columns must be controlled by pceTableFixedColumnContract and BusinessTableScrollContainer.',
      failureMessage: 'Business page contains local fixed-column sticky or left offset.',
    })
  }
}

if (fs.existsSync(psFile)) {
  const source = fs.readFileSync(psFile, 'utf8')
  const requiredMarkers = [
    'phase-a-payment-prepare-operation-column',
    'phase-a-payment-execution-draft',
    'phase-a-payment-record-review',
    'phase-a-payment-voucher-review',
    'phase-a-operation-jitter',
    'phase-a-required-list-controls',
    'phase-a-fixed-columns',
    'phase-a-horizontal-scroll',
    'phase-a-screenshot-evidence',
    'phase-b-discover-all-list-pages',
    'phase-b-operation-column-layout',
    'phase-b-list-required-controls',
    'phase-b-fixed-column-contract',
    'phase-b-horizontal-scroll-contract',
    'phase-b-basic-operation-classification',
    'phase-b-repeated-defect-guards',
    'phase-b-runtime-all-list-pages',
    'business-regression',
    'build',
    'verify:pce-operation-column-layout',
    'verify:pce-list-required-controls',
    'verify:pce-horizontal-scroll',
    'verify:pce-canonical-names',
    'verify:pce-fixed-columns',
    'verify:pce-page-enforcement',
    'verify:pce-ui-runtime',
    'completion-report.json',
    'test-results/pce-operation-column-layout',
    'test-results/pce-horizontal-scroll',
    'test-results/pce-specific-page-fix',
    'test-results/pce-ui-baseline/tables',
  ]
  for (const marker of requiredMarkers) {
    if (!source.includes(marker)) {
      recordFailure({
        defectId: 'PCE-REG-010',
        file: psFile,
        line: 1,
        prohibitedPattern: `missing marker ${marker}`,
        requiredImplementation: 'PowerShell full acceptance must run platform baseline gates before business tests.',
        failureMessage: `PowerShell script is missing baseline marker: ${marker}`,
      })
    }
  }
} else {
  recordFailure({
    defectId: 'PCE-REG-010',
    file: psFile,
    line: 1,
    prohibitedPattern: 'missing Test-PcePurchasePaymentFlow.ps1',
    requiredImplementation: 'PowerShell full acceptance script must exist.',
    failureMessage: 'PowerShell full acceptance script is missing.',
  })
}

const summary = {
  version: PCE_DEFECT_REGRESSION_VERSION,
  registeredDefectCount: pceDefectRegressionRegistry.length,
  scannedFileCount: files.length,
  repeatedDefectCount: failures.length,
  manualClassificationRequiredCount: 0,
  unregisteredPlatformRuleCount: 0,
}

console.log(JSON.stringify(summary, null, 2))

if (failures.length) {
  console.error(`${PCE_DEFECT_REGRESSION_VERSION} repeated defect guard failed: ${failures.length}`)
  for (const failure of failures) {
    console.error(`- ${failure.defectId} ${failure.file}:${failure.line} ${failure.prohibitedPattern}`)
    console.error(`  required: ${failure.requiredImplementation}`)
    console.error(`  message: ${failure.failureMessage}`)
  }
  process.exit(1)
}

console.log(`${PCE_DEFECT_REGRESSION_VERSION} repeated defect guard passed.`)
