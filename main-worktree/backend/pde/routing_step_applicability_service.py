"""Authoritative, read-only RoutingStep applicability contract and resolver.

The resolver is deliberately fail-closed.  It never infers applicability from
operation names, free text, product names, or imported spreadsheets.  A
conditional step can be resolved either by one exact released engineering fact
or by one audited authorized-person decision bound to the exact order-
engineering context.  Conflicting or invalid sources always remain pending.
"""
from __future__ import annotations
from pde.baseline_usage_service import production_baselines, production_status

from dataclasses import dataclass

from django.core.exceptions import ValidationError


CONTRACT_VERSION = "PCE-ROUTING-STEP-APPLICABILITY-V1.0"

MANDATORY = "MANDATORY"
CONDITIONAL = "CONDITIONAL"
REQUIRED = "REQUIRED"
NOT_APPLICABLE = "NOT_APPLICABLE"
PENDING = "PENDING"

MODE_LABELS = {
    MANDATORY: "必经工序",
    CONDITIONAL: "条件执行工序",
}
RESULT_LABELS = {
    REQUIRED: "本次必须执行",
    NOT_APPLICABLE: "本次不适用",
    PENDING: "待正式条件确认",
}

# This is the complete governed condition vocabulary for V1.  Codes are
# stable server contracts; labels are the only values intended for end users.
CONDITION_REGISTRY = {
    "DRAWING_ENGRAVING_REQUIRED": {
        "label": "正式图纸要求雕刻纹路",
        "sourceLabel": "已发布工程事实或授权业务人员人工确认",
        "factCode": "DRAWING_ENGRAVING_REQUIRED",
        "question": "本次订单工程对象是否需要雕刻纹路？",
    },
    "PREPRODUCTION_SPECIAL_SHAPE_REQUIRED": {
        "label": "生产前已确认异形加工要求",
        "sourceLabel": "已发布工程事实或授权业务人员人工确认",
        "factCode": "PREPRODUCTION_SPECIAL_SHAPE_REQUIRED",
        "question": "本次订单工程对象是否需要生产前异形加工？",
    },
}

# User-confirmed compatibility facts for the immutable CALC-3 initial version.
# The key uses formal object codes and revision only; names are intentionally
# absent so that no fuzzy/free-text inference is possible.
LEGACY_EXACT_CONTRACTS = {
    ("QSFB/FM", "SYSTEM_INITIAL_VERSION", 1, "PROC202608000003"): {
        "mode": MANDATORY,
    },
    ("QSFB/FM", "SYSTEM_INITIAL_VERSION", 1, "PROC202608000005"): {
        "mode": MANDATORY,
    },
    ("QSFB/FM", "SYSTEM_INITIAL_VERSION", 1, "PROC202608000009"): {
        "mode": CONDITIONAL,
        "conditionCode": "DRAWING_ENGRAVING_REQUIRED",
    },
    ("QSFB/FM", "SYSTEM_INITIAL_VERSION", 1, "PROC202608000010"): {
        "mode": CONDITIONAL,
        "conditionCode": "PREPRODUCTION_SPECIAL_SHAPE_REQUIRED",
    },
}


def validate_operation_parameters_applicability(parameters):
    """Validate only the governed applicability member of operation parameters."""
    if parameters in (None, ""):
        return
    if not isinstance(parameters, dict):
        raise ValidationError("工序参数必须是对象。")
    contract = parameters.get("applicability")
    if contract is None:
        return
    if not isinstance(contract, dict):
        raise ValidationError("工序适用性合同必须是对象。")
    unknown = set(contract) - {"contractVersion", "mode", "conditionCode"}
    if unknown:
        raise ValidationError(f"工序适用性合同包含未治理字段：{', '.join(sorted(unknown))}。")
    version = contract.get("contractVersion", CONTRACT_VERSION)
    if version != CONTRACT_VERSION:
        raise ValidationError("工序适用性合同版本不受支持。")
    mode = contract.get("mode")
    condition_code = str(contract.get("conditionCode") or "").strip()
    if mode not in MODE_LABELS:
        raise ValidationError("工序适用方式只允许必经或条件执行。")
    if mode == MANDATORY and condition_code:
        raise ValidationError("必经工序不得同时配置条件代码。")
    if mode == CONDITIONAL and condition_code not in CONDITION_REGISTRY:
        raise ValidationError("条件执行工序必须选择受治理的正式条件。")


