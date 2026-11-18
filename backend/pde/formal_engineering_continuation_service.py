"""Formal multi-object continuation for the accepted engineering calculator.

The module is intentionally an adapter, not a second calculator.  Numeric work
continues to be performed by ``calculation_batch_reuse.run_batch`` which calls
the governed Decimal engine in ``engineering_rule_foundation``.  This service
adds the missing server-validated baseline, object scope, persistence and audit
contracts without adding a model or migration.
"""

from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from hashlib import sha256
import json
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from masterdata.models import CodeRule, UnitOfMeasure
from sales.models import SalesOrderItem
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .calculation_batch_reuse import run_batch
from .baseline_source_identity import resolve_baseline_source_identity
from .engineering_calculation_service import (
    EngineeringCalculationError,
    EngineeringCalculationService,
    serialize_calculation,
)
from .engineering_rule_foundation import specification_hash
from .formal_calculation_readback import summarize_formal_calculations
from .crm_order_admission import CRMOrderAdmissionError, require_crm_order_admission, require_current_order_admission
from .models import (
    EngineeringBreakdownOption,
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringRuleDefinition,
    ManufacturingProcessType,
    LegacyInFlightOrderAdoption,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ProductCategory,
    ProductDesignItem,
    ProductManufacturingOutput,
    ProductionPlanOperationRequirementAllocation,
)
from .production_foundation_service import (
    EngineeringLifecycleService,
    ProductionFoundationService,
    _actor_chain,
    _audit,
    _snapshot,
)


FORMAL_RULE_PACKAGES = {
    "APPROVED_SOURCE_NET": {
        "version": "V1",
        "name": "既有工程净量正式规则包",
        "adapter": "backend.pde.calculation_batch_reuse.evaluate_row",
        "resultScope": "original",
        "businessExplanation": {
            "purpose": "把已确认工程基线中的对象尺寸、数量、工艺、见光和封边条件转换为可追溯的工程净量。",
            "applicableObjects": ["三合一生产单受控分支", "房门单开门／单面套受控分支"],
            "excludedObjects": ["尚未完成受控适配的结构分支", "负尺寸或负数量", "缺少必填工艺、见光或封边条件的对象"],
            "inputs": [
                {"name": "对象尺寸", "technicalName": "J／K／L", "unit": "mm", "description": "来源对象的受治理尺寸输入。"},
                {"name": "来源数量", "technicalName": "M", "unit": "来源单位", "description": "保留来源数量及其单位，不猜测单位。"},
                {"name": "结构与油漆工艺", "technicalName": "H／I", "unit": "条件", "description": "用于选择房门受控计算分支。"},
                {"name": "见光与封边条件", "technicalName": "O／P", "unit": "条件", "description": "用于决定适用的见光面积和封边结果。"},
            ],
            "calculationRelations": [
                "三合一分支按来源尺寸、数量、见光条件和封边方式生成对应部件净量。",
                "房门分支按单开门／单面套结构和油漆工艺逐步形成门套、门扇尺寸及面积、长度和数量结果。",
                "各对象实际表达式、输入和来源单元格保存在正式核算明细中；登记包装表达式不替代这些逐结果表达式。",
            ],
            "outputs": [
                {"name": "部件及门套／来源数量", "technicalName": "按对象分支", "unit": "来源数量单位"},
                {"name": "工程净面积、见光面积、门套净面积", "technicalName": "按对象分支", "unit": "m²"},
                {"name": "结构封边及封边皮净长度", "technicalName": "封边皮25／50等", "unit": "m"},
                {"name": "门套和门扇尺寸", "technicalName": "按对象分支", "unit": "mm"},
            ],
        },
    },
    "SOURCE_LINEAR_CONTINUATION": {
        "version": "V1",
        "name": "既有线条延续正式规则包",
        "adapter": "backend.pde.calculation_batch_reuse.evaluate_linear_row",
        "resultScope": "linear-continuation",
        "businessExplanation": {
            "purpose": "根据房门工程对象的基准尺寸、横竖加量、单双和数量，形成六项受治理线条结果。",
            "applicableObjects": ["房门来源行", "具备门洞／门套基准尺寸及横加、竖加、单双和数量条件的对象"],
            "excludedObjects": ["非房门来源行", "缺少基准尺寸、横加／竖加、单双或数量的对象", "净长超过3600mm且没有受治理开料档位的对象"],
            "inputs": [
                {"name": "门洞／门套基准高宽", "technicalName": "基准尺寸", "unit": "mm", "description": "线条净长计算的受治理基准。"},
                {"name": "竖加", "technicalName": "AP", "unit": "mm", "description": "竖向线条尺寸增量。"},
                {"name": "横加", "technicalName": "AO", "unit": "mm", "description": "横向线条尺寸增量。"},
                {"name": "线条单双", "technicalName": "AZ", "unit": "条件", "description": "决定线条条数分支。"},
                {"name": "来源数量", "technicalName": "M", "unit": "来源单位", "description": "用于形成横竖线条条数。"},
            ],
            "calculationRelations": [
                "AT／AU分别形成竖线和横线净长，AW／AY形成对应条数。",
                "AV／AX在净长基础上按2440、2600、2800、3050、3600mm受治理档位形成开料长。",
                "缺少上游净长或超过最大档位时保持缺项，不猜测开料长度。",
            ],
            "outputs": [
                {"name": "竖线净长", "technicalName": "AT", "unit": "mm"},
                {"name": "横线净长", "technicalName": "AU", "unit": "mm"},
                {"name": "竖线开料长", "technicalName": "AV", "unit": "mm"},
                {"name": "横线开料长", "technicalName": "AX", "unit": "mm"},
                {"name": "竖线条数", "technicalName": "AW", "unit": "条"},
                {"name": "横线条数", "technicalName": "AY", "unit": "条"},
            ],
        },
    },
}


CANONICAL_BUSINESS_NAMES = {
    "opening_height": "门洞高度",
    "opening_width": "门洞宽度",
    "casing_height": "门套高度",
    "casing_width": "门套宽度",
    "door_height": "门扇高度",
    "door_width": "门扇宽度",
    "SOURCE_VALUE": "对象级受治理输入",
    "result": "逐对象派生工程量",
}

UNIT_DIMENSION_LABELS = {
    "length": "长度",
    "area": "面积",
    "count": "数量",
    "dimensionless": "无量纲／由对象分支确定",
}


def _business_field(field):
    technical_name = str(field.get("canonicalName") or "")
    chinese_name = CANONICAL_BUSINESS_NAMES.get(technical_name)
    return {
        "name": chinese_name or f"{technical_name or '未命名字段'}（中文含义待确认）",
        "technicalName": technical_name or "未提供",
        "unit": field.get("unit") or UNIT_DIMENSION_LABELS.get(field.get("unitDimension"), "按正式定义"),
        "description": field.get("description") or "以当前正式规则定义为准。",
    }


def formal_rule_business_explanation(*, rule_code, rule_name, version, specification, status=None):
    """Project one governed specification into a read-only Chinese employee view."""
    specification = specification if isinstance(specification, dict) else {}
    package = FORMAL_RULE_PACKAGES.get(rule_code)
    if package and version == package["version"]:
        blueprint = next(row for row in formal_rule_blueprints() if row["rule_code"] == rule_code)
        if specification_hash(specification) == specification_hash(blueprint["specification"]):
            explanation = dict(package["businessExplanation"])
            explanation["explanationScope"] = "既有受治理方案完整中文说明"
        else:
            explanation = {}
    else:
        explanation = {}
    inputs = [_business_field(row) for row in specification.get("inputs", []) if isinstance(row, dict)]
    outputs = [_business_field(row) for row in specification.get("outputs", []) if isinstance(row, dict)]
    if not explanation:
        output_name = outputs[0]["name"] if outputs else "规则结果"
        expression = str(specification.get("expression") or "未提供受控表达式")
        explanation = {
            "explanationScope": "根据当前正式定义可解释的字段；未识别技术字段已明确标记待确认",
            "purpose": f"当前规则“{rule_name or rule_code}”用于形成{output_name}。",
            "applicableObjects": [
                f"正式适用范围：{specification.get('applicability', {}).get('scope') or '当前定义未提供'}",
                "其它适用条件以当前正式定义中的applicability为准。",
            ],
            "excludedObjects": ["不满足当前正式定义适用条件或缺少必填输入的对象。"],
            "inputs": inputs,
            "calculationRelations": [f"{output_name}按受控表达式“{expression}”计算；技术标识保留用于追溯。"],
            "outputs": outputs,
        }
    explanation.update({
        "missingCondition": "任一必填输入或适用条件缺失时保留缺项（value=null），不得用0冒充已计算结果。",
        "precisionRule": (
            f"Decimal精度{specification.get('decimalPrecision', '按正式定义')}，"
            f"输出小数位{specification.get('outputScale', '按正式定义')}，"
            f"舍入方式{specification.get('roundingMode', '按正式定义')}。"
        ),
        "versionRule": (
            f"当前版本{version or '未提供'}；已发布定义不可直接修改，只能通过受控版本动作形成后续版本。"
            if status == "released" else
            f"登记版本{version or '未提供'}；保存后仍须按现有状态机评审和发布。"
        ),
        "technicalTrace": {
            "ruleCode": rule_code,
            "version": version,
            "executionAdapter": specification.get("executionAdapter") or "当前定义未提供执行适配器",
            "expression": specification.get("expression") or "当前定义未提供包装表达式",
            "specificationHash": specification_hash(specification),
        },
    })
    return explanation


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


