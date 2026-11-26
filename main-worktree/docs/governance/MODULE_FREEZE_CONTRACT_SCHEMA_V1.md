# MODULE FREEZE CONTRACT SCHEMA V1

状态：ACTIVE。每个 `FROZEN` 模块必须有独立、版本化、可机读比对的冻结契约；未满足本 Schema 不得冻结。

## 必填头字段

`contractId`、`schemaVersion`、`moduleId`、`freezeVersion`、`status=FROZEN`、`userAcceptanceEvidence`、`lastVerifiedAt`、`registryVersion`、`sourceBaselineManifest`、`unfreezeStatus=LOCKED`。

## Frozen Core Contract

必须逐项固定：`businessObjects`、`canonicalNames`、`routes`、`menuPaths`、`formalComponents`、`formalApis`、`formalDataAuthorities`、`primaryBusinessIdentities`、`readPermissions`、`executePermissions`、`workflowContract`、`incomingRelationships`、`outgoingRelationships`、`criticalUiDataContract`、`goldenBusinessFacts`、`allowedExtensionPoints`、`sharedDependencies`、`regressionGates`。

每项至少含 expected value、证据路径、SHA-256 或稳定标识、验证方法、失败语义。菜单必须含角色、DOM 文案、层级、点击后 URL 和页面标题；API 必须含 method/path/schema/authority；数据必须含 DB/API/UI 同一 identity；权限必须区分 read 与 execute。

## 变更规则

任何 expected value 漂移、文件 SHA 漂移或共享依赖命中，必须输出 `FROZEN MODULE IMPACT DETECTED`。只有 Registry 中记录 `UNFREEZE_REQUESTED` 且附用户明确授权证据，才可进入修改；完成后必须全量复验、用户验收并形成新版本契约。无授权变更必须使保护 Gate 与 Build FAIL。

## 最小机器结构

```json
{
  "contractId": "MODULE_FREEZE_CONTRACT_<MODULE>_Vx",
  "schemaVersion": "1.0",
  "moduleId": "...",
  "freezeVersion": "...",
  "status": "FROZEN",
  "userAcceptanceEvidence": ["..."],
  "core": {
    "businessObjects": [], "canonicalNames": [], "routes": [], "menuPaths": [],
    "formalComponents": [], "formalApis": [], "formalDataAuthorities": [],
    "primaryBusinessIdentities": [], "readPermissions": [], "executePermissions": [],
    "workflowContract": {}, "incomingRelationships": [], "outgoingRelationships": [],
    "criticalUiDataContract": {}, "goldenBusinessFacts": [], "allowedExtensionPoints": [],
    "sharedDependencies": [], "regressionGates": []
  },
  "sourceBaselineManifest": "...",
  "unfreezeStatus": "LOCKED"
}
```