def normalized_contract(contract):
    contract = dict(contract or {})
    result = {
        "contractVersion": CONTRACT_VERSION,
        "mode": contract.get("mode"),
    }
    if contract.get("conditionCode"):
        result["conditionCode"] = contract["conditionCode"]
    validate_operation_parameters_applicability({"applicability": result})
    return result


def explicit_contract(step):
    parameters = step.operation_parameters if isinstance(step.operation_parameters, dict) else {}
    contract = parameters.get("applicability")
    if contract is None:
        return None
    validate_operation_parameters_applicability(parameters)
    return normalized_contract(contract)


def legacy_exact_contract(step):
    version = step.routing_version
    routing = version.routing if version.routing_id else None
    operation = step.operation
    key = (
        routing.routing_code if routing else "",
        version.routing_version,
        version.revision,
        operation.code,
    )
    contract = LEGACY_EXACT_CONTRACTS.get(key)
    return normalized_contract(contract) if contract else None


def successor_contract(step):
    """Return the safe contract to materialize while copying a successor draft."""
    contract = explicit_contract(step) or legacy_exact_contract(step)
    if contract:
        return contract
    # Existing terminal versions historically treated unmarked operations as
    # normal required steps.  Materializing that compatibility meaning in a
    # new draft removes ambiguity without changing the source version.
    if step.routing_version.status in {"reviewed", "released", "obsolete"}:
        return normalized_contract({"mode": MANDATORY})
    return None


@dataclass(frozen=True)
class ResolutionContext:
    engineering_calculation: object | None = None
    engineering_document_version: object | None = None
    order_engineering_instance: object | None = None
    order_engineering_baseline: object | None = None
    bom_version: object | None = None