_NO_WORKBOOK_INPUT = object()


def calculation_input_hash(baseline_reference, objects, *, workbook_source=_NO_WORKBOOK_INPUT):
    """One input envelope for native writes and fixed-version proof readers.

    Absence is the original contract. A present proof must identify the known
    workbook contract; None/unknown contracts must never fall back to legacy.
    Source publication and frozen object validation remain independent gates.
    """
    envelope = {'baseline': baseline_reference, 'objects': objects}
    if workbook_source is not _NO_WORKBOOK_INPUT:
        from .engineering_workbook_source_service import CONTRACT
        if not isinstance(workbook_source, dict) or workbook_source.get('contractVersion') != CONTRACT:
            raise EngineeringCalculationError('CALCULATION_INPUT_CONTRACT_UNPROVEN',
                '核算输入包含未知或缺失的工作簿来源证明合同。')
        envelope['workbookSource'] = workbook_source
    return _hash(envelope)


def formal_rule_blueprints():
    """Return explicit payloads for the normal rule create/review/release service."""
    blueprints = []
    for code, package in FORMAL_RULE_PACKAGES.items():
        blueprints.append({
            "company_id": None,
            "rule_code": code,
            "rule_name": package["name"],
            "version": package["version"],
            "rule_kind": "formula",
            "specification": {
                "rulePackage": {"code": code, "version": package["version"]},
                "executionAdapter": package["adapter"],
                "expression": "SOURCE_VALUE",
                "inputs": [{
                    "canonicalName": "SOURCE_VALUE",
                    "description": "对象级原实现受治理输入",
                    "valueType": "decimal",
                    "unitDimension": "dimensionless",
                    "unitRequired": False,
                    "sourceType": "ENGINEERING_INPUT",
                    "required": True,
                }],
                "outputs": [{
                    "canonicalName": "result",
                    "description": "逐对象派生工程量（实际字段见计算明细）",
                    "valueType": "decimal",
                    "unitDimension": "dimensionless",
                    "unit": None,
                    "resultDomain": "DERIVED_FACT",
                }],
                "dependencies": [],
                "decimalPrecision": 28,
                "outputScale": 6,
                "roundingMode": "ROUND_HALF_UP",
                "sourceEvidence": {
                    "reference": package["adapter"],
                    "acceptedRuleIdentity": f"{code}@{package['version']}",
                },
                "applicability": {
                    "scope": "order_engineering",
                    "objectAuthority": "OrderEngineeringBaselineItem.content_snapshot",
                    "resultScope": package["resultScope"],
                },
            },
        })
    return blueprints


def formal_rule_registration_materials():
    """Return read-only registration material derived from the executable package contract.

    These rows are deliberately not model instances and carry no lifecycle status.  They
    let the existing rule page explain what still needs to be registered without creating
    a draft or consulting order/calculation facts.
    """
    return [
        {
            "materialType": "ENGINEERING_RULE_REGISTRATION_CANDIDATE",
            "registrationStatus": "NOT_REGISTERED_MATERIAL",
            "registrationStatusLabel": "待登记材料，尚未形成正式规则",
            "ruleCode": blueprint["rule_code"],
            "ruleName": blueprint["rule_name"],
            "version": blueprint["version"],
            "ruleKind": blueprint["rule_kind"],
            "specification": blueprint["specification"],
            "specificationHash": specification_hash(blueprint["specification"]),
            "executionAdapter": blueprint["specification"]["executionAdapter"],
            "applicability": blueprint["specification"]["applicability"],
            "dependencies": blueprint["specification"]["dependencies"],
            "inputs": blueprint["specification"]["inputs"],
            "outputs": blueprint["specification"]["outputs"],
            "businessExplanation": formal_rule_business_explanation(
                rule_code=blueprint["rule_code"],
                rule_name=blueprint["rule_name"],
                version=blueprint["version"],
                specification=blueprint["specification"],
            ),
        }
        for blueprint in formal_rule_blueprints()
    ]


def _package_rules(company_id, rule_ids=None):
    queryset = EngineeringRuleDefinition.objects.filter(
        company_id=company_id,
        rule_code__in=FORMAL_RULE_PACKAGES,
    )
    if rule_ids is not None:
        try:
            requested = [int(value) for value in rule_ids]
        except (TypeError, ValueError):
            raise EngineeringCalculationError("RULE_SET_REQUIRED", "正式规则ID必须为整数。")
        if len(requested) != len(set(requested)):
            raise EngineeringCalculationError("RULE_SET_REQUIRED", "正式规则ID不得重复。")
        queryset = queryset.filter(pk__in=requested)
    rows = list(queryset.order_by("rule_code", "version", "pk"))
    by_code = {row.rule_code: row for row in rows if row.status == "released"}
    missing = [code for code in FORMAL_RULE_PACKAGES if code not in by_code]
    if missing:
        raise EngineeringCalculationError(
            "FORMAL_RULE_PACKAGES_NOT_RELEASED",
            "既有核算规则包尚未通过正式规则服务发布。",
            {"missingRulePackages": missing},
        )
    if rule_ids is not None and len(rows) != len(rule_ids):
        raise EngineeringCalculationError(
            "RULE_SET_MISMATCH", "所选规则必须且只能是本次正式接续的两个已发布规则包。"
        )
    for code, rule in by_code.items():
        expected = FORMAL_RULE_PACKAGES[code]
        specification = rule.specification if isinstance(rule.specification, dict) else {}
        package = specification.get("rulePackage") or {}
        applicability = specification.get("applicability") or {}
        if (
            rule.version != expected["version"]
            or package.get("code") != code
            or package.get("version") != expected["version"]
            or specification.get("executionAdapter") != expected["adapter"]
            or applicability.get("scope") != "order_engineering"
        ):
            raise EngineeringCalculationError(
                "FORMAL_RULE_PACKAGE_CONTRACT_MISMATCH",
                "正式规则定义与已验收原实现映射不一致。",
                {"ruleId": rule.pk, "ruleCode": code},
            )
    return by_code


def _baseline_reference(baseline, items, *, read_cache=None):
    # The header hash represents the complete order baseline, while ``items`` is
    # deliberately only the current instance subset. Rebuild the header hash in
    # the same order used by ProductVersionManagementService when the baseline
    # was saved; never compare a 5/3/62/1 subset hash with the 71-object header.
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, baseline.company_id)
    ordered_hashes = _read_once(cache, ('baseline_complete_item_hashes', baseline.company_id, baseline.pk), lambda: list(
        baseline.items
        .order_by("design_item__sales_order_item__line_no", "source_attribute_id", "design_item_id", "pk")
        .values_list('content_hash', flat=True)
    ))
    recalculated_snapshot_hash = _hash(ordered_hashes)
    if recalculated_snapshot_hash != baseline.snapshot_hash:
        raise EngineeringCalculationError(
            "BASELINE_SNAPSHOT_HASH_MISMATCH",
            "基线明细哈希与基线头记录不一致，已停止执行。",
            {"saved": baseline.snapshot_hash, "actual": recalculated_snapshot_hash},
        )
    if baseline.scope_item_count != len(ordered_hashes):
        raise EngineeringCalculationError(
            "BASELINE_SCOPE_COUNT_MISMATCH", "基线保存范围与实际明细数量不一致。"
        )
    return {
        "id": baseline.pk,
        "baselineNo": baseline.baseline_no,
        "status": baseline.status,
        "orderId": baseline.sales_order_id,
        "orderNo": baseline.sales_order.order_no,
        "itemCount": baseline.scope_item_count,
        "candidateHash": baseline.candidate_hash,
        "snapshotHash": baseline.snapshot_hash,
        "selectedItemCount": len(items),
        "selectedItemHash": _hash([{
            "designItemId": row.design_item_id,
            "sourceAttributeId": row.source_attribute_id,
            "contentHash": row.content_hash,
        } for row in items]),
    }


