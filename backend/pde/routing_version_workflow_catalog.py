"""System-owned Workflow catalog for RoutingVersion formal review.

The review Workflow is a product contract, not business data that employees
should type into the generic process designer.  This catalog creates the one
canonical definition and its one canonical review node idempotently.  It never
grants a role or scope and never creates a WorkflowInstance, ApprovalTask or
ApprovalDecision.
"""

from __future__ import annotations

from hashlib import sha256
import json

from django.db import transaction

from system.models import Permission
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


CATALOG_CONTRACT = "PCE-ROUTING-VERSION-REVIEW-WORKFLOW-CATALOG-V1.0"
REVIEW_PERMISSION = "pde.routing_version.review"
DOCUMENT_TYPE = "RoutingVersion"
COMPATIBLE_DOCUMENT_TYPES = (DOCUMENT_TYPE, "pde.RoutingVersion", "routing-versions")

CANONICAL_DEFINITION = {
    "definition_code": "PDE_ROUTING_VERSION_FORMAL_REVIEW",
    "definition_name": "工艺路线版本正式评审流程",
    "business_domain": "PDE",
    "description": "系统目录自动生成；用于工艺路线版本正式评审，不执行发布。",
    "document_type": DOCUMENT_TYPE,
    "version": 1,
    "active": True,
}

CANONICAL_NODE = {
    "node_code": "FORMAL_REVIEW",
    "node_name": "正式评审",
    "sequence": 1,
    "business_action_code": REVIEW_PERMISSION,
    "active": True,
    "description": "由具备正式权限、组织范围、岗位与职责的业务人员作出评审决定。",
}


def _hash_definition(definition, nodes):
    fact = {
        "definitionCode": definition.definition_code,
        "definitionName": definition.definition_name,
        "businessDomain": definition.business_domain,
        "description": definition.description,
        "documentType": definition.document_type,
        "version": definition.version,
        "active": definition.active,
        "nodes": [
            {
                "nodeCode": node.node_code,
                "nodeName": node.node_name,
                "sequence": node.sequence,
                "businessActionCode": node.business_action_code,
                "active": node.active,
                "description": node.description,
            }
            for node in nodes
        ],
    }
    return sha256(
        json.dumps(
            fact,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _assert_definition_contract(definition):
    mismatches = {
        field: {"expected": expected, "actual": getattr(definition, field)}
        for field, expected in CANONICAL_DEFINITION.items()
        if getattr(definition, field) != expected
    }
    nodes = list(definition.nodes.order_by("sequence", "node_code"))
    if len(nodes) != 1:
        mismatches["nodes"] = {"expected": 1, "actual": len(nodes)}
    elif any(getattr(nodes[0], field) != expected for field, expected in CANONICAL_NODE.items()):
        mismatches["node"] = {
            "expected": CANONICAL_NODE,
            "actual": {
                field: getattr(nodes[0], field)
                for field in CANONICAL_NODE
            },
        }
    if mismatches:
        raise ValueError(
            "工艺路线版本正式评审Workflow已存在但与系统目录合同不一致；"
            f"停止自动覆盖：{json.dumps(mismatches, ensure_ascii=False, sort_keys=True)}"
        )
    expected_hash = _hash_definition(definition, nodes)
    if definition.definition_hash != expected_hash:
        raise ValueError(
            "工艺路线版本正式评审Workflow内容哈希与系统目录合同不一致；停止自动覆盖。"
        )
    return nodes[0]


@transaction.atomic
def ensure_routing_version_workflow_catalog():
    """Create or verify the canonical review template without human fields."""

    permission = Permission.objects.select_for_update().filter(code=REVIEW_PERMISSION).first()
    if not permission:
        raise ValueError(f"正式权限{REVIEW_PERMISSION}尚未登记，不能生成Workflow目录。")

    definition = (
        ProcessDefinition.objects.select_for_update()
        .prefetch_related("nodes")
        .filter(definition_code=CANONICAL_DEFINITION["definition_code"])
        .first()
    )
    if definition:
        node = _assert_definition_contract(definition)
        return {
            "contractVersion": CATALOG_CONTRACT,
            "sourceCode": "SYSTEM_CATALOG",
            "sourceLabel": "系统目录自动生成",
            "created": False,
            "definitionId": definition.pk,
            "definitionCode": definition.definition_code,
            "nodeId": node.pk,
            "nodeCode": node.node_code,
            "definitionHash": definition.definition_hash,
        }

    conflicts = list(
        ProcessDefinition.objects.select_for_update()
        .filter(document_type__in=COMPATIBLE_DOCUMENT_TYPES, active=True)
        .values_list("pk", "definition_code", "document_type")
    )
    if conflicts:
        raise ValueError(
            "正式库已存在其他启用的RoutingVersion Workflow，停止自动生成以避免双重权威："
            f"{conflicts}"
        )

    definition = ProcessDefinition.objects.create(
        **CANONICAL_DEFINITION,
        definition_hash="",
    )
    node = WorkflowNodeDefinition.objects.create(
        process_definition=definition,
        **CANONICAL_NODE,
    )
    definition.definition_hash = _hash_definition(definition, [node])
    definition.save(update_fields=["definition_hash"])
    return {
        "contractVersion": CATALOG_CONTRACT,
        "sourceCode": "SYSTEM_CATALOG",
        "sourceLabel": "系统目录自动生成",
        "created": True,
        "definitionId": definition.pk,
        "definitionCode": definition.definition_code,
        "nodeId": node.pk,
        "nodeCode": node.node_code,
        "definitionHash": definition.definition_hash,
    }


__all__ = [
    "CANONICAL_DEFINITION",
    "CANONICAL_NODE",
    "CATALOG_CONTRACT",
    "ensure_routing_version_workflow_catalog",
]