class RoutingStepApplicabilityResolver:
    @staticmethod
    def condition_options():
        return [
            {
                "value": code,
                "label": item["label"],
                "sourceLabel": item["sourceLabel"],
                "question": item["question"],
            }
            for code, item in CONDITION_REGISTRY.items()
        ]

    @classmethod
    def resolve(
        cls,
        step,
        *,
        engineering_calculation=None,
        engineering_document_version=None,
        order_engineering_instance=None,
        order_engineering_baseline=None,
        bom_version=None,
        production_plan=None,
        manufacturing_output=None,
        read_cache=None,
    ):
        # Object decisions are independent persisted facts, never edits to a
        # released routing version. Legacy callers without plan scope retain
        # the exact existing contract and compatibility behavior.
        if production_plan is not None:
            from .conditional_execution_preparation import resolve_conditional_execution
            conditional = resolve_conditional_execution(
                step, production_plan, manufacturing_output=manufacturing_output,
                engineering_calculation=engineering_calculation,
                order_engineering_instance=order_engineering_instance,
                order_engineering_baseline=order_engineering_baseline, bom_version=bom_version,
                read_cache=read_cache,
            )
            if conditional is not None:
                # A proved policy is an additional plan-stage fact. It never
                # rewrites the released route or grants object execution.
                payload = cls._payload(
                    step=step, contract={'mode': CONDITIONAL,
                        'conditionCode': conditional['conditionCode']}, result=PENDING,
                    contract_source='FORMAL_CONDITIONAL_PREPARATION', contract_explicit=False,
                    formal_source_label='正式条件准备裁决及原生审计',
                )
                payload.update(conditionalExecution=conditional,
                    resultLabel=conditional['triggerPolicyLabel'],
                    conditionLabel=conditional['triggerPolicyLabel'],
                    pendingReason=conditional['pendingScopeLabel'],
                    formalPolicyValidated=True, formalApplicabilityValidated=False)
                return payload
            from .routing_object_applicability_service import RoutingObjectApplicabilityService
            objects = RoutingObjectApplicabilityService.resolve_for_step(
                step, production_plan=production_plan, manufacturing_output=manufacturing_output,
                engineering_calculation=engineering_calculation,
                order_engineering_instance=order_engineering_instance,
                order_engineering_baseline=order_engineering_baseline,
                bom_version=bom_version,
            )
            if objects is not None:
                contract = explicit_contract(step) or legacy_exact_contract(step)
                if contract is None and step.routing_version.status in {"reviewed", "released", "obsolete"}:
                    contract = normalized_contract({"mode": MANDATORY})
                result = objects["result"]
                reasons = objects.get("reasons") or []
                payload = cls._payload(
                    step=step, contract=contract, result=result,
                    contract_source="FORMAL_OBJECT_APPLICABILITY",
                    contract_explicit=explicit_contract(step) is not None,
                    pending_code="OBJECT_APPLICABILITY_PENDING" if result == PENDING else "",
                    pending_reason="；".join(str(row.get("statusLabel", row.get("message", row)))
                        if isinstance(row, dict) else str(row) for row in reasons) if result == PENDING else "",
                    formal_source_label="正式对象适用性记录及原生审计",
                )
                payload["objectApplicability"] = objects
                payload["formalApplicabilityValidated"] = bool(objects.get("complete") and result != PENDING)
                return payload
        contract = explicit_contract(step)
        contract_source = "EXPLICIT_VERSION_CONTRACT"
        contract_explicit = contract is not None
        if contract is None:
            contract = legacy_exact_contract(step)
            contract_source = "USER_CONFIRMED_LEGACY_COMPATIBILITY" if contract else ""
        if contract is None:
            if step.routing_version.status in {"reviewed", "released", "obsolete"}:
                contract = normalized_contract({"mode": MANDATORY})
                contract_source = "TERMINAL_VERSION_COMPATIBILITY"
            else:
                return cls._payload(
                    step=step,
                    contract=None,
                    result=PENDING,
                    contract_source="MISSING",
                    contract_explicit=False,
                    pending_code="APPLICABILITY_CONTRACT_MISSING",
                    pending_reason="草稿步骤尚未维护正式工序适用方式。",
                )

        mode = contract["mode"]
        if mode == MANDATORY:
            return cls._payload(
                step=step,
                contract=contract,
                result=REQUIRED,
                contract_source=contract_source,
                contract_explicit=contract_explicit,
            )

        context = ResolutionContext(
            engineering_calculation=engineering_calculation,
            engineering_document_version=engineering_document_version,
            order_engineering_instance=order_engineering_instance,
            order_engineering_baseline=order_engineering_baseline,
            bom_version=bom_version,
        )
        return cls._resolve_conditional(
            step, contract, context,
            contract_source=contract_source,
            contract_explicit=contract_explicit,
        )

    @classmethod
    def _resolve_conditional(cls, step, contract, context, *, contract_source, contract_explicit):
        from .routing_manual_applicability_service import RoutingManualApplicabilityService

        manual = RoutingManualApplicabilityService.resolve_for_step(
            step,
            engineering_calculation=context.engineering_calculation,
            order_engineering_instance=context.order_engineering_instance,
            order_engineering_baseline=context.order_engineering_baseline,
            bom_version=context.bom_version,
        )
        formal = cls._formal_candidate(step, contract, context)

        invalid = next(
            (candidate for candidate in (manual, formal) if candidate.get("status") == "INVALID"),
            None,
        )
        if invalid:
            return cls._payload(
                step=step, contract=contract, result=PENDING,
                contract_source=contract_source, contract_explicit=contract_explicit,
                pending_code=invalid["pendingCode"],
                pending_reason=invalid["pendingReason"],
                document=formal.get("document"), fact=formal.get("fact"), manual=manual,
            )
        if manual.get("status") == "PENDING":
            return cls._payload(
                step=step, contract=contract, result=PENDING,
                contract_source=contract_source, contract_explicit=contract_explicit,
                pending_code="MANUAL_DECISION_PENDING",
                pending_reason="授权业务人员已明确选择待确认。",
                document=formal.get("document"), fact=formal.get("fact"), manual=manual,
                formal_source_label=manual.get("sourceLabel"),
            )
        if manual.get("status") == "RESOLVED" and formal.get("status") == "RESOLVED":
            if manual["result"] != formal["result"]:
                return cls._payload(
                    step=step, contract=contract, result=PENDING,
                    contract_source=contract_source, contract_explicit=contract_explicit,
                    pending_code="MANUAL_AND_FORMAL_FACT_CONFLICT",
                    pending_reason="授权人工判断与既有正式工程事实冲突，必须人工处理冲突后再继续。",
                    document=formal.get("document"), fact=formal.get("fact"), manual=manual,
                    formal_source_label="授权业务人员人工确认与已发布工程事实存在冲突",
                )
        if manual.get("status") == "RESOLVED":
            return cls._payload(
                step=step, contract=contract, result=manual["result"],
                contract_source=contract_source, contract_explicit=contract_explicit,
                document=formal.get("document"), fact=formal.get("fact"), manual=manual,
                formal_source_label=manual.get("sourceLabel"),
            )
        if formal.get("status") == "RESOLVED":
            return cls._payload(
                step=step, contract=contract, result=formal["result"],
                contract_source=contract_source, contract_explicit=contract_explicit,
                document=formal.get("document"), fact=formal.get("fact"),
                formal_source_label="已发布工程资料版本中的正式工程派生事实",
            )
        return cls._payload(
            step=step, contract=contract, result=PENDING,
            contract_source=contract_source, contract_explicit=contract_explicit,
            pending_code="FORMAL_OR_MANUAL_CONDITION_REQUIRED",
            pending_reason="尚无精确绑定的已发布工程事实或授权业务人员人工确认。",
        )

    @classmethod
    def _formal_candidate(cls, step, contract, context):
        from .models import EngineeringDerivedFact, EngineeringDocumentVersion

        condition = CONDITION_REGISTRY[contract["conditionCode"]]
        document = context.engineering_document_version
        documents = EngineeringDocumentVersion.objects.none()
        if document is None:
            documents = EngineeringDocumentVersion.objects.filter(
                related_routing_id=step.routing_version_id,
                status="released",
            )
            if context.engineering_calculation is not None:
                documents = documents.filter(engineering_calculation=context.engineering_calculation)
            if context.order_engineering_instance is not None:
                documents = documents.filter(order_engineering_instance=context.order_engineering_instance)
            if context.order_engineering_baseline is not None:
                documents = documents.filter(order_engineering_baseline=context.order_engineering_baseline)
            if context.bom_version is not None:
                documents = documents.filter(related_bom=context.bom_version)
            document_rows = list(documents.order_by("pk")[:2])
            if not document_rows:
                return {"status": "MISSING"}
            if len(document_rows) != 1:
                return {
                    "status": "INVALID",
                    "pendingCode": "FORMAL_ENGINEERING_DOCUMENT_NOT_UNIQUE",
                    "pendingReason": "存在多个候选工程资料版本，无法唯一确定正式条件来源。",
                }

            document = document_rows[0]

        error = cls._document_chain_error(step, document, context)
        if error:
            return {
                "status": "INVALID",
                "pendingCode": "FORMAL_ENGINEERING_CHAIN_INVALID",
                "pendingReason": error,
                "document": document,
            }

        facts = list(EngineeringDerivedFact.objects.filter(
            calculation_id=document.engineering_calculation_id,
            fact_code=condition["factCode"],
            source_type="ENGINEERING_DERIVED",
            status="active",
        ).order_by("sequence", "pk")[:2])
        if not facts:
            return {"status": "MISSING", "document": document}
        if len(facts) != 1:
            return {
                "status": "INVALID",
                "pendingCode": "FORMAL_CONDITION_FACT_NOT_UNIQUE",
                "pendingReason": "正式工程条件事实存在重复，无法安全判断。",
                "document": document,
            }
        fact = facts[0]
        if fact.value_type.lower() not in {"bool", "boolean"} or not isinstance(fact.value, bool):
            return {
                "status": "INVALID",
                "pendingCode": "FORMAL_CONDITION_FACT_INVALID",
                "pendingReason": "正式工程条件必须是唯一布尔事实。",
                "document": document,
                "fact": fact,
            }
        return {
            "status": "RESOLVED",
            "result": REQUIRED if fact.value else NOT_APPLICABLE,
            "document": document,
            "fact": fact,
        }

    @staticmethod
    def _document_chain_error(step, document, context):
        if document.status != "released":
            return "工程资料版本尚未发布。"
        if document.related_routing_id != step.routing_version_id:
            return "工程资料版本未绑定当前精确路线版本。"
        if not document.engineering_calculation_id:
            return "工程资料版本未冻结正式工程核算修订。"
        calculation = document.engineering_calculation
        if calculation.status != "completed":
            return "工程资料版本引用的工程核算尚未完成。"
        if not document.order_engineering_instance_id or not document.order_engineering_baseline_id:
            return "工程资料版本未冻结订单工程实例和已确认工程基线。"
        if production_status(document.order_engineering_baseline) != "confirmed":
            return "工程资料版本引用的工程基线尚未确认。"
        if calculation.engineering_instance_id != document.order_engineering_instance_id:
            return "工程核算与工程资料版本的订单工程实例不一致。"
        if context.engineering_calculation is not None and calculation.pk != context.engineering_calculation.pk:
            return "调用上下文工程核算与工程资料版本不一致。"
        if context.order_engineering_instance is not None and (
            document.order_engineering_instance_id != context.order_engineering_instance.pk
        ):
            return "调用上下文订单工程实例与工程资料版本不一致。"
        if context.order_engineering_baseline is not None and (
            document.order_engineering_baseline_id != context.order_engineering_baseline.pk
        ):
            return "调用上下文工程基线与工程资料版本不一致。"
        if context.bom_version is not None and document.related_bom_id != context.bom_version.pk:
            return "调用上下文BOM版本与工程资料版本不一致。"
        return ""

    @staticmethod
    def _payload(
        *, step, contract, result, contract_source, contract_explicit,
        pending_code="", pending_reason="", document=None, fact=None, manual=None,
        formal_source_label="",
    ):
        mode = contract.get("mode") if contract else None
        condition_code = contract.get("conditionCode", "") if contract else ""
        condition = CONDITION_REGISTRY.get(condition_code, {})
        return {
            "contractVersion": CONTRACT_VERSION,
            "stepId": step.pk,
            "mode": mode,
            "modeLabel": MODE_LABELS.get(mode, "待维护"),
            "conditionCode": condition_code,
            "conditionLabel": condition.get("label", "不适用" if mode == MANDATORY else "待维护"),
            "formalSourceLabel": formal_source_label or condition.get(
                "sourceLabel", "路线版本步骤正式合同" if mode == MANDATORY else "尚未确定",
            ),
            "result": result,
            "resultLabel": RESULT_LABELS[result],
            "pendingCode": pending_code,
            "pendingReason": pending_reason,
            "contractSource": contract_source,
            "contractExplicit": contract_explicit,
            "formalApplicabilityValidated": bool(contract_explicit and result != PENDING),
            "engineeringDocumentVersionId": getattr(document, "pk", None),
            "engineeringDocumentVersionNo": getattr(document, "document_version", "") if document else "",
            "engineeringDerivedFactId": getattr(fact, "pk", None),
            "manualDecision": (manual or {}).get("decision"),
            "manualDecisionLabel": (manual or {}).get("decisionLabel", ""),
            "manualDecisionSourceLabel": (manual or {}).get("sourceLabel", ""),
            "manualDecisionConfirmedBy": (manual or {}).get("confirmedByUsername", ""),
            "manualDecisionConfirmedAt": (manual or {}).get("confirmedAt", ""),
            "manualDecisionAuditId": (manual or {}).get("auditId"),
        }