def _snapshot_design_input(item):
    snapshot = item.content_snapshot if isinstance(item.content_snapshot, dict) else {}
    design = snapshot.get("designItem") if isinstance(snapshot.get("designItem"), dict) else {}
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    revision = snapshot.get("revision") if isinstance(snapshot.get("revision"), dict) else {}
    existing = design.get("existingDesignData") if isinstance(design.get("existingDesignData"), dict) else {}
    design_data = revision.get("designData") if isinstance(revision.get("designData"), dict) else {}
    identity = resolve_baseline_source_identity(item)
    effective = {**existing, **design_data}
    edge_name = str(effective.get("edgeMethod") or "")
    if not edge_name and revision.get("edgeMethodId"):
        option = EngineeringBreakdownOption.objects.filter(pk=revision["edgeMethodId"]).only("name").first()
        edge_name = option.name if option else ""
    return {
        "baselineItemId": item.pk,
        "baselineContentHash": item.content_hash,
        "designItemId": item.design_item_id,
        "designItemNo": item.item_no_snapshot,
        "sourceAttributeId": item.source_attribute_id,
        "sourceRecordId": item.source_record_id,
        "sourceSheet": identity["sourceSheet"],
        "sourceRow": identity["sourceRow"],
        "sourceKey": identity["sourceKey"],
        "sourceIdentity": identity,
        "nativeCalculationInputs": design_data.get("calculationInputs"),
        "revision": revision.get("revision"),
        "designLength": revision.get("designLength") if revision else effective.get("designLength"),
        "designWidth": revision.get("designWidth") if revision else effective.get("designWidth"),
        "designThickness": revision.get("designThickness") if revision else effective.get("designThickness"),
        "designUomId": revision.get("designUomId"),
        "physicalQuantity": design.get("physicalQuantity"),
        "physicalUomId": design.get("physicalUomId"),
        "physicalUom": design.get("physicalUom"),
        "productCategoryId": design.get("productCategoryId"),
        "productDefinitionId": design.get("productDefinitionId"),
        "materialId": revision.get("materialId"),
        "materialProcessTypeId": revision.get("materialProcessTypeId"),
        "paintProcessTypeId": revision.get("paintProcessTypeId"),
        "edgeMethodId": revision.get("edgeMethodId"),
        "edgeMethod": edge_name,
        "visibleCondition": effective.get("visibleCondition") or "",
        "finishOrColor": effective.get("finishOrColor") or "",
        "paintProcess": effective.get("paintProcess") or "",
        "routingProcessCode": existing.get("routingProcessCode") or "",
        "processConfigurationCode": effective.get("processConfigurationCode") or existing.get("routingProcessCode") or "",
        "inputAuthority": "CONFIRMED_ORDER_ENGINEERING_BASELINE_ITEM",
        "sourceVersion": item.source_version_snapshot,
        "sourceContentHash": item.source_content_hash_snapshot,
    }


def _calculation_has_fixed_consumers(calculation):
    """A successor is a new version, not revocation of a consumed version."""
    if ProductManufacturingOutput.objects.filter(engineering_calculation_id=calculation.pk).exists():
        return True
    return ProductionPlanOperationRequirementAllocation.objects.filter(
        company_id=calculation.company_id,
    ).filter(
        Q(operation_requirement__source_calculation_id=calculation.pk)
        | Q(operation_requirement__source_calculation__origin_calculation_id=calculation.pk)
        | Q(operation_requirement__calculation_id=calculation.pk)
    ).exists()


def _retire_unconsumed_calculation(previous, calculation, *, user, decision, execution_chain):
    """Retire only unconsumed revisions; an output/allocation pins its source."""
    if previous and previous.status == "completed" and not _calculation_has_fixed_consumers(previous):
        previous_audit = _audit(
            user=user, organization_id=user.company_id,
            action_code="production.engineering.calculation.execute",
            instance=previous, before=_snapshot(previous),
            after={**_snapshot(previous), "status": "superseded", "supersededById": calculation.pk},
            reason="新基线、对象输入或规则版本形成后续核算修订",
            authorization=decision, execution_chain=execution_chain,
        )
        transition_business_object(
            business_object=previous, object_type="EngineeringCalculationRecord",
            source_state="completed", target_state="superseded",
            action_code="production.engineering.calculation.execute", operator=user,
            reason="新核算修订已完成；旧结果保留并失效",
            audit_reference=f"OrganizationOperatingAuditRecord:{previous_audit.pk}",
            allowed_transitions=(("completed", "superseded"),), version_field=None,
        )
        EngineeringDerivedFact.objects.filter(calculation=previous, status="active").update(status="superseded")


def _guard_consumed_legacy_revision(previous, *, sales_item, instance, baseline, company_id, continuation_record=None, user=None, workbook_source_context=None):
    """A new completed main record must not invalidate a fixed legacy scope."""
    if previous is None:
        return
    if continuation_record is not None:
        from .engineering_calculation_continuation_service import validate_pending_authority
        validate_pending_authority(continuation_record,previous=previous,sales_item=sales_item,
            instance=instance,baseline=baseline,company_id=company_id,user=user,workbook_source_context=workbook_source_context)
        return
    adoption = LegacyInFlightOrderAdoption.objects.filter(company_id=company_id,
        sales_order_id=sales_item.sales_order_id).values("pk", "adoption_no", "evidence_snapshot__scope").first()
    if not adoption:
        return
    frozen_scope = adoption["evidence_snapshot__scope"] or {}
    fixed_by_adoption = previous.pk in (frozen_scope.get("engineeringCalculationIds") or [])
    if not fixed_by_adoption and not _calculation_has_fixed_consumers(previous):
        return
    try:
        require_current_order_admission(order=sales_item.sales_order, lock=True,
            sales_order_item_id=sales_item.pk, engineering_instance_id=instance.pk,
            calculation_id=previous.pk)
    except CRMOrderAdmissionError as error:
        raise EngineeringCalculationError(error.code, error.message, error.details) from error
    raise EngineeringCalculationError("LEGACY_MAIN_CALCULATION_CONTINUATION_REQUIRED",
        "当前历史承接范围仍固定原主核算；尚无正式的新主核算准入接续，已在任何新核算写入前停止。",
        {"legacyAdoptionId": adoption["pk"], "legacyAdoptionNo": adoption["adoption_no"],
         "frozenScope": frozen_scope, "previousCalculationId": previous.pk,
         "requestedBaselineId": baseline.pk, "businessWriteSideEffectCount": 0})


def native_successor_proof(previous, current, *, company_id, item_id, instance_id):
    """Read the native non-legacy successor that this calculator already writes.

    Legacy adoption continues to require its original 0046 authority. This is
    recognition of actual immutable native facts, not a caller-supplied proof
    or an alternate calculator/version workflow.
    """
    from .engineering_calculation_continuation_service import _main_proof
    from .baseline_usage_service import validate_baseline
    from workflow_runtime.models import BusinessStateTransition
    from system.models import OrganizationOperatingAuditRecord
    if (LegacyInFlightOrderAdoption.objects.filter(company_id=company_id,
            sales_order_id=current.sales_order_item.sales_order_id).exists()
        or current.supersedes_id!=previous.pk or current.revision!=previous.revision+1
        or any(row.company_id!=company_id or row.sales_order_item_id!=item_id
            or row.engineering_instance_id!=instance_id for row in (previous,current))
        or previous.source_record_id!=current.source_record_id
        or not ProductManufacturingOutput.objects.filter(engineering_calculation_id=previous.pk).exists()):
        raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN',
            '原生接续必须是同企业、同订单行、同实例的准确已消费前驱；历史承接仍须原0046合同。')
    proofs=[];baseline_ids=[]
    action='production.engineering.calculation.execute'
    for calculation in (previous,current):
        proof=_main_proof(calculation)
        trace=calculation.trace or {};reference=trace.get('baselineReference') or {}
        baseline=OrderEngineeringBaseline.objects.filter(pk=reference.get('id'),
            company_id=company_id,sales_order_id=calculation.sales_order_item.sales_order_id).first()
        if not baseline:
            raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','原生主核算缺少准确冻结基线。')
        validate_baseline(baseline)
        _,_,_,_,_,actual_reference=_resolve_context(company_id=company_id,sales_order_item_id=item_id,
            engineering_instance_id=instance_id,baseline_id=baseline.pk,lock=False)
        source=calculation.source_record
        if (reference!=actual_reference or source.status!='confirmed'
            or trace.get('sourceReference')!={'id':source.pk,'sourceNo':source.source_no,
                'sourceVersion':source.source_version,'contentHash':source.content_hash}
            or not isinstance(trace.get('objectInputSnapshot'),list)
            or calculation_input_hash(reference,trace['objectInputSnapshot'],
                **({'workbook_source':trace['workbookSource']} if 'workbookSource' in trace else {}))!=calculation.input_hash):
            raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','原生主核算冻结输入、来源版本或基线已变化。')
        events=list(BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',
            object_id=calculation.pk).order_by('pk'))
        if len(events)!=1 or (events[0].source_state,events[0].target_state,events[0].action_code)!=('running','completed',action):
            raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','原生主核算缺少唯一合法完成转换。')
        event=events[0]
        if not re.fullmatch(r'OrganizationOperatingAuditRecord:[1-9][0-9]*',event.audit_reference or ''):
            raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','原生主核算审计引用无效。')
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=int(event.audit_reference.split(':')[-1]),
            organization_id=company_id,target_type='EngineeringCalculationRecord',target_id=calculation.pk,
            action_code=action,actor_id=event.operator_id).first()
        state=(audit.after_snapshot or {}).get('state',{}) if audit else {}
        authority=(audit.after_snapshot or {}).get('authorization',{}) if audit else {}
        if (not audit or not authority.get('allowed') or action not in authority.get('permissionCodes',[])
            or state.get('status')!='completed' or state.get('inputHash')!=calculation.input_hash
            or state.get('resultHash')!=calculation.result_hash):
            raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','原生主核算缺少一致的权限、状态及完成审计。')
        proofs.append({**proof,'auditId':audit.pk,'stateTransitionId':event.pk,'baselineId':baseline.pk})
        baseline_ids.append(baseline.pk)
    if baseline_ids[0]==baseline_ids[1]:
        raise EngineeringCalculationError('NATIVE_MAIN_SUCCESSOR_UNPROVEN','新版必须有独立新冻结基线，不得重标旧核算。')
    return {'contractVersion':'PCE-NATIVE-MAIN-SUCCESSOR-PROOF-V1','authority':'FormalEngineeringContinuationService native audited successor',
        'previousCalculationId':previous.pk,'newCalculationId':current.pk,'mainProofs':proofs,
        'predecessorCalculationId':previous.pk,'orderEngineeringInstanceId':instance_id,
        'companyId':company_id,'salesOrderItemId':item_id,'engineeringInstanceId':instance_id,
        'legacyAdoptionRequired':False,'businessWriteCount':0}


