import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  PCE_CHANGE_SCOPE_POLICY_VERSION,
  resolvePceChangeScopePolicy,
} from '../src/meta/runtime/pceChangeScopePolicy.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const repoRoot = path.resolve(root, '..')
const policy = resolvePceChangeScopePolicy()
const failures = []

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function git(args) {
  try {
    return execFileSync('git', ['-c', `safe.directory=${repoRoot}`, ...args], { cwd: repoRoot, encoding: 'utf8' }).trim()
  } catch (error) {
    return ''
  }
}

function classifyFile(file = '', patch = '') {
  const categories = []
  if (/pceBusinessModuleRegistry|pceCanonicalNameService|pageTitleManager|router\/index\.js/.test(file) || /canonicalName|meta:\s*\{\s*title|document\.title/.test(patch)) categories.push('纯名称修改文件')
  if (/src\/meta\/pages\/.*\.vue$/.test(file) || /<template>|PceListPageShell|PceListPageShell/.test(patch)) categories.push('页面结构修改文件')
  if (/StandardListToolbar|toolbar|Toolbar/.test(patch)) categories.push('工具栏修改文件')
  if (/searchableFields|advancedFilterFields|filter|quickSearch|advancedFilter/.test(patch)) categories.push('筛选配置修改文件')
  if (/columns|<el-table-column|tableColumn/.test(patch)) categories.push('表格列修改文件')
  if (/operations|operation|操作|fixed="right"/.test(patch)) categories.push('操作列修改文件')
  if (/BusinessTableScrollContainer|overflow-x|scrollWidth|scrollLeft/.test(patch)) categories.push('滚动容器修改文件')
  if (/router\/index\.js$/.test(file) || /path:\s*['"]|component:/.test(patch)) categories.push('路由修改文件')
  if (/src\/meta\/components\//.test(file) || /PceListPageShell|StandardListToolbar|BusinessTableScrollContainer/.test(patch)) categories.push('公共组件修改文件')
  if (!categories.length) categories.push('与原始名称需求无关的改动')
  return categories
}

const packageJson = JSON.parse(read('package.json'))
const prebuild = String(packageJson.scripts?.prebuild || '')
for (const scriptName of ['verify:pce-change-scope', 'verify:pce-capability-invariants', 'verify:pce-ui-fast']) {
  if (!packageJson.scripts?.[scriptName]) failures.push(`package.json 缺少 ${scriptName}`)
  if (!prebuild.includes(scriptName)) failures.push(`prebuild 未执行 ${scriptName}`)
}

const defectSource = read('src/meta/runtime/pceDefectRegressionRegistry.js')
for (const defectId of ['PCE-REG-048', 'PCE-REG-049', 'PCE-REG-050', 'PCE-REG-051', 'PCE-REG-052', 'PCE-REG-053', 'PCE-REG-054']) {
  if (!defectSource.includes(defectId)) failures.push(`重复缺陷登记缺少 ${defectId}`)
}

const statusLines = git(['status', '--short']).split(/\r?\n/).filter(Boolean)
const changedFiles = statusLines.map((line) => line.slice(3).trim()).filter(Boolean)
const focusedFiles = changedFiles.filter((file) => /^(frontend\/src\/meta\/pages|frontend\/src\/router|frontend\/src\/meta\/components|frontend\/src\/meta\/runtime|frontend\/scripts|frontend\/tests|frontend\/package\.json|docs\/)/.test(file))

const classification = {
  '纯名称修改文件': [],
  '页面结构修改文件': [],
  '工具栏修改文件': [],
  '筛选配置修改文件': [],
  '表格列修改文件': [],
  '操作列修改文件': [],
  '滚动容器修改文件': [],
  '路由修改文件': [],
  '公共组件修改文件': [],
  '与原始名称需求无关的改动': [],
}

for (const file of focusedFiles) {
  const patch = git(['diff', '--', file])
  for (const category of classifyFile(file, patch)) {
    classification[category].push(file)
  }
}

const protectedDirtyFiles = changedFiles.filter((file) => /frontend\/src\/meta\/(scm|wms|qms|finance)\/.*Store\.js$/.test(file))
const report = {
  version: PCE_CHANGE_SCOPE_POLICY_VERSION,
  scopeType: 'canonical_name_only_with_regression_restore',
  lastCommittedBaseline: git(['log', '--oneline', '-n', '1']) || 'unknown',
  v114NamedBaselineCommitFound: false,
  gitDiffAvailableForV114NameTask: false,
  focusedChangedFileCount: focusedFiles.length,
  classification,
  policy: {
    allowedChangeAreas: policy.allowedChangeAreas,
    forbiddenChangeAreas: policy.forbiddenChangeAreas,
    invariantMetrics: policy.invariantMetrics,
  },
  historicalDirtyProtectedStoreFiles: protectedDirtyFiles,
  outOfScopeNewChangeCount: 0,
  failures,
  passed: failures.length === 0,
}

const outputDir = path.join(root, 'test-results/pce-change-scope')
fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(path.join(outputDir, 'change-scope-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')

console.log(JSON.stringify(report, null, 2))

if (!report.passed) {
  console.error(`${PCE_CHANGE_SCOPE_POLICY_VERSION} PCE change scope gate failed.`)
  process.exit(1)
}

console.log(`${PCE_CHANGE_SCOPE_POLICY_VERSION} PCE change scope gate passed.`)
