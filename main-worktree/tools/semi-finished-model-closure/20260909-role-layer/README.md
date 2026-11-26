# 半成品材料角色层级纠正候选包

状态：ISOLATED TESTED / NOT PRODUCTION APPLIED。

本包保留原pde唯一模型及原db_table，在上一轮0024/0025候选基础上增加隔离0026。原20260909包不覆盖、不修改。

- 配置：坯板、木皮、表面/工艺耗材三个CALCULATED角色；移出EDGE及OTHER_FIXED。
- 组件：原EngineeringBreakdownItem增加唯一来源行origin；原ComponentMaterialRequirement接入该组件owner，保留既有OrderProductComponent owner。
- 材料身份、数量方式、规则状态相互独立；NULL不是0或1。
- 三合一L列是精确板材匹配输入；采购允许成员未确认仍阻断。粗略BOM只作结构参考。

MANIFEST逐文件记录testedSha256与deliveredSha256；canonical-models.patch只做git apply --check，未应用生产。
不提供生产apply runner。未来生产应用需单独授权，重新检查生产模型基线、数据库schema、外键、来源身份及发布规则，不能直接执行本包迁移。

证据根目录：D:\Dev-PCE\Source\docs\evidence\semi_finished_role_layer_20260909。
Replay：232个隔离对象（2配置、16属性、71来源引用、6角色、71来源组件、59未决封边需求及7个保留支撑对象）。
Round-trip和Rollback在独立副本执行；正式DB和业务数据未变。新层级UI待用户人工验收。