def _resolve_context(*, company_id, sales_order_item_id, engineering_instance_id, baseline_id, lock=False):
    item_query = SalesOrderItem.objects.select_related("sales_order", "uom")
    instance_query = OrderEngineeringInstance.objects.select_related(
        "sales_order_item__sales_order", "source_record", "product_category", "selected_process_type"
    )
    baseline_query = OrderEngineeringBaseline.objects.filter(company_id=company_id).select_related("sales_order")
    if lock:
        item_query = item_query.select_for_update()
        instance_query = instance_query.select_for_update()
        baseline_query = baseline_query.select_for_update()
    sales_item = item_query.filter(pk=sales_order_item_id).first()
    instance = instance_query.filter(pk=engineering_instance_id).first()
    baseline = baseline_query.filter(pk=baseline_id).first()
    if not sales_item or not instance or not baseline:
        raise EngineeringCalculationError("FORMAL_CONTEXT_NOT_FOUND", "订单行、工程实例或基线不存在。")
    if (
        sales_item.sales_order.company_id != company_id
        or instance.company_id != company_id
        or baseline.company_id != company_id
        or instance.sales_order_item_id != sales_item.pk
        or baseline.sales_order_id != sales_item.sales_order_id
    ):
        raise EngineeringCalculationError(
            "FORMAL_CONTEXT_MISMATCH", "公司、订单、订单行、实例和基线不属于同一正式上下文。"
        )
    from .baseline_usage_service import validate_baseline
    from .product_design_service import ProductDesignError
    try:
        validate_baseline(baseline,purpose='PRODUCTION_USE')
    except ProductDesignError as error:
        raise EngineeringCalculationError(error.code,error.message,error.details) from error
    if baseline.status != "confirmed":
        raise EngineeringCalculationError("CONFIRMED_BASELINE_REQUIRED", "正式核算必须选择已确认工程基线。")
    if instance.source_record.status != "confirmed" or instance.status not in {"source_confirmed", "calculated", "released"}:
        raise EngineeringCalculationError("ORDER_ENGINEERING_SOURCE_NOT_READY", "来源或订单工程实例尚未确认。")
    baseline_items = list(
        baseline.items.select_related("design_item__sales_order_item__sales_order", "source_record", "source_attribute", "design_revision", "baseline")
        .filter(design_item__sales_order_item=sales_item)
        .order_by("source_attribute_id", "design_item_id", "pk")
    )
    if not baseline_items:
        raise EngineeringCalculationError("BASELINE_INSTANCE_SCOPE_EMPTY", "基线没有当前订单行实例的工程对象。")
    if any(row.source_record_id != instance.source_record_id for row in baseline_items):
        raise EngineeringCalculationError("BASELINE_SOURCE_MISMATCH", "基线对象来源与工程实例来源不一致。")
    design_inputs = [_snapshot_design_input(row) for row in baseline_items]
    if len({row["designItemId"] for row in design_inputs}) != len(design_inputs):
        raise EngineeringCalculationError("BASELINE_OBJECT_DUPLICATED", "实例基线子集包含重复工程对象。")
    baseline_ref = _baseline_reference(baseline, baseline_items)
    return sales_item, instance, baseline, baseline_items, design_inputs, baseline_ref


def _resolve_instance_identity(sales_item, *, instance=None):
    design_items = list(
        ProductDesignItem.objects.select_related("product_category", "source_record")
        .prefetch_related("design_revisions__material_process_type")
        .filter(company_id=sales_item.sales_order.company_id, sales_order_item=sales_item)
        .order_by("source_attribute_id", "pk")
    )
    if not design_items:
        raise EngineeringCalculationError("DESIGN_OBJECT_SCOPE_EMPTY", "订单行没有稳定工程对象。")
    source_ids = {row.source_record_id for row in design_items}
    category_ids = {row.product_category_id for row in design_items if row.product_category_id}
    process_ids = set()
    source_process_codes = set()
    for row in design_items:
        revisions = list(row.design_revisions.all())
        latest = max(revisions, key=lambda value: value.revision) if revisions else None
        if latest and latest.material_process_type_id:
            process_ids.add(latest.material_process_type_id)
        existing = row.existing_design_data if isinstance(row.existing_design_data, dict) else {}
        code = str(existing.get("routingProcessCode") or "").split("/", 1)[0].strip()
        if code:
            source_process_codes.add(code)
    if len(source_ids) != 1 or len(category_ids) != 1:
        raise EngineeringCalculationError(
            "INSTANCE_IDENTITY_NOT_UNIQUE", "订单行的来源或产品分类不能唯一确定。",
            {"sourceIds": sorted(source_ids), "productCategoryIds": sorted(category_ids)},
        )
    # A completed intake records the selected process on the instance. Optional
    # imported design fields must not be used to reconstruct that saved choice.
    # Keep the original derivation for new and incomplete legacy instances.
    if instance and instance.product_category_id and instance.selected_process_type_id:
        company_id = sales_item.sales_order.company_id
        if (
            instance.company_id != company_id
            or instance.sales_order_item_id != sales_item.pk
            or instance.source_record_id != next(iter(source_ids))
            or instance.product_category_id != next(iter(category_ids))
            or instance.source_record.company_id != company_id
            or instance.product_category.company_id != company_id
            or instance.selected_process_type.company_id != company_id
        ):
            raise EngineeringCalculationError(
                "INSTANCE_IDENTITY_MISMATCH", "已保存工程实例与当前订单行的公司、来源或产品分类不一致。",
                {"engineeringInstanceId": instance.pk, "salesOrderItemId": sales_item.pk},
            )
        return {
            "sourceRecordId": instance.source_record_id,
            "productCategoryId": instance.product_category_id,
            "selectedProcessTypeId": instance.selected_process_type_id,
            "designItems": design_items,
        }
    if len(process_ids) != 1:
        if len(source_process_codes) != 1:
            raise EngineeringCalculationError(
                "INSTANCE_PROCESS_NOT_UNIQUE", "订单行的正式工艺类型不能唯一确定。",
                {"processTypeIds": sorted(process_ids), "sourceProcessCodes": sorted(source_process_codes)},
            )
        process = ManufacturingProcessType.objects.filter(
            company_id=sales_item.sales_order.company_id,
            code=next(iter(source_process_codes)),
        ).first()
        if not process:
            raise EngineeringCalculationError("INSTANCE_PROCESS_NOT_FOUND", "来源工艺代码没有匹配正式工艺类型。")
        process_ids = {process.pk}
    return {
        "sourceRecordId": next(iter(source_ids)),
        "productCategoryId": next(iter(category_ids)),
        "selectedProcessTypeId": next(iter(process_ids)),
        "designItems": design_items,
    }


def _selected_workbook(company_id,workbook_source_record_id=None,workbook_source_context=None,baseline=None):
    if workbook_source_context is None and workbook_source_record_id is None:return None
    from .engineering_workbook_source_service import resolve_workbook_source,WorkbookSourceError
    reference=(workbook_source_context or {}).get('proof',{}).get('sourceRecordId')
    if workbook_source_record_id is not None and reference is not None and workbook_source_record_id!=reference:
        raise EngineeringCalculationError('WORKBOOK_SOURCE_CONTEXT_MISMATCH','工作簿来源选择与冻结上下文不一致')
    try:
        current=resolve_workbook_source(workbook_source_record_id if workbook_source_record_id is not None else reference,
            company_id=company_id,baseline=baseline)
    except WorkbookSourceError as error:
        raise EngineeringCalculationError(error.code,error.message,error.details) from error
    if workbook_source_context is not None and current['proof']!=workbook_source_context.get('proof'):
        raise EngineeringCalculationError('WORKBOOK_SOURCE_CONTEXT_CHANGED','工作簿或映射版本证明已变化')
    return current


