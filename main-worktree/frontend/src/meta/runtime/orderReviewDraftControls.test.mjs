import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

import { normalizeResponsibleEmployeeId } from './orderReviewDraftControls.js'

assert.equal(normalizeResponsibleEmployeeId(''), null)
assert.equal(normalizeResponsibleEmployeeId(undefined), null)
assert.equal(normalizeResponsibleEmployeeId(null), null)
assert.equal(normalizeResponsibleEmployeeId(17), 17)

const pageSource = await readFile(
  fileURLToPath(new URL('../pages/CrossFunctionalReviewPage.vue', import.meta.url)),
  'utf8',
)

assert.doesNotMatch(pageSource, /<th>查看依据或依据说明<\/th>/)
assert.match(pageSource, />补充说明<\/el-button>/)
assert.match(pageSource, /clearable:true/)
assert.match(pageSource, /title:'清空'/)
assert.doesNotMatch(pageSource, /其\{\{\s*index\s*\+\s*1\s*\}\}/)
assert.match(pageSource, /BusinessTableScrollContainer/)
assert.match(pageSource, /fixed="right"/)
assert.match(pageSource, /title="操作说明"/)
assert.match(pageSource, /保存草稿.*只保存内容.*进入待审批/s)
assert.match(pageSource, /当前进度与下一步/)
assert.match(pageSource, /操作未成功：\$\{errorMessage\}/)
assert.match(pageSource, /\{\{ title \}\}最终审批/)
assert.match(pageSource, /不按同意人数、比例或是否存在不同意自动形成最终结论/)
// Approval comes from server facts; opinion counts never decide the final result.
assert.match(pageSource, /facts\?\.approval\?\.statusLabel/)
assert.match(pageSource, /最终决定.*具备专门动作权限和公司范围/s)
assert.match(pageSource, /finalApprove/)
assert.match(pageSource, /:disabled="!canSubmit"/)
assert.match(pageSource, /canActorSignRow\(row\)/)
assert.match(pageSource, /提交成功：评审记录/)
assert.match(pageSource, /选择“不同意”后须填写原因并先保存本人意见，随后可以本人签认/)
assert.match(pageSource, /签认衔接缺口/)
assert.match(pageSource, /责任人办理/)
assert.match(pageSource, /首次登录准备/)
assert.match(pageSource, /具备资格/)
assert.match(pageSource, /canFullDraftEdit/)
assert.match(pageSource, /canEditRow\(row\)/)
assert.match(pageSource, /facts\.value\?\.authorization\?\.sign\?\.executable/)
assert.match(pageSource, /firstLoginSetup\?\.selfServiceAvailable|firstLoginSetup\?\.statement/)
assert.match(pageSource, /登录准备状态/)
assert.match(pageSource, /正式提交人/)
assert.match(pageSource, /eligibleSubmitters/)
assert.match(pageSource, /identityNote/)
assert.match(pageSource, /otherResponsibilityCandidates/)
assert.match(pageSource, /新增其它评审事项无需先保存即可选择合法责任候选/)
assert.match(pageSource, /未找到符合条件的责任人/)
assert.match(pageSource, /责任人候选读取失败/)
assert.match(pageSource, /state\.noCandidateReason/)
assert.match(pageSource, /当前身份没有责任选择资格/)
assert.match(pageSource, /persistedOpinionFingerprint/)
assert.match(pageSource, /请先保存本人意见/)
assert.match(pageSource, /signingReadiness\?\.disabledReason/)
assert.match(pageSource, /row\?\.signingReadiness\?\.executable===true/)

console.log('orderReviewDraftControls: final-approval contract assertions passed')
