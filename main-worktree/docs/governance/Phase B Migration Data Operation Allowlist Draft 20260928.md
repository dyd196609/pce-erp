# Migration Data Operation Allowlist Draft

> Source Commit: `969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`。本草案由Git对象级静态扫描生成；未导入Django、未连接数据库、未执行Migration。

## 1. 分类规则

- A：允许Replay执行。当前没有任何项目被自动归入A。
- B：需要人工确认并签署白名单后方可执行。
- C：禁止进入当前Replay目标集合。
- `Seed候选`与`权限候选`为静态特征识别结果，必须结合函数内容人工复核，不能替代签署。

## 2. 扫描摘要

- Migration总数：153
- 含RunPython：46
- 含RunSQL：1
- Seed候选：27
- 权限候选：19
- RunPython.noop候选：42

## 3. 全量候选清单

|Migration|RunPython|RunSQL|Seed|数据影响|权限影响|幂等要求|反向行为|风险等级|处理建议|分类|
|---|---:|---:|---:|---|---|---|---|---|---|---|
| `bank_send_execution_gate.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_execution_simulation.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_execution_simulation.0002_v65_simulation_audit_isolation_gate` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_execution_simulation.0003_v66_chain_trace_final_approval` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_execution_simulation.0004_v67_production_release_isolation` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_execution_simulation.0005_v68_execution_framework_design` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_preparation.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_request.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_task.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_task.0002_banksendtask_batch_id` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `bank_send_task.0003_banksendtaskcanarypoolentry` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `formal_payment_order.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `formal_payment_order.0002_formalpaymentorder_source_scenario_code` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `formal_payment_order.0003_formalpaymentorder_execution_gate` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `formal_payment_order.0004_state_consistency_contract` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0002_alter_materialcategory_options` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0003_materialcategory_parent` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0004_enterprise_procurement_dimensions_r4` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0005_project_selector_linkage_r5` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0006_price_approval_result_supplier_material_price_v45_8` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0007_supplier_material_price_manual_source_r5` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `masterdata.0008_material_supply_governance_a0` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0009_unit_and_code_governance_a1` | 是 | 是 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0010_material_unit_confirmation_a1_final` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0011_foundation_identity_uom_and_encoders` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | 非noop或待人工解析 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0012_standard_uom_initialization_v12` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | 非noop或待人工解析 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `masterdata.0013_manufacturing_plant_phase_a` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `mes.0001_manufacturing_domain_foundation_phase_a` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payable_confirmation_prepare.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_instruction_prepare.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_instruction_prepare.0002_state_machine_semantics` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `payment_order_draft.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_order_draft.0002_state_machine_semantics` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `payment_order_prepare.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_order_prepare.0002_state_machine_semantics` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `payment_request.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_request.0002_state_machine_semantics` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `payment_request_prepare.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_risk_review.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `payment_risk_review.0002_paymentriskreview_scenario_code` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0002_pde_emd_relationships` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0003_pde_version_governance` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0004_pde_manufacturing_output` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0005_product_engineering_readiness` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0006_production_master_data_a1` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0007_production_master_permissions_and_codes_a1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0008_engineering_fact_source_a15` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0009_stable_business_references_a15` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0010_engineering_permissions_a15` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0011_plan_operator_engineering_authority_a15` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0012_engineeringbreakdownitem_and_more` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0013_production_unified_model_permissions_a17` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0014_alter_productcategory_industry_type` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0015_standard_capacity_measurement_status_a1_final` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0016_a1_final_industry_semantics` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0017_engineering_rule_foundation_do2` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0018_engineering_calculation_closure_do3` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0019_manufacturing_structure_wave2` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0020_group3_transition_mode_override` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0021_group3a_operation_executor_authority` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | 非noop或待人工解析 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0022_manufacturing_definition_applicability` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0023_order_engineering_calculation_bom_closure` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0024_engineering_breakdown_option` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0025_order_cross_functional_review` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0026_order_review_itemized` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0027_order_review_participant_grant` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0028_product_design_plan_content_completion` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pde.0029_product_design_plan_group_scope` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0030_order_engineering_baseline` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `pde.0031_operation_time_standard_phase_a_rebased` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pfm.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `pfm.0002_employee_formal_organization_relations` | 是 | 否 | 否 | 组织关系绑定；当前要求重新设计 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 高 | 禁止进入当前Replay；等待受控新设计 | **C** |
| `pfm.0003_enterprise_organization_model_v1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `planning.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `planning.0002_planning_access_workflow_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `planning.0003_demand_sales_order_source` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `planning.0004_engineering_and_plan_compatibility_a15` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `planning.0005_order_planning_chain_v1` | 是 | 否 | 候选 | MPS/MRP角色及权限seed；已排除 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 高 | 禁止进入当前Replay；保留记录 | **C** |
| `planning.0006_material_plant_profile_phase_a` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0002_purchaseorder_department` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0003_purchaseorder_require_department` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0004_purchaseorder_purchase_department` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0005_scm_business_object_recovery_v1142813` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0006_purchase_request_lifecycle_v1142142` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0007_purchase_request_smart_form_r3` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0008_purchase_request_enterprise_model_r4` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0009_purchase_request_business_flow_r7` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0010_supplier_quotation_v11428422` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0011_quote_comparison_fact_v11428423_r5` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0012_price_approval_preparation_v11428424` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0013_price_approval_legacy_projection_v11428424_r3` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0014_price_approval_projection_snapshot_v11428424_r3` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0015_price_approval_review_result_v11428424_r23` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0016_supplier_master_completeness_v11428427227` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `procurement.0017_supplier_category_classification_v11428427227` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `procurement.0018_supplier_delivery_address_v11428427228` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `procurement.0019_supplier_master_reverse_enrichment_v1142842724511` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0020_standard_purchase_price_link_v46_batch2` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0021_purchase_mode_entry_v46_batch22_r1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0022_direct_price_source_trace_v46_batch22_r2` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0023_purchase_order_buyer_employee_r5` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0024_purchase_fulfillment_inventory_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `procurement.0025_purchase_request_purchase_plan_source_v1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0026_location_lot_identity_a1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0027_inventory_dimensions_a15` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `procurement.0028_completed_module_read_permissions` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | 非noop或待人工解析 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `purchase.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase.0002_alter_purchaseorder_options_and_more` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase_accounts_payable_draft.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase_canary.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase_canary.0002_purchasecanarylineage` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase_invoice_prepare.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `purchase_invoice_prepare.0002_legalentityinvoiceauthorityrecord_and_more` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `reconciliation.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `reconciliation.0002_payablecheckauthorityrecord_and_more` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `reconciliation.0003_businessdocumentnumberreservation_reusable` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `sales.0001_initial` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `sales.0002_sales_order_engineering_refs_a15` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `sales.0003_industrial_order_engineering_input_do1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `sales.0004_order_operating_system_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `sales.0005_sales_order_item_tax_snapshot` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0002_v82_difference_collaboration` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0003_v83_payable_payment_request` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0004_v831_workflow_actions` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0005_v84_payment_status_closed_loop` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `supplier_performance.0006_formal_supplier_settlement_14_22_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0002_permission_role_rolepermission` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0003_menu_rolemenu` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0004_erp_access_foundation` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0005_organization_access_core_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0006_enterprise_organization_model_v1` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0007_remove_department_cost_center_and_more` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 有候选；须逐项确认 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0008_position_effective_period` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0009_responsibility_lifecycle_v1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0010_positionworkflowresponsibility_workflow_node` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0011_process_operation_governance_a1` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0012_remove_process_system_process_standard_hours_nonnegative_and_more` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0013_process_workshop_a1_final` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0014_workshop_encoder_and_operation_measurement` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0015_process_default_transition_mode` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `system.0016_process_display_order` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `system.0017_team_operation_capability` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `workflow_runtime.0001_initial` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `workflow_runtime.0002_business_state_transition` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `workflow_runtime.0003_transition_fact_integrity` | 是 | 否 | 否 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `workflow_runtime.0004_payment_chain_transition_backfill` | 是 | 否 | 候选 | 有；函数级范围待白名单复核 | 未发现显式权限数据操作 | 必须证明 | noop；须接受残留/补偿合同 | 中/高，待评审 | 人工审查函数、对象、幂等与反向后再签署 | **B** |
| `workflow_runtime.0005_workflownodedefinition_and_more` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |
| `workflow_runtime.0006_merge_formal_definitions_and_payment_backfill` | 否 | 否 | 否 | 未发现显式数据操作 | 未发现显式权限数据操作 | N/A（静态结构） | N/A | 低/中，目标集合仍待签署 | 仅Schema操作；仍不得自动归A | **B** |

## 4. 特别排除记录

- `planning.0005_order_planning_chain_v1`：C类。创建MPS/MRP结构并执行角色/权限seed，reverse为noop；已由admin签署排除当前Target Schema。
- `planning.0006_material_plant_planning_profile`：固定Source Commit中不存在；当前收敛证据要求重新设计对0005的依赖，未获独立授权前按C类边界处理。
- `pfm.0002_employee_formal_organization_relations`：C类。admin已签署`REDESIGN REQUIRED`，当前文件不得进入Replay目标集合。

## 5. 白名单签署区

|字段|内容|
|---|---|
|Approved A Items|  |
|Approved RunPython|  |
|Approved RunSQL|  |
|Approved Seed/Permission Seed|  |
|Idempotency Evidence|  |
|Reverse/Residual Contract|  |
|Signer|  |
|Date|  |

当前没有任何项目进入A类，R5保持`BLOCKED`。