def _preview_baseline_inputs(keys, design_inputs, workbook):
    source_rows=[row for row in design_inputs if row.get('sourceIdentity',{}).get('type')=='PCE_SOURCE_ROW_REVISION']
    if source_rows:
        if len(source_rows)!=len(design_inputs) or workbook is not None:
            raise EngineeringCalculationError('FORMAL_SOURCE_ROW_SCOPE_MIXED','本次来源行核算须完整同合同范围，不混用或替换Excel来源。')
        from .formal_source_row_calculation import preview
        return preview(source_rows)
    native = [row for row in design_inputs
              if row.get("sourceIdentity", {}).get("type") == "NATIVE_DESIGN_REVISION"]
    if native:
        from .native_design_calculation_adapter import preview_native_inputs
        preview = preview_native_inputs(native)
        imported = [row for row in design_inputs if row not in native]
        if imported:
            legacy = run_batch([row['sourceKey'] for row in imported], design_inputs=imported,
                               **({'workbook_source_context': workbook} if workbook else {}))
            preview['rows'].extend(legacy['rows'])
            preview['batchFingerprint'] = _hash([preview['batchFingerprint'], legacy['batchFingerprint']])
            preview['inputRevisionHash'] = _hash([preview['inputRevisionHash'], legacy['inputRevisionHash']])
        preview['resultPositionCount'] = len(preview['rows'])
        return preview
    return run_batch(keys, design_inputs=design_inputs,
                     **({"workbook_source_context": workbook} if workbook else {}))


class FormalEngineeringContinuationService:
    @classmethod
    def facts(cls, *, user, order_no=None,workbook_source_record_id=None):
        EngineeringCalculationService._authorize(
            user=user, action_code="production.engineering.calculation.view", company_id=user.company_id,
        )
        items = SalesOrderItem.objects.select_related("sales_order", "uom").filter(
            sales_order__company_id=user.company_id,
        )
        if order_no:
            items = items.filter(sales_order__order_no=order_no)
        items = list(items.order_by("sales_order_id", "line_no", "pk"))
        instance_by_item = {
            row.sales_order_item_id: row
            for row in OrderEngineeringInstance.objects.filter(
                company_id=user.company_id, sales_order_item_id__in=[item.pk for item in items],
            ).select_related("source_record", "product_category", "selected_process_type")
        }
        lines = []
        for item in items:
            instance = instance_by_item.get(item.pk)
            design_scope = _resolve_instance_identity(item, instance=instance) if item.engineering_mode == "ORDER_ENGINEERED" else None
            design_items = design_scope["designItems"] if design_scope else []
            lines.append({
                "salesOrderItemId": item.pk,
                "orderNo": item.sales_order.order_no,
                "lineNo": item.line_no,
                "orderQuantity": str(item.quantity),
                "orderUomCode": item.uom.code if item.uom_id else None,
                "designObjectCount": len(design_items),
                "designItemNos": [row.item_no for row in design_items],
                "sourceRecordId": design_scope["sourceRecordId"] if design_scope else None,
                "productCategoryId": design_scope["productCategoryId"] if design_scope else None,
                "selectedProcessTypeId": design_scope["selectedProcessTypeId"] if design_scope else None,
                "orderEngineeringInstanceId": instance.pk if instance else None,
                "orderEngineeringInstanceNo": instance.instance_no if instance else None,
                "instanceStatus": instance.status if instance else "not_created",
                "instanceStatusLabel": instance.get_status_display() if instance else "未建立",
                "sourceStatus": instance.source_record.status if instance else (
                    design_items[0].source_record.status if design_items else "unknown"
                ),
                "sourceStatusLabel": instance.source_record.get_status_display() if instance else (
                    design_items[0].source_record.get_status_display() if design_items else "未知"
                ),
                "writeImpact": "创建1个订单工程实例" if not instance else "不重复创建；复用已有实例",
            })
        # Read the existing formal records; never derive saved state from validation
        # or the instance's lifecycle flag. This does not change execute eligibility.
        calculation_records = []
        for record in EngineeringCalculationRecord.objects.filter(
            company_id=user.company_id, scope="order_engineering",
            sales_order_item_id__in=[item.pk for item in items],
            engineering_instance_id__in=[row.pk for row in instance_by_item.values()],
        ).order_by("-created_at", "-pk"):
            baseline = (record.trace or {}).get("baselineReference") or {}
            calculation_records.append({
                "id": record.pk, "calculationNo": record.calculation_no,
                "companyId": record.company_id, "scope": record.scope,
                "salesOrderItemId": record.sales_order_item_id,
                "orderEngineeringInstanceId": record.engineering_instance_id,
                "sourceRecordId": record.source_record_id,
                "status": record.status, "statusLabel": record.get_status_display(),
                "revision": record.revision,
                "baselineId": baseline.get("id"), "baselineNo": baseline.get("baselineNo"),
                "finishedAt": record.finished_at.isoformat() if record.finished_at else None,
            })
        line_saved_states, saved_state = summarize_formal_calculations(
            company_id=user.company_id, lines=lines, records=calculation_records,
        )
        for line in lines:
            line["formalCalculationState"] = line_saved_states[line["salesOrderItemId"]]
            instance = instance_by_item.get(line["salesOrderItemId"])
            if instance:
                from .oei_calculated_transition_repair_service import calculated_state_facts
                line["lifecycleStateFacts"] = calculated_state_facts(instance=instance, company_id=user.company_id)
            from .engineering_calculation_continuation_service import EngineeringCalculationContinuationService
            line['calculationContinuation'] = EngineeringCalculationContinuationService.facts(
                user=user,sales_order_item_id=line['salesOrderItemId'],
                engineering_instance_id=line['orderEngineeringInstanceId'],workbook_source_record_id=workbook_source_record_id)
        order_ids = sorted({item.sales_order_id for item in items})
        baselines = list(production_baselines().filter(
            company_id=user.company_id, sales_order_id__in=order_ids,
        ).select_related("sales_order").order_by("sales_order_id", "-sequence"))
        permissions = {}
        for code in (
            "production.engineering.source.maintain",
            "production.engineering.order.maintain",
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.engineering.rule.release",
        ):
            permissions[code] = AuthorizationService.decide(
                user=user, action_code=code, organization_id=user.company_id,
                business_object={"organizationId": user.company_id},
            )
        released = EngineeringRuleDefinition.objects.filter(
            company_id=user.company_id, rule_code__in=FORMAL_RULE_PACKAGES, status="released",
        ).order_by("rule_code")
        from .engineering_workbook_source_service import workbook_source_facts
        return {
            'workbookSources':workbook_source_facts(user.company_id),'workbookSourceRecordId':workbook_source_record_id,
            "orderNo": order_no or (lines[0]["orderNo"] if len({row['orderNo'] for row in lines}) == 1 else ""),
            "lines": lines,
            "lineCount": len(lines),
            "formalCalculationState": saved_state,
            "designObjectCount": sum(row["designObjectCount"] for row in lines),
            "baselines": [{
                "id": row.pk, "baselineNo": row.baseline_no, "status": row.status,
                "statusLabel": row.get_status_display(), "itemCount": row.scope_item_count,
                "candidateHash": row.candidate_hash, "snapshotHash": row.snapshot_hash,
            } for row in baselines],
            "formalRulePackages": [{
                "id": row.pk, "ruleCode": row.rule_code, "version": row.version,
                "ruleName": row.rule_name, "status": row.status,
            } for row in released],
            "requiredRulePackages": [f"{code}@{row['version']}" for code, row in FORMAL_RULE_PACKAGES.items()],
            "permissions": permissions,
            "sourceMaintenancePath": "/foundation/master-data/engineering-source-records",
            "sourceMaintenanceLabel": "工程来源记录 → 确认来源",
            "writeBoundary": "创建实例、确认实例来源和执行核算均为独立显式动作；页面打开、刷新、校验不写业务数据。",
            "factSource": "server",
            "businessWriteSideEffectCount": 0,
        }

    @classmethod
    def condition_preflight(cls, *, user, order_no, source_record_id=None,workbook_source_record_id=None):
        """Read-only conditions and native validation for the selected source.

        Missing prerequisites stay explicit. Once available, each concrete
        instance is checked against the same server-resolved workbook/baseline.
        No historical-read authority is granted to this execution preflight.
        """
        order_no = str(order_no or "").strip()
        if not order_no:
            raise EngineeringCalculationError(
                "PREFLIGHT_ORDER_CONTEXT_REQUIRED", "请先从页面可见列表选择一个明确订单。"
            )
        if workbook_source_record_id in (None,''):
            selected_workbook_id=None
        else:
            from .calculation_batch_reuse import _workbook_source_identity
            try:selected_workbook_id=_workbook_source_identity(workbook_source_record_id)
            except ValueError as error:
                raise EngineeringCalculationError('WORKBOOK_SOURCE_ID_INVALID','必须明确选择当前公司的正式工作簿来源身份') from error
        facts = cls.facts(user=user, order_no=order_no,workbook_source_record_id=selected_workbook_id)
        lines = facts["lines"]
        if not lines:
            raise EngineeringCalculationError(
                "PREFLIGHT_ORDER_NOT_FOUND", "订单不存在、无可查看订单行或不属于当前公司。"
            )
        workbook=_selected_workbook(user.company_id,selected_workbook_id)
        actual_source_ids = sorted({row["sourceRecordId"] for row in lines if row.get("sourceRecordId")})
        if workbook is not None and workbook['proof']['objectSourceRecordId'] not in actual_source_ids:
            raise EngineeringCalculationError('PREFLIGHT_WORKBOOK_CONTEXT_MISMATCH',
                '所选工作簿的正式对象来源不属于当前订单范围')
        if source_record_id not in (None, ""):
            try:
                requested_source_id = int(source_record_id)
            except (TypeError, ValueError):
                raise EngineeringCalculationError(
                    "PREFLIGHT_SOURCE_CONTEXT_INVALID", "工程来源上下文必须来自页面可见选择。"
                )
            if requested_source_id not in actual_source_ids:
                raise EngineeringCalculationError(
                    "PREFLIGHT_SOURCE_CONTEXT_MISMATCH",
                    "所选工程来源不属于当前订单的产品设计对象范围。",
                    {"orderNo": order_no, "sourceRecordId": requested_source_id},
                )

        confirmed_baselines = [row for row in facts["baselines"] if row["status"] == "confirmed"]
        if workbook is not None:
            scope=workbook['proof']['sourceScope']
            confirmed_baselines=[row for row in confirmed_baselines if row['id']==scope['baselineId']
                and row['snapshotHash']==scope['baselineSnapshotHash']]
            if len(confirmed_baselines)!=1:
                raise EngineeringCalculationError('WORKBOOK_BASELINE_MISMATCH',
                    '所选工作簿没有固定当前订单准确的已确认基线及Hash')
        required_packages = set(facts["requiredRulePackages"])
        released_packages = {
            f'{row["ruleCode"]}@{row["version"]}' for row in facts["formalRulePackages"]
        }
        missing_packages = sorted(required_packages - released_packages)
        blockers = []
        if any(row["sourceStatus"] != "confirmed" for row in lines):
            blockers.append({
                "code": "SOURCE_RECORD_NOT_CONFIRMED",
                "scope": "order",
                "reason": "当前工程来源仍为草稿；正式实例确认与执行前必须先由有权人员确认来源。",
                "nextStepLabel": facts["sourceMaintenanceLabel"],
                "nextStepPath": facts["sourceMaintenancePath"],
            })
        missing_instance_lines = [row["lineNo"] for row in lines if not row["orderEngineeringInstanceId"]]
        if missing_instance_lines:
            blockers.append({
                "code": "ORDER_ENGINEERING_INSTANCE_NOT_CREATED",
                "scope": "order-lines",
                "reason": f'订单第{",".join(str(value) for value in missing_instance_lines)}行尚未形成订单工程实例；各行可分别办理，不要求四行同时就绪。',
                "nextStepLabel": "在当前订单行的正式接续区形成实例",
                "nextStepPath": "/pde/engineering-calculations",
            })
        if not confirmed_baselines:
            blockers.append({
                "code": "CONFIRMED_BASELINE_REQUIRED",
                "scope": "order",
                "reason": "当前订单没有可用于完整执行前校验的已确认工程基线。",
                "nextStepLabel": "产品版本管理 → 工程基线",
                "nextStepPath": "/pde/product-versions",
            })
        if missing_packages:
            blockers.append({
                "code": "FORMAL_RULE_PACKAGES_INCOMPLETE",
                "scope": "formal-rule-packages",
                "reason": f'本订单正式接续仍缺少已发布规则包：{"、".join(missing_packages)}。',
                "nextStepLabel": "由规则发布权限人员按正式流程办理",
                "nextStepPath": "/foundation/master-data/engineering-rules",
            })

        line_results = []
        validation_checked_at = timezone.now().isoformat()
        for row in lines:
            line_blockers = []
            pending_labels = []
            if row["sourceStatus"] != "confirmed":
                line_blockers.append({
                    "code": "SOURCE_RECORD_NOT_CONFIRMED",
                    "reason": "工程来源尚未确认。",
                })
                pending_labels.append("确认工程来源")
            if not row["orderEngineeringInstanceId"]:
                line_blockers.append({
                    "code": "ORDER_ENGINEERING_INSTANCE_NOT_CREATED",
                    "reason": "本销售订单行尚未形成订单工程实例。",
                })
                pending_labels.append("形成本行订单工程实例")
            if not confirmed_baselines:
                line_blockers.append({
                    "code": "CONFIRMED_BASELINE_REQUIRED",
                    "reason": "尚无已确认工程基线。",
                })
                pending_labels.append("确认工程基线")
            if missing_packages:
                line_blockers.append({
                    "code": "FORMAL_RULE_PACKAGES_INCOMPLETE",
                    "reason": f'所需正式规则尚未全部发布：{"、".join(missing_packages)}。',
                })
                pending_labels.append("发布两套正式规则")
            execute_permission = facts["permissions"]["production.engineering.calculation.execute"]
            if not execute_permission.get("allowed"):
                line_blockers.append({
                    "code": "FORMAL_EXECUTION_PERMISSION_REQUIRED",
                    "reason": "当前账号没有正式核算执行权限。",
                })
                pending_labels.append("由有执行权限人员办理")
            full_validation = {
                "status": "not_ready",
                "statusLabel": "前置条件未齐，未执行完整校验",
                "checkedAt": validation_checked_at,
                "ready": False,
                "objectCount": None,
                "resultPositionCount": None,
                "blockers": [
                    item for item in line_blockers
                    if item["code"] != "FORMAL_EXECUTION_PERMISSION_REQUIRED"
                ],
                "businessWriteSideEffectCount": 0,
            }
            validation_prerequisite_codes = {
                "SOURCE_RECORD_NOT_CONFIRMED",
                "ORDER_ENGINEERING_INSTANCE_NOT_CREATED",
                "CONFIRMED_BASELINE_REQUIRED",
                "FORMAL_RULE_PACKAGES_INCOMPLETE",
            }
            has_validation_prerequisite_blocker = any(
                item["code"] in validation_prerequisite_codes for item in line_blockers
            )
            if not has_validation_prerequisite_blocker:
                try:
                    validation = cls.validate(
                        user=user,
                        sales_order_item_id=row["salesOrderItemId"],
                        engineering_instance_id=row["orderEngineeringInstanceId"],
                        baseline_id=confirmed_baselines[0]["id"],
                        rule_ids=[item["id"] for item in facts["formalRulePackages"]],
                        workbook_source_record_id=selected_workbook_id,
                        workbook_source_context=workbook,
                    )
                    full_validation = {
                        "status": "passed" if validation["ready"] else "blocked",
                        "statusLabel": "完整办理条件校验通过" if validation["ready"] else "完整办理条件校验有阻断",
                        "checkedAt": validation_checked_at,
                        "ready": validation["ready"],
                        "objectCount": validation["selection"]["objectCount"],
                        "resultPositionCount": validation["selection"]["resultPositionCount"],
                        "selection": validation["selection"],
                        "inputSnapshotHash": validation["inputSnapshotHash"],
                        "previewResultHash": validation["previewResultHash"],
                        "blockers": validation["blockers"],
                        "businessWriteSideEffectCount": validation["businessWriteSideEffectCount"],
                    }
                except EngineeringCalculationError as exc:
                    full_validation = {
                        "status": "read_failed",
                        "statusLabel": "完整办理条件校验读取失败",
                        "checkedAt": validation_checked_at,
                        "ready": False,
                        "objectCount": None,
                        "resultPositionCount": None,
                        "blockers": [{
                            "code": getattr(exc, "code", "FULL_VALIDATION_READ_FAILED"),
                            "reason": getattr(exc, "message", str(exc)),
                        }],
                        "businessWriteSideEffectCount": 0,
                    }
            line_results.append({
                **row,
                "readyForFullValidation": not line_blockers,
                "saveReadinessStatus": "ready_for_full_validation" if not line_blockers else "incomplete",
                "saveReadinessStatusLabel": "可进入完整执行前校验" if not line_blockers else "保存准备未完成",
                "saveReadinessSummary": "可进入完整执行前校验" if not pending_labels else f'需完成：{"、".join(pending_labels)}',
                "blockerCodes": [item["code"] for item in line_blockers],
                "blockers": line_blockers,
                "confirmedBaseline": confirmed_baselines[0] if confirmed_baselines else None,
                "releasedRulePackageCount": len(released_packages),
                "requiredRulePackageCount": len(required_packages),
                "fullValidation": full_validation,
            })
        return {
            "preflightType": "READ_ONLY_CONDITION_PREFLIGHT",
            "orderNo": order_no,
            "sourceRecordIds": actual_source_ids,
            "workbookSourceRecordId":selected_workbook_id,
            "readyForFullValidation": not blockers,
            "readyForFormalExecution": False,
            "blockers": blockers,
            "lines": line_results,
            "confirmedBaselines": confirmed_baselines,
            "formalRulePackages": facts["formalRulePackages"],
            "requiredRulePackages": facts["requiredRulePackages"],
            "permissions": facts["permissions"],
            "formalCalculationState": facts["formalCalculationState"],
            "stageExplanation": {
                "conditionPreflight": "仅回读订单、来源、实例、基线、正式规则与权限事实，说明缺少什么。",
                "fullValidation": "针对一个已建立实例，校验其确认来源、基线对象子集、正式规则和计算输入。",
                "formalExecution": "通过服务端权限和完整校验后，显式创建正式核算记录。",
            },
            "factSource": "server",
            "businessWriteSideEffectCount": 0,
        }

    @classmethod
    def create_instance(cls, *, user, sales_order_item_id, idempotency_key, reason=""):
        EngineeringCalculationService._authorize(
            user=user, action_code="production.engineering.order.maintain", company_id=user.company_id,
        )
        sales_item = SalesOrderItem.objects.select_related("sales_order").filter(
            pk=sales_order_item_id, sales_order__company_id=user.company_id,
        ).first()
        if not sales_item:
            raise EngineeringCalculationError("SALES_ORDER_ITEM_NOT_FOUND", "订单行不存在或不属于当前公司。")
        existing = OrderEngineeringInstance.objects.filter(sales_order_item=sales_item).first()
        if existing:
            return {"row": _snapshot(existing), "idempotent": True, "auditId": None}
        identity = _resolve_instance_identity(sales_item)
        source = identity["designItems"][0].source_record
        try:
            require_crm_order_admission(
                company_id=user.company_id,
                source_record_id=identity["sourceRecordId"],
                source_order_no=sales_item.sales_order.external_source_no,
                source_version=source.source_version,
                lock=True,
            )
        except CRMOrderAdmissionError as exc:
            raise EngineeringCalculationError(
                exc.code, exc.message, {"crmOrderAdmission": exc.details},
            ) from exc
        payload = {
            "company_id": user.company_id,
            "sales_order_item_id": sales_item.pk,
            "product_id": None,
            "baseline_product_version_id": None,
            "product_category_id": identity["productCategoryId"],
            "selected_process_type_id": identity["selectedProcessTypeId"],
            "source_record_id": identity["sourceRecordId"],
            "reason": reason or "在原工程核算页形成订单行工程实例",
        }
        try:
            result = ProductionFoundationService.write(
                "order-engineering-instances", user=user, payload=payload,
                idempotency_key=idempotency_key,
                source_identity={
                    "sourceSystem": "PDE_FORMAL_ENGINEERING_CONTINUATION",
                    "sourceType": "BUSINESS_ACTION_SCOPE",
                    "sourceObjectType": "SalesOrderItem",
                    "externalId": f"order-engineering-instance:{sales_item.pk}",
                    "auditMetadata": {
                        "orderNo": sales_item.sales_order.order_no,
                        "lineNo": sales_item.line_no,
                        "designItemIds": [row.pk for row in identity["designItems"]],
                    },
                },
            )
        except Exception as exc:
            if isinstance(exc, EngineeringCalculationError):
                raise
            raise EngineeringCalculationError(
                getattr(exc, "code", "INSTANCE_CREATE_FAILED"),
                getattr(exc, "message", str(exc)), getattr(exc, "details", {}),
            )
        return result

    @classmethod
    def confirm_instance_source(cls, *, user, engineering_instance_id, reason=""):
        try:
            return EngineeringLifecycleService.transition(
                "order-engineering-instances", object_id=engineering_instance_id,
                target_status="source_confirmed", user=user,
                reason=reason or "原工程核算页确认实例采用已确认工程来源",
            )
        except Exception as exc:
            raise EngineeringCalculationError(
                getattr(exc, "code", "INSTANCE_SOURCE_CONFIRM_FAILED"),
                getattr(exc, "message", str(exc)), getattr(exc, "details", {}),
            )

    @classmethod
    def validate(cls, *, user, sales_order_item_id, engineering_instance_id, baseline_id, rule_ids=None,
                 workbook_source_record_id=None,workbook_source_context=None):
        EngineeringCalculationService._authorize(
            user=user, action_code="production.engineering.calculation.view", company_id=user.company_id,
        )
        sales_item, instance, baseline, baseline_items, design_inputs, baseline_ref = _resolve_context(
            company_id=user.company_id, sales_order_item_id=sales_order_item_id,
            engineering_instance_id=engineering_instance_id, baseline_id=baseline_id,
        )
        rules = _package_rules(user.company_id, rule_ids)
        keys = [row["sourceKey"] for row in design_inputs]
        if len(keys) != len(set(keys)):
            raise EngineeringCalculationError("BASELINE_SOURCE_KEY_DUPLICATED", "实例基线子集包含重复来源身份。")
        workbook=_selected_workbook(user.company_id,workbook_source_record_id,workbook_source_context,baseline)
        preview = _preview_baseline_inputs(keys, design_inputs, workbook)
        missing = [row for row in preview["rows"] if row.get("state") != "calculated"]
        return {
            "ready": not missing and not preview.get("blockers"),
            "blockers": [*preview.get("blockers", []), *[{
                "code": "OBJECT_CALCULATION_INPUT_INCOMPLETE",
                "designObject": row.get("sourceKey"),
                "result": row.get("project"),
                "reason": row.get("reason"),
            } for row in missing]],
            "selection": {
                "orderNo": sales_item.sales_order.order_no,
                "salesOrderItemId": sales_item.pk,
                "lineNo": sales_item.line_no,
                "orderEngineeringInstanceId": instance.pk,
                "instanceNo": instance.instance_no,
                "sourceRecordId": instance.source_record_id,
                "baselineReference": baseline_ref,
                "objectCount": len(baseline_items),
                "resultPositionCount": preview.get("resultPositionCount", len(preview["rows"])),
                "sourceIdentities": [row["sourceIdentity"] for row in design_inputs],
                "ruleIds": [rules[code].pk for code in FORMAL_RULE_PACKAGES],
                **({'workbookSource':workbook['proof'],'workbookSourceRecordId':workbook['proof']['sourceRecordId']} if workbook else {}),
            },
            "inputSnapshotHash": _hash(design_inputs),
            "previewResultHash": _hash({"rows": preview["rows"], "blockers": preview["blockers"]}) if preview.get("blockers") else _hash(preview["rows"]),
            "factSource": "server",
            "businessWriteSideEffectCount": 0,
        }

    @classmethod
    def execute(cls, **kwargs):
        user = kwargs["user"]
        decision = EngineeringCalculationService._authorize(
            user=user, action_code="production.engineering.calculation.execute", company_id=user.company_id,
        )
        try:
            execution_chain = _actor_chain(user)
        except Exception as exc:
            raise EngineeringCalculationError(
                getattr(exc, "code", "FORMAL_EXECUTION_CHAIN_REQUIRED"),
                getattr(exc, "message", str(exc)), getattr(exc, "details", {}),
            )
        return cls._execute_atomic(decision=decision, execution_chain=execution_chain, **kwargs)

    @classmethod
    @transaction.atomic
    def _execute_atomic(
        cls, *, user, sales_order_item_id, engineering_instance_id, baseline_id,
        rule_ids=None, reason="", decision, execution_chain, continuation_record=None,
        workbook_source_record_id=None,workbook_source_context=None,
    ):
        sales_item, instance, baseline, baseline_items, design_inputs, baseline_ref = _resolve_context(
            company_id=user.company_id, sales_order_item_id=sales_order_item_id,
            engineering_instance_id=engineering_instance_id, baseline_id=baseline_id, lock=True,
        )
        rules = _package_rules(user.company_id, rule_ids)
        keys = [row["sourceKey"] for row in design_inputs]
        if len(keys) != len(set(keys)):
            raise EngineeringCalculationError("BASELINE_SOURCE_KEY_DUPLICATED", "实例基线子集包含重复来源身份。")
        workbook=_selected_workbook(user.company_id,workbook_source_record_id,workbook_source_context,baseline)
        batch = _preview_baseline_inputs(keys, design_inputs, workbook)
        if batch.get("blockers"):
            raise EngineeringCalculationError(
                batch["blockers"][0]["code"], "原生设计核算输入不满足受控映射；未写入任何核算结果。",
                {"blockers": batch["blockers"]},
            )
        missing = [row for row in batch["rows"] if row.get("state") != "calculated"]
        if missing:
            raise EngineeringCalculationError(
                "OBJECT_CALCULATION_INPUT_INCOMPLETE", "对象级输入存在缺项；本实例未写入任何核算结果。",
                {"missingCount": len(missing), "missing": missing[:20]},
            )
        rule_graph = [{
            "id": rules[code].pk,
            "ruleCode": code,
            "version": rules[code].version,
            "executionAdapter": FORMAL_RULE_PACKAGES[code]["adapter"],
            "specificationHash": _hash(rules[code].specification),
        } for code in FORMAL_RULE_PACKAGES]
        object_snapshot = [{
            "baselineItemId": row["baselineItemId"], "designItemId": row["designItemId"],
            "designItemNo": row["designItemNo"], "sourceAttributeId": row["sourceAttributeId"],
            "sourceKey": row["sourceKey"], "contentHash": row["baselineContentHash"],
            "sourceVersion": row["sourceVersion"], "sourceContentHash": row["sourceContentHash"],
            "input": row,
        } for row in design_inputs]
        input_hash = calculation_input_hash(baseline_ref, object_snapshot,
            **({'workbook_source': workbook['proof']} if workbook else {}))
        rule_graph_hash = _hash(rule_graph)
        idempotency_payload = {
            "scope": "order_engineering",
            "sourceRecordId": instance.source_record_id,
            "salesOrderItemId": sales_item.pk,
            "engineeringInstanceId": instance.pk,
            "baselineId": baseline.pk,
            "baselineSnapshotHash": baseline.snapshot_hash,
            "selectedItemHash": baseline_ref["selectedItemHash"],
            "inputHash": input_hash,
            "ruleGraphHash": rule_graph_hash,
            **({'workbookSource':workbook['proof']} if workbook else {}),
        }
        idempotency_key = _hash(idempotency_payload)
        existing = EngineeringCalculationRecord.objects.filter(
            company_id=user.company_id, idempotency_key=idempotency_key,
        ).first()
        if existing:
            audit = OrganizationOperatingAuditRecord.objects.filter(
                action_code="production.engineering.calculation.execute",
                target_type="EngineeringCalculationRecord", target_id=existing.pk,
            ).order_by("-pk").first()
            return {
                "calculation": serialize_calculation(existing), "idempotent": True,
                "auditId": audit.pk if audit else None, "authorization": decision,
                "executionChain": execution_chain,
            }
        previous = EngineeringCalculationRecord.objects.select_for_update().filter(
            company_id=user.company_id, scope="order_engineering", engineering_instance=instance,
        ).order_by("-revision", "-pk").first()
        _guard_consumed_legacy_revision(previous, sales_item=sales_item, instance=instance,
            baseline=baseline, company_id=user.company_id,continuation_record=continuation_record,user=user,
            workbook_source_context=workbook)
        revision = previous.revision + 1 if previous else 1
        try:
            calculation_no = CodeRule.next_code(
                entity_type="production_engineering_calculation", company_id=user.company_id,
            )
        except CodeRule.DoesNotExist:
            raise EngineeringCalculationError("CODE_RULE_REQUIRED", "缺少正式工程计算编码规则。")
        started_at = timezone.now()
        calculation = create_business_object_with_initial_state(
            model=EngineeringCalculationRecord, initial_state="running",
            company_id=user.company_id, scope="order_engineering",
            source_record=instance.source_record, sales_order_item=sales_item,
            engineering_instance=instance, calculation_no=calculation_no,
            rule_set_version="+".join(f"{code}@{rules[code].version}" for code in FORMAL_RULE_PACKAGES),
            revision=revision, supersedes=previous, idempotency_key=idempotency_key,
            input_hash=input_hash, rule_graph_hash=rule_graph_hash, started_at=started_at,
            trace={
                "scope": "order_engineering",
                "baselineReference": baseline_ref,
                "sourceReference": {
                    "id": instance.source_record_id, "sourceNo": instance.source_record.source_no,
                    "sourceVersion": instance.source_record.source_version,
                    "contentHash": instance.source_record.content_hash,
                },
                "salesOrderItemId": sales_item.pk,
                "orderEngineeringInstanceId": instance.pk,
                "objectInputSnapshot": object_snapshot,
                "objectInputSnapshotHash": input_hash,
                "ruleGraphSnapshot": rule_graph,
                "batchFingerprint": batch["batchFingerprint"],
                "inputRevisionHash": batch["inputRevisionHash"],
                "resultPositionCount": len(batch["rows"]),
                "materialRequirementCount": 0,
                "operationRequirementCount": 0,
                "idempotencyPayload": idempotency_payload,
                "factSource": "server",
                **({'workbookSource':workbook['proof'],'workbookSourceRecordId':workbook['proof']['sourceRecordId']} if workbook else {}),
            },
        )
        try:
            calculation.full_clean()
        except ValidationError as exc:
            raise EngineeringCalculationError(
                "CALCULATION_CONTEXT_INVALID", "工程计算聚合校验失败。", exc.message_dict,
            )
        input_by_key = {row["sourceKey"]: row for row in design_inputs}
        result_snapshot = []
        for sequence, result in enumerate(batch["rows"], 1):
            package_code = (
                "SOURCE_LINEAR_CONTINUATION"
                if result.get("resultScope") == "linear-continuation"
                else "APPROVED_SOURCE_NET"
            )
            rule = rules[package_code]
            object_input = input_by_key[result["sourceKey"]]
            unit_code = str(result.get("unit") or "")
            unit_candidates = [unit_code]
            if unit_code == "m2":
                unit_candidates.extend(["m²", "㎡"])
            uom = UnitOfMeasure.objects.filter(
                company_id=user.company_id, code__in=unit_candidates, is_active=True,
            ).order_by("pk").first() if unit_code else None
            output_value = {"decimal": str(result["value"])}
            detail = EngineeringCalculationDetail.objects.create(
                calculation=calculation, sequence=sequence, rule=rule,
                rule_code=rule.rule_code, rule_version=rule.version,
                expression_snapshot=str(result.get("expression") or "SOURCE_BRANCH"),
                input_snapshot={
                    "object": object_input,
                    "ruleInputs": result.get("inputs") or [],
                    "sourceCell": result.get("sourceCell"),
                    "sourceFormula": result.get("sourceFormula"),
                    **({'workbookSource':result.get('workbookSource'),'adapterSlot':result.get('adapterSlot'),
                        'sourceColumn':result.get('sourceColumn'),'sourceCell':result.get('sourceCell')} if workbook else {}),
                },
                dependency_snapshot=[], output_name=str(result.get("project") or result.get("column")),
                output_value=output_value, uom=uom,
                precision=int(result.get("precision") or 28),
                rounding=str(result.get("rounding") or "ROUND_HALF_UP"),
                status="succeeded", started_at=started_at, finished_at=timezone.now(),
            )
            fact_code = f"{object_input['designItemNo']}:{result.get('column')}"[:120]
            fact = EngineeringDerivedFact(
                calculation=calculation, rule=rule, source_detail=detail,
                fact_code=fact_code, canonical_field=str(result.get("column") or result.get("project")),
                sequence=sequence, value=output_value, value_type="decimal", uom=uom,
                source_type="ENGINEERING_DERIVED", status="active",
                source_path=f"baseline.items[{object_input['baselineItemId']}].results[{result.get('column')}]",
                trace={
                    "baselineId": baseline.pk, "baselineItemId": object_input["baselineItemId"],
                    "baselineContentHash": object_input["baselineContentHash"],
                    "designItemId": object_input["designItemId"],
                    "designItemNo": object_input["designItemNo"],
                    "sourceAttributeId": object_input["sourceAttributeId"],
                    "sourceKey": object_input["sourceKey"],
                    "ruleCode": rule.rule_code, "ruleVersion": rule.version,
                    "resultScope": result.get("resultScope"),
                    "unitSnapshot": unit_code or None,
                    **({'workbookSource':result.get('workbookSource'),'adapterSlot':result.get('adapterSlot'),
                        'sourceColumn':result.get('sourceColumn'),'sourceCell':result.get('sourceCell')} if workbook else {}),
                    "comparison": {
                        "expected": result.get("expected"), "difference": result.get("difference"),
                        "matched": result.get("matched"), "statusLabel": result.get("statusLabel"),
                    },
                },
            )
            fact.full_clean()
            fact.save()
            result_snapshot.append({
                "sequence": sequence, "designItemId": object_input["designItemId"],
                "designItemNo": object_input["designItemNo"], "sourceKey": result["sourceKey"],
                "canonicalField": result.get("column"), "displayName": result.get("project"),
                "value": output_value, "unit": unit_code or None,
                "ruleCode": rule.rule_code, "ruleVersion": rule.version,
                "detailId": detail.pk, "factId": fact.pk,
                **({'workbookSource':result.get('workbookSource'),'adapterSlot':result.get('adapterSlot'),
                    'sourceColumn':result.get('sourceColumn'),'sourceCell':result.get('sourceCell')} if workbook else {}),
            })
        result_hash = _hash(result_snapshot)
        calculation.result_hash = result_hash
        calculation.finished_at = timezone.now()
        calculation.trace = {
            **calculation.trace,
            "resultSnapshot": result_snapshot,
            "resultHash": result_hash,
            "completedDetailCount": len(result_snapshot),
            "completedDerivedFactCount": len(result_snapshot),
        }
        calculation.save(update_fields=["result_hash", "finished_at", "trace", "updated_at"])
        audit = _audit(
            user=user, organization_id=user.company_id,
            action_code="production.engineering.calculation.execute",
            instance=calculation, before={},
            after={
                **_snapshot(calculation), "status": "completed", "decision": "SUCCEEDED",
                "baselineReference": baseline_ref,
                "objectCount": len(object_snapshot), "resultPositionCount": len(result_snapshot),
                "inputHash": input_hash, "resultHash": result_hash,
                "operator": execution_chain["account"],
            },
            reason=reason or "按已确认工程基线执行对象级正式核算",
            authorization=decision, execution_chain=execution_chain,
        )
        transition_business_object(
            business_object=calculation, object_type="EngineeringCalculationRecord",
            source_state="running", target_state="completed",
            action_code="production.engineering.calculation.execute", operator=user,
            reason=reason or "对象级正式核算完成",
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions=(("running", "completed"),), version_field=None,
        )
        if continuation_record is None:
            _retire_unconsumed_calculation(previous, calculation, user=user,
                decision=decision, execution_chain=execution_chain)
        if instance.status == "source_confirmed":
            EngineeringLifecycleService.transition(
                "order-engineering-instances", object_id=instance.pk,
                target_status="calculated", user=user,
                reason="对象级正式核算完成且派生事实已持久化",
            )
        calculation.refresh_from_db()
        return {
            "calculation": {**serialize_calculation(calculation),
                **({'workbookSourceRecordId':workbook['proof']['sourceRecordId']} if workbook else {})}, "idempotent": False,
            "auditId": audit.pk, "authorization": decision,
            "executionChain": execution_chain,
        }

